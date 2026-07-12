import io
import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from zaphodvox import __version__
from zaphodvox.audio import concat_files
from zaphodvox.dictionary import add_words, build_speller, load_words
from zaphodvox.encoder import Encoder
from zaphodvox.manifest import Fragment, Manifest
from zaphodvox.named_voices import NamedVoices
from zaphodvox.arg_parser import parse_args
from zaphodvox.llm import LLMClient, proofread
from zaphodvox.paths import abspath, clip_filename, rebase_ref
from zaphodvox.proof import ProofReport, proof_text
from zaphodvox.qwen.voice import QwenVoice
from zaphodvox.text import clean_text, parse_text
from zaphodvox.voice import Voice


def main(
    raw_args: Optional[list[str]] = None,
    preparsed_args: Optional[Namespace] = None
) -> None:
    """Main function that performs text cleaning and text-to-speech encoding.

    Args:
        raw_args: The list of command-line arguments. Defaults to `None`.
        preparsed_args: The parsed command-line arguments. Defaults to `None`.

    Raises:
        ValueError: If the specified encoder is not found.
    """
    args: Namespace = preparsed_args or parse_args(raw_args or sys.argv[1:])
    # Manuscripts routinely contain characters the Windows console codepage
    # (cp1252) cannot encode, and `--proof` quotes the offending text back at
    # the user. Replace the unencodable rather than raise.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    console = Console(highlight=False)
    handle_version_and_ntd(args, console)
    try:
        validate(args)

        if args.add_word:
            add_word(args, console)
            return

        if not args.basename:
            if args.inputfile:
                args.basename = args.inputfile.stem
            elif args.voice_id:
                args.basename = args.voice_id.lower()
            elif args.voice_description:
                args.basename = 'design'
        args.encoder, args.voice = encoder_voice(args)
        text, manifest = read_text_manifest(args.inputfile)

        if args.adopt is not None:
            adopt(args, text, console)
            return

        if args.proof:
            proof(args, text, console)
            return

        args.named_voices = read_voices(args.voices_file, manifest)
        args.indexes = args.indexes if manifest else None

        if args.audition:
            audition(args, text, console)
            return

        if args.clean and not manifest:
            text = clean(args, text)

        if args.plan or args.encode:
            manifest = plan(args, text, manifest)
            if args.plan:
                fn = f'{args.basename}-plan.json'
                fp = file_path(args.plan_out, fn, args.out_dir)
                write_manifest(manifest, fp)

        if args.encode:
            assert manifest is not None
            manifest = encode(args, manifest)
            if args.save_manifest:
                fn = f'{args.basename}-manifest.json'
                fp = file_path(args.manifest_out, fn, args.out_dir)
                write_manifest(manifest, fp)

        if args.concat and manifest:
            concat(args, manifest)
    except Exception as e:
        console.print(f'[bold red]Er, error: {e}[/bold red]')
        sys.exit(1)


def handle_version_and_ntd(args: Namespace, console: Console) -> None:
    """Handles the --version command-line argument and exits if there is
        nothing to do.

    Args:
        args: The parsed command-line arguments.
        console: The `Console` object.
    """
    clean: bool = args.clean
    plan: bool = args.plan
    encode: bool = args.encode
    concat: bool = args.concat
    audition: bool = bool(args.audition)
    adopt: bool = args.adopt is not None
    proof: bool = args.proof
    add_word: bool = bool(args.add_word)

    if args.version:
        console.print(f'{Path(sys.argv[0]).stem}, version {__version__}')
        sys.exit(0)
    if not any(
        [clean, plan, encode, concat, audition, adopt, proof, add_word]
    ):
        console.print(
            "[italic dim]Nothing to do... I'd give you advice, "
            "but you wouldn't listen. No one ever does.[/italic dim]"
        )
        sys.exit(0)


