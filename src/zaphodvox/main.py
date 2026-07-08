import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from zaphodvox import __version__
from zaphodvox.audio import concat_files
from zaphodvox.encoder import Encoder
from zaphodvox.manifest import Fragment, Manifest
from zaphodvox.named_voices import NamedVoices
from zaphodvox.arg_parser import parse_args
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
    console = Console(highlight=False)
    handle_version_and_ntd(args, console)
    try:
        validate(args)

        if not args.basename:
            if args.inputfile:
                args.basename = args.inputfile.stem
            elif args.voice_id:
                args.basename = args.voice_id.lower()
        args.encoder, args.voice = encoder_voice(args)
        text, manifest = read_text_manifest(args.inputfile)
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

    if args.version:
        console.print(f'{Path(sys.argv[0]).stem}, version {__version__}')
        sys.exit(0)
    if not any([clean, plan, encode, concat, audition]):
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
    audition: Optional[int] = args.audition

    if not (inputfile or audition):
        raise ValueError('No input file specified.')
    if (encode or audition) and not encoder_name:
        raise ValueError('No encoder specified.')
    if audition:
        if any([args.clean, args.plan, args.encode, args.concat]):
            raise ValueError(
                '--audition cannot be combined with other actions.'
            )
        if not args.voice_id:
            raise ValueError('Auditioning requires a preset "--voice-id".')
        if args.voice_ref_audio:
            raise ValueError(
                'Auditioning generates reference clips; do not supply '
                '"--voice-ref-audio".'
            )
        if not (args.audition_text or inputfile):
            raise ValueError('No audition text specified.')


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
    """Synthesizes several candidate reference clips of a preset voice, one per
        seed, so the best-sounding take can be adopted as a clone reference.

    Args:
        args: The parsed command-line arguments.
        text: The input file text, used for the sample sentence when
            `--audition-text` is not given.
        console: The `Console` object.

    Raises:
        ValueError: If no audition text can be determined.
    """
    basename: str = args.basename
    count: int = args.audition
    encoder: Encoder = args.encoder
    instruct: Optional[str] = args.voice_instruct
    language: str = args.voice_language
    out_dir: Optional[Path] = args.out_dir
    voice_id: str = args.voice_id

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

    file_ext = encoder.file_extension
    fragments = [
        Fragment(
            text=audition_text,
            filename=f'{basename}-audition-{seed:02}.{file_ext}',
            voice=QwenVoice(
                voice_id=voice_id, language=language,
                instruct=instruct, seed=seed
            )
        )
        for seed in range(count)
    ]
    encoder.encode_manifest(Manifest(fragments=fragments), encode_dir=out_dir)

    index = [
        {
            'seed': seed,
            'filename': fragment.filename,
            'voice_id': voice_id,
            'instruct': instruct,
            'language': language,
            'text': audition_text,
        }
        for seed, fragment in enumerate(fragments)
    ]
    index_fp = file_path(None, f'{basename}-audition.json', out_dir)
    with open(str(index_fp), 'w') as f:
        f.write(json.dumps(index, indent=4))

    header = f'Auditioning "{voice_id}"'
    if instruct:
        header += f'  ·  instruct: "{instruct}"'
    header += f'  ·  {language}'
    console.print(header)
    table = Table()
    table.add_column('seed', justify='right')
    table.add_column('file')
    for seed, fragment in enumerate(fragments):
        table.add_row(str(seed), fragment.filename)
    console.print(table)
    first = fragments[0].filename
    console.print(
        'Adopt one, e.g. seed 0:\n'
        f'  as a clone anchor:  --voice-ref-audio={first} '
        '--voice-ref-text="<audition text>"\n'
        f'  or reuse its seed:  --voice-id={voice_id} --voice-seed=0'
    )
    console.print(f'[dim]Index written to {index_fp}[/dim]')


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
        with open(str(inputfile), 'r') as file:
            text = file.read()
            try:
                manifest = Manifest.model_validate_json(text)
            except ValueError:
                manifest = None
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
        with open(str(path), 'r') as file:
            voices_json = file.read()
        voices = NamedVoices.model_validate_json(voices_json)
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
    with open(str(file_path), 'w') as f:
        f.write(text)


def write_manifest(manifest: Manifest, file_path: Path) -> None:
    """Writes the given manifest to the specified file path.

    Args:
        manifest: The `Manifest` to be written.
        file_path: The `Path` to the output file where the manifest will be saved.
    """
    with open(str(file_path), 'w') as f:
        f.write(manifest.model_dump_json(indent=4, exclude_none=True))


if __name__ == '__main__':
    main()