def validate(args: Namespace) -> None:
    """Validates the specified command-line arguments.

    Args:
        args: The parsed command-line arguments.

    Raises:
        ValueError: If there is a problem with the specified arguments.
    """
    inputfile: Optional[Path] = args.inputfile
    encoder_name: Optional[str] = args.encoder_name
    encode: bool = args.encode
    audition: Optional[str] = args.audition
    add_word = args.add_word

    if add_word:
        if not args.dict:
            raise ValueError('--add-word requires --dict.')
        return
    if not (inputfile or audition):
        raise ValueError('No input file specified.')
    if (encode or audition) and not encoder_name:
        raise ValueError('No encoder specified.')
    if args.proof and any(
        [args.clean, args.plan, encode, args.concat, audition,
         args.adopt is not None]
    ):
        raise ValueError('--proof cannot be combined with other actions.')
    if audition:
        if any([args.clean, args.plan, args.encode, args.concat]):
            raise ValueError(
                '--audition cannot be combined with other actions.'
            )
        sources = [
            args.voice_id, args.voice_ref_audio, args.voice_description
        ]
        if not any(sources):
            raise ValueError(
                'Auditioning requires a preset "--voice-id", a clone '
                '"--voice-ref-audio", or a "--voice-description".'
            )
        if sum(source is not None for source in sources) > 1:
            raise ValueError(
                'Specify exactly one of "--voice-id", "--voice-ref-audio", or '
                '"--voice-description".'
            )
        if not (args.audition_text or inputfile):
            raise ValueError('No audition text specified.')
    if args.adopt is not None:
        if any([args.clean, args.plan, encode, args.concat, audition]):
            raise ValueError('--adopt cannot be combined with other actions.')
        if not inputfile:
            raise ValueError('--adopt requires an audition index inputfile.')
        if not args.voice_name:
            raise ValueError('--adopt requires --voice-name.')
        if not args.voices_file:
            raise ValueError('--adopt requires --voices-file.')


def encoder_voice(
    args: Namespace
) -> tuple[Optional[Encoder], Optional[Voice]]:
    """Creates the encoder and voice (if configured) from the specified
        command-line arguments.

    Args:
        args: The parsed command-line arguments.

    Returns:
        A tuple containing the encoder and voice from the specified
            command-line arguments.
    """
    encoder_name: str = args.encoder_name

    encoder: Optional[Encoder] = None
    voice: Optional[Voice] = None
    if encoder_name:
        for encoder_class in Encoder.__subclasses__():
            if encoder_name == encoder_class.name:
                encoder, voice = encoder_class.from_args(args)
                break
        if not encoder:
            raise ValueError(f'Encoder "{encoder_name}" not found.')
    return encoder, voice


def clean(args: Namespace, text: str) -> str:
    """Cleans the specified text and returns it.

    Args:
        text: The text to be cleaned.
        max_chars: The maximum number of characters to allow in the cleaned
            text.

    Returns:
        The cleaned text.
    """
    basename: str = args.basename
    clean_out: Optional[Path] = args.clean_out
    max_chars: Optional[int] = args.max_chars
    out_dir: Optional[Path] = args.out_dir

    text = clean_text(text, max_chars=max_chars)
    fn = f'{basename}-clean.txt'
    fp = file_path(clean_out, fn, out_dir)
    write_cleaned(text, fp)
    return text


def plan(
    args: Namespace, text: str, manifest: Optional[Manifest]
) -> Manifest:
    """Optionally cleans the text and then generates a plan manifest, both of
        which may be written to file.

    Args:
        args: The parsed command-line arguments.
        text: The text to be cleaned/planned.

    Returns:
        The plan manifest.
    """
    basename: str = args.basename
    encoder: Optional[Encoder] = args.encoder
    max_chars: Optional[int] = args.max_chars
    named_voices: NamedVoices = args.named_voices
    silence_duration: Optional[int] = args.silence_duration
    voice: Optional[Voice] = args.voice
    voice_name: Optional[str] = args.voice_name

    plan_manifest = None
    encoder_voices = named_voices.encoder_voices()
    if not voice and voice_name:
        voice = encoder_voices.get(voice_name)
    if manifest:
        fragments = []
        for fragment in manifest.fragments:
            f = fragment.model_copy()
            if f.voice_name:
                f.voice = encoder_voices.get(f.voice_name)
            elif voice:
                f.voice = voice
            # Otherwise keep the fragment's own inline voice (if any).
            fragments.append(f)
    else:
        fragments = parse_text(
            text, voice=voice, voices=encoder_voices, max_chars=max_chars
        )
    file_ext = file_extension(manifest, encoder)
    plan_manifest = Manifest.plan(
        fragments, basename, file_ext, silence_duration=silence_duration
    )
    plan_manifest.set_used_voices(named_voices.voices)
    return plan_manifest


def encode(args: Namespace, manifest: Manifest) -> Manifest:
    """Encodes the specified manifest and optionally concatenates the
        encoded files to the specified directory.

    Args:
        args: The parsed command-line arguments.
        manifest: The manifest to encode.

    Returns:
        The encoded manifest.
    """
    out_dir: Optional[Path] = args.out_dir
    encoder: Encoder = args.encoder
    index_str: Optional[str] = args.indexes
    named_voices: NamedVoices = args.named_voices
    silence_duration: Optional[int] = args.silence_duration

    manifest = encoder.encode_manifest(
        manifest,
        encode_dir=out_dir,
        indexes=parse_indexes(index_str, manifest.length),
        voices=named_voices.encoder_voices(),
        silence_duration=silence_duration
    )
    manifest.set_used_voices(named_voices.voices)
    return manifest


def concat(args: Namespace, manifest: Manifest) -> None:
    """Encodes the specified manifest and optionally concatenates the
        encoded files to the specified directory.

    Args:
        args: The parsed command-line arguments.
        manifest: The manifest to encode and/or concat.
    """
    basename: str = args.basename
    concat_out: Optional[Path] = args.concat_out
    out_dir: Optional[Path] = args.out_dir
    encoder: Encoder = args.encoder

    file_ext = file_extension(manifest, encoder)
    filename = f'{basename}.{file_ext}'
    concat_out = file_path(concat_out, filename, out_dir)
    concat_files(out_dir or Path(), manifest, file_ext, concat_out)


AUDITION_MIN_CHARS = 120
"""A soft minimum audition-text length (~10s of speech) below which a warning
is shown, since short clips make poor clone references."""


def audition(args: Namespace, text: str, console: Console) -> None:
    """Synthesizes several candidate reference clips of a preset, designed, or
        cloned voice, one per seed, so the best-sounding take can be adopted as
        a clone reference.

    Auditioning a clone (`--voice-ref-audio`) re-clones an existing voice: the
    candidates are synthetic takes of it, so adopting one re-anchors the voice
    to clean studio audio. That is the way to launder a noisy human recording
    into a usable reference. It costs a generation of fidelity, so it is worth
    doing once, from the original recording — not to a clip that is itself
    already a synthetic take.

    Args:
        args: The parsed command-line arguments.
        text: The input file text, used for the sample sentence when
            `--audition-text` is not given.
        console: The `Console` object.

    Raises:
        ValueError: If no audition text can be determined.
    """
    basename: str = args.basename
    description: Optional[str] = args.voice_description
    encoder: Encoder = args.encoder
    instruct: Optional[str] = args.voice_instruct
    language: str = args.voice_language
    out_dir: Optional[Path] = args.out_dir
    ref_audio: Optional[Path] = args.voice_ref_audio
    ref_text: Optional[str] = args.voice_ref_text
    temperature: Optional[float] = args.voice_temperature
    voice_id: Optional[str] = args.voice_id

    seeds = parse_seeds(args.audition)
    audition_text = args.audition_text or next(
        (line.strip() for line in text.split('\n') if line.strip()), ''
    )
    if not audition_text:
        raise ValueError('No audition text specified.')
    if len(audition_text) < AUDITION_MIN_CHARS:
        console.print(
            '[yellow]Warning: the audition text is short; aim for ~10-15s of '
            f'speech ({AUDITION_MIN_CHARS}+ characters) for a good clone '
            'reference.[/yellow]'
        )

    def candidate_voice(seed: int) -> QwenVoice:
        if ref_audio:
            # Re-cloning an existing clone. The candidates are synthetic takes
            # of the source voice, so adopting one re-anchors the voice to clean
            # studio audio instead of the original recording.
            return QwenVoice(
                ref_audio=ref_audio.as_posix(), ref_text=ref_text,
                language=language, seed=seed, temperature=temperature
            )
        if description:
            return QwenVoice(
                description=description, language=language,
                seed=seed, temperature=temperature
            )
        return QwenVoice(
            voice_id=voice_id, language=language,
            instruct=instruct, seed=seed, temperature=temperature
        )

    file_ext = encoder.file_extension
    fragments = [
        Fragment(
            text=audition_text,
            filename=f'{basename}-audition-{seed:02}.{file_ext}',
            voice=candidate_voice(seed)
        )
        for seed in seeds
    ]
    encoder.encode_manifest(Manifest(fragments=fragments), encode_dir=out_dir)

    index = [
        {
            'seed': seed,
            'filename': fragment.filename,
            'voice_id': voice_id,
            'ref_audio': ref_audio.as_posix() if ref_audio else None,
            'description': description,
            'instruct': instruct,
            'language': language,
            'temperature': temperature,
            'text': audition_text,
        }
        for seed, fragment in zip(seeds, fragments)
    ]
    index_fp = file_path(None, f'{basename}-audition.json', out_dir)
    with open(str(index_fp), 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(index, indent=4))

    if ref_audio:
        header = f'Auditioning clone of "{ref_audio}"'
        if not ref_text:
            header += '  ·  [dim]zero-shot (no --voice-ref-text)[/dim]'
    elif description:
        header = f'Auditioning designed voice: "{description}"'
    else:
        header = f'Auditioning "{voice_id}"'
        if instruct:
            header += f'  ·  instruct: "{instruct}"'
    if temperature is not None:
        header += f'  ·  temp: {temperature}'
    header += f'  ·  {language}'
    console.print(header)
    table = Table()
    table.add_column('seed', justify='right')
    table.add_column('file')
    for seed, fragment in zip(seeds, fragments):
        table.add_row(str(seed), fragment.filename)
    console.print(table)
    console.print(
        f'Adopt the one you like as a clone voice, e.g. seed {seeds[0]}:\n'
        f'  zaphodvox --adopt {seeds[0]} --voice-name <name> --voices-file '
        f'voices.json {index_fp}'
    )
    console.print(f'[dim]Index written to {index_fp}[/dim]')


def adopt(args: Namespace, text: str, console: Console) -> None:
    """Adopts an audition candidate as a clone voice in a voices file.

    Reads the audition index (the inputfile), builds a `QwenVoice` that clones
    the candidate for the requested seed, and adds/updates it under
    `--voice-name` in `--voices-file` (created if it does not exist).

    Args:
        args: The parsed command-line arguments.
        text: The audition index JSON (the inputfile contents).
        console: The `Console` object.

    Raises:
        ValueError: If no candidate matches the requested seed.
    """
    seed: int = args.adopt
    voice_name: str = args.voice_name
    voices_file: Path = args.voices_file

    index = json.loads(text)
    entry = next((e for e in index if e.get('seed') == seed), None)
    if entry is None:
        raise ValueError(f'No audition candidate for seed {seed}.')

    inputfile: Path = args.inputfile
    candidate = inputfile.parent / entry['filename']
    clip = voices_file.parent / clip_filename(voice_name, candidate.suffix)
    copied = copy_clip(candidate, clip)
    voice = QwenVoice(
        ref_audio=clip.as_posix(),
        ref_text=entry.get('text'),
        language=entry.get('language', 'English'),
        seed=args.voice_seed if args.voice_seed is not None else seed,
        temperature=(
            args.voice_temperature if args.voice_temperature is not None
            else entry.get('temperature')
        ),
    )

    named = NamedVoices()
    try:
        with open(str(voices_file), 'r', encoding='utf-8') as f:
            named = NamedVoices.model_validate_json(f.read())
        anchor_voices(named.voices, voices_file.parent)
    except FileNotFoundError:
        pass
    voices = dict(named.voices or {})
    existed = voice_name in voices
    voices[voice_name] = voice
    named.voices = voices
    # The new voice's path is relative to where the command was run; the ones
    # already in the file are relative to the file. Rewrite both to the file, so
    # a clip beside it stays a bare filename and the library stays movable.
    rebase_voices([*voices.values()], voices_file.parent)
    with open(str(voices_file), 'w', encoding='utf-8', newline='\n') as f:
        f.write(named.model_dump_json(indent=4, exclude_none=True))

    if copied:
        console.print(f'Copied {candidate} -> {clip}')
    verb = 'Updated' if existed else 'Added'
    console.print(f'{verb} voice "{voice_name}" in {voices_file}:')
    console.print(voice.model_dump_json(indent=4, exclude_none=True))
    if copied:
        console.print(
            '[dim]The clip now lives beside the voices file; the audition '
            'files can be deleted.[/dim]'
        )


def proof(args: Namespace, text: str, console: Console) -> None:
    """Proofreads the text and writes a report of deterministic issues
        (spelling against a project wordlist, junk/unusual characters,
        whitespace).

    Args:
        args: The parsed command-line arguments.
        text: The manuscript text.
        console: The `Console` object.
    """
    basename: str = args.basename
    dict_path: Path = args.dict or Path(f'{basename}.dict')
    out_dir: Optional[Path] = args.out_dir

    speller = build_speller(args.dict_language, load_words(dict_path))
    findings = proof_text(text, speller).findings
    if args.llm_url:
        client = LLMClient(args.llm_url, args.llm_model)
        findings += proofread(text, client)
    report = ProofReport.from_findings(findings)
    report.source_file = str(args.inputfile)

    fp = file_path(args.proof_out, f'{basename}-proof.json', out_dir)
    with open(str(fp), 'w', encoding='utf-8', newline='\n') as f:
        f.write(report.model_dump_json(indent=4, exclude_none=True))

    total = len(report.findings)
    if not total:
        console.print('[green]No issues found.[/green]')
    else:
        table = Table(title=f'{total} issue(s)')
        table.add_column('line', justify='right')
        table.add_column('type')
        table.add_column('text')
        table.add_column('message')
        for finding in sorted(report.findings, key=lambda f: f.line):
            detail = finding.message
            if finding.suggestions:
                detail += '  → ' + ', '.join(finding.suggestions)
            if finding.count and finding.count > 1:
                detail += f'  ({finding.count}×)'
            table.add_row(str(finding.line), finding.type, finding.text, detail)
        console.print(table)
        console.print(
            '[dim]'
            + '  '.join(f'{k}: {v}' for k, v in report.summary.items())
            + '[/dim]'
        )
    console.print(f'[dim]Report written to {fp}[/dim]')


def add_word(args: Namespace, console: Console) -> None:
    """Adds word(s) to the project wordlist and exits.

    Args:
        args: The parsed command-line arguments.
        console: The `Console` object.
    """
    dict_path: Path = args.dict
    added = add_words(dict_path, args.add_word)
    if added:
        console.print(
            f'Added {len(added)} word(s) to {dict_path}: ' + ', '.join(added)
        )
    else:
        console.print(f'No new words added to {dict_path}.')


def copy_clip(source: Path, dest: Path) -> bool:
    """Copies an adopted reference clip in beside the voices file.

    The audition candidates are throwaways: the rest of them get deleted, and
    the one that is kept should not be left sitting in a scratch directory that
    a voices library then depends on. Copying it in means the library holds
    every clip it refers to, and the audition output can be discarded wholesale.

    Nothing is deleted here -- the other candidates are left where they are.

    Args:
        source: The `Path` of the audition candidate.
        dest: The `Path` to copy it to.

    Returns:
        `True` if the clip was copied, `False` if it was already in place.

    Raises:
        ValueError: If the candidate does not exist.
    """
    if not source.is_file():
        raise ValueError(f'Audition candidate "{source}" not found.')
    if abspath(source) == abspath(dest):
        return False
    with open(str(source), 'rb') as f_in:
        data = f_in.read()
    with open(str(dest), 'wb') as f_out:
        f_out.write(data)
    return True


def anchor_voices(voices: Optional[dict[str, QwenVoice]], base_dir: Path) -> None:
    """Anchors each voice's relative `ref_audio` to the directory of the file it
    was read from.

    Args:
        voices: The named voices to anchor.
        base_dir: The directory `Path` of the file the voices were read from.
    """
    for voice in (voices or {}).values():
        voice.anchor(base_dir)


def rebase_voices(voices: list[Optional[Voice]], target_dir: Path) -> None:
    """Rewrites each voice's `ref_audio` in place so that it stays valid from
    the file it is about to be written into.

    A voice is routinely copied out of the file that declared it (a shared
    voices file) and into another (a project's manifest). Its path is only
    meaningful relative to an anchor, so moving the voice without rewriting the
    path would silently repoint it at the wrong directory.

    Args:
        voices: The voices to rewrite. Non-Qwen and non-clone voices are
            ignored.
        target_dir: The directory `Path` of the file being written.
    """
    for voice in voices:
        if isinstance(voice, QwenVoice) and voice.ref_audio:
            voice.ref_audio = rebase_ref(
                voice.ref_audio, voice.base_dir, target_dir
            )
            voice.anchor(target_dir)


def read_text_manifest(
    inputfile: Optional[Path]
) -> tuple[str, Optional[Manifest]]:
    """Reads the text and optionally creates a manifest from the specified
        input file.

    Args:
        inputfile: The `Path` to the input file.

    Returns:
        A tuple containing the text and manifest from the specified input file.
    """
    text = ''
    manifest = None
    if inputfile:
        with open(str(inputfile), 'r', encoding='utf-8') as file:
            text = file.read()
            try:
                manifest = Manifest.model_validate_json(text)
            except ValueError:
                manifest = None
        if manifest:
            base_dir = inputfile.parent
            anchor_voices(manifest.voices, base_dir)
            for fragment in manifest.fragments:
                if isinstance(fragment.voice, QwenVoice):
                    fragment.voice.anchor(base_dir)
    return text, manifest


def read_voices(
    path: Optional[Path], manifest: Optional[Manifest]
) -> NamedVoices:
    """Reads the voices file at the specified path.

    Args:
        path: The `Path` to the voices file.
        manifest: The `Manifest` to be used to add voices.

    Returns:
        The `NamedVoices` object.
    """
    voices = NamedVoices()
    if path:
        with open(str(path), 'r', encoding='utf-8') as file:
            voices_json = file.read()
        voices = NamedVoices.model_validate_json(voices_json)
        anchor_voices(voices.voices, path.parent)
    if manifest:
        voices.add_voices(manifest.voices)
    return voices


def parse_indexes(index_str: Optional[str], range_length: int) -> list[int]:
    """Reads the indexes from the specified string.

    Args:
        indexes: The string containing the indexes.
        range_length: The length of the range to use if no indexes are
            specified.

    Returns:
        A list of indexes.
    """
    ranges: list[range] = []
    if index_str_clean := index_str.strip() if index_str else '':
        for part in (s.strip() for s in index_str_clean.split(',')):
            if '-' in part:
                start_str, end_str = (s.strip() for s in part.split('-', 1))
                ranges.append(range(
                    int(start_str) if start_str else 0,
                    int(end_str) if end_str else range_length
                ))
            else:
                idx = int(part)
                ranges.append(range(idx, idx + 1))
    else:
        ranges.append(range(0, range_length))
    return sorted(set(sum((list(r) for r in ranges), [])))


def parse_seeds(spec: str) -> list[int]:
    """Parses a seed spec (in the style of `--indexes`) into a sorted list of
        unique seeds.

    Accepts single seeds and closed ranges, comma-separated: `5`, `1-5`,
    `3,9,20`. Unlike `--indexes`, open-ended ranges (`5-`, `-3`) are not
    supported, as seeds have no upper bound.

    Args:
        spec: The seed spec string.

    Returns:
        The sorted, de-duplicated list of seeds.

    Raises:
        ValueError: If the spec is empty, malformed, or uses an open-ended
            range.
    """
    seeds: set[int] = set()
    for part in (s.strip() for s in spec.split(',')):
        if not part:
            continue
        if '-' in part:
            start_str, end_str = (s.strip() for s in part.split('-', 1))
            if not start_str or not end_str:
                raise ValueError(
                    f'Open-ended seed range "{part}" is not supported; give '
                    'both ends (e.g. "1-5").'
                )
            try:
                start, end = int(start_str), int(end_str)
            except ValueError:
                raise ValueError(f'Invalid seed range "{part}".')
            seeds.update(range(start, end + 1))
        else:
            try:
                seeds.add(int(part))
            except ValueError:
                raise ValueError(f'Invalid seed "{part}".')
    if not seeds:
        raise ValueError('No seeds specified for --audition.')
    return sorted(seeds)


def file_path(
    path: Optional[Path], filename: str, default_dir: Optional[Path]
) -> Path:
    """Returns the specified path if it is a file. Otherwise, if it is a
        directory return it joined with the specified filename. Otherwise,
        return default directory joined with the specified filename.

    Args:
        path: The path to check.
        filename: The filename to join with a directory.
        default_dir: The default directory to join with the filename.

    Returns:
        The specified path if it is a file. Otherwise, if it is a
            directory, the directory joined with the filename.
            Otherwise the default directory joined with the filename.
    """
    if path and path.is_dir():
        path = path / filename
    if not path and default_dir:
        path = default_dir / filename
    if not path:
        path = Path(filename)
    return path


def file_extension(
    manifest: Optional[Manifest], encoder: Optional[Encoder]
) -> str:
    """Returns the file extension for the specified manifest or encoder.

    Args:
        manifest: The manifest to check.
        encoder: The encoder to check.

    Returns:
        The file extension for the specified manifest and encoder.
    """
    file_ext = manifest.file_extension if manifest else None
    if not file_ext and encoder:
        file_ext = encoder.file_extension
    return file_ext or 'wav'


def write_cleaned(text: str, file_path: Path) -> None:
    """Writes the given manifest to the specified file path.

    Args:
        manifest: The `Manifest` to be written.
        file_path: The `Path` to the output file where the manifest will be saved.
    """
    with open(str(file_path), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def write_manifest(manifest: Manifest, file_path: Path) -> None:
    """Writes the given manifest to the specified file path.

    Voice reference paths are rewritten to stay valid from the manifest, since a
    voice may have been read from a voices file in another directory. The copy is
    deep so that rewriting them cannot disturb the in-memory manifest, which a
    subsequent `--concat` still reads from.

    Args:
        manifest: The `Manifest` to be written.
        file_path: The `Path` to the output file where the manifest will be saved.
    """
    manifest = manifest.model_copy(deep=True)
    rebase_voices(
        [*(manifest.voices or {}).values()]
        + [f.voice for f in manifest.fragments],
        file_path.parent
    )
    with open(str(file_path), 'w', encoding='utf-8', newline='\n') as f:
        f.write(manifest.model_dump_json(indent=4, exclude_none=True))


if __name__ == '__main__':
    main()
