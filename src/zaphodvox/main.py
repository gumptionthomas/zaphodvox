import sys
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from rich import print

from zaphodvox.audio import concat_files, copy_files
from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.encoder import Encoder
from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.manifest import Manifest
from zaphodvox.named_voices import NamedVoices
from zaphodvox.parser import parse_args
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
    if not (args.clean or args.plan or args.encode or args.delete_history):
        print(
            "[italic dim]Nothing to do... I'd give you advice, "
            "but you wouldn't listen. No one ever does.[/italic dim]"
        )
        sys.exit(0)
    try:
        args.basename = args.basename or args.inputfile.stem
        args.parent_dir = Path(args.inputfile.parent)
        args.copy_dir = args.copy_dir or Path.cwd()
        args.named_voices = read_voices(args.voices_file)
        text, manifest = read_text_manifest(args.inputfile)
        args.encoder_name = args.encoder
        args.encoder, args.voice = encoder_voice(args)
        if args.encode and not args.encoder:
            raise ValueError('No encoder specified.')
        plan_manifest = clean_plan(args, text, manifest)
        args.named_voices.add_voices(plan_manifest.voices)
        if args.encode and args.encoder:
            args.indexes = None
            if manifest:
                args.encode_dir = args.encode_dir or args.parent_dir
                args.indexes = args.manifest_indexes or None
            if args.encode_dir and args.copy_dir.samefile(args.encode_dir):
                args.copy_dir = None
            encode_concat_copy(args, plan_manifest)
        if args.delete_history and args.encoder:
            if isinstance(args.encoder, ElevenLabsEncoder):
                args.encoder.delete_history()
    except Exception as e:
        print(f'[bold red]Er, error: {e}[/bold red]')
        sys.exit(1)


def encoder_voice(
    args: Namespace
) -> tuple[Optional[GoogleEncoder | ElevenLabsEncoder], Optional[Voice]]:
    """Creates the encoder and voice (if configured) from the specified
        command-line arguments.

    Args:
        args: The parsed command-line arguments.

    Returns:
        A tuple containing the encoder and voice from the specified
            command-line arguments.
    """
    encoder_name: str = args.encoder_name

    encoder: Optional[GoogleEncoder | ElevenLabsEncoder] = None
    voice: Optional[Voice] = None
    if encoder_name:
        if encoder_name == 'google':
            encoder, voice = GoogleEncoder.from_args(args)
        if encoder_name == 'elevenlabs':
            encoder, voice = ElevenLabsEncoder.from_args(args)
        if not encoder:
            raise ValueError(f'Encoder "{encoder_name}" not found.')
    return encoder, voice


def clean_plan(
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
    clean: bool = args.clean
    clean_out: Optional[Path] = args.clean_out
    encode: bool = args.encode
    encoder: Optional[Encoder] = args.encoder
    encoder_name: Optional[str] = args.encoder_name
    max_chars: Optional[int] = args.max_chars
    named_voices: NamedVoices = args.named_voices
    parent_dir: Path = args.parent_dir
    plan: bool = args.plan
    plan_out: Optional[Path] = args.plan_out
    silence_duration: Optional[int] = args.silence_duration
    voice: Optional[Voice] = args.voice

    if clean and not manifest:
        text = clean_text(text, max_chars=max_chars)
        clean_out = clean_out or parent_dir.joinpath(f'{basename}-clean.txt')
        write_cleaned(text, clean_out)
    plan_manifest = Manifest()
    if plan or encode:
        combined_named_voices = NamedVoices(voices=named_voices.voices)
        combined_named_voices.add_voices(manifest.voices if manifest else None)
        encoder_voices = combined_named_voices.encoder_voices(encoder_name)
        fragments = manifest.fragments if manifest else None
        if fragments is not None:
            for fragment in fragments:
                if fragment.voice_name:
                    fragment.voice = encoder_voices.get(fragment.voice_name)
                else:
                    fragment.voice = voice
        else:
            fragments = parse_text(
                text,
                voice=voice,
                voices=encoder_voices,
                max_chars=max_chars
            )
        plan_manifest = Manifest.plan(
            fragments, basename, encoder.file_extension if encoder else 'wav',
            silence_duration=silence_duration
        )
        plan_manifest.set_used_voices(combined_named_voices.voices)
        if plan:
            plan_out = plan_out or parent_dir.joinpath(f'{basename}-plan.json')
            write_manifest(plan_manifest, plan_out)
    return plan_manifest


def encode_concat_copy(args: Namespace, manifest: Manifest) -> None:
    """Encodes the specified manifest, optionally concatenates the
        encoded files, and optionally copies the encoded files to the
        specified directory.

    Args:
        args: The parsed command-line arguments.
        manifest: The manifest to encode, concat, and/or copy.
    """
    basename: str = args.basename
    concat: bool = args.concat
    concat_out: Optional[Path] = args.concat_out
    copy: bool = args.copy
    copy_dir: Optional[Path] = args.copy_dir
    encoder: Encoder = args.encoder
    encoder_name: str = args.encoder_name
    encode_dir: Optional[Path] = args.encode_dir
    indexes: Optional[list[int]] = args.indexes
    manifest_out: Optional[Path] = args.manifest_out
    named_voices: NamedVoices = args.named_voices
    silence_duration: Optional[int] = args.silence_duration

    with TemporaryDirectory() as temp_pathname:
        encoding_dir = encode_dir or Path(temp_pathname)
        encoded_manifest = Manifest()
        encoder_voices = named_voices.encoder_voices(encoder_name)
        try:
            encoded_manifest = encoder.encode_manifest(
                manifest,
                encoding_dir,
                indexes=indexes,
                voices=encoder_voices,
                silence_duration=silence_duration
            )
            encoded_manifest.set_used_voices(named_voices.voices)
            dest_dir = copy_dir or encoding_dir
            if not manifest_out:
                manifest_out = dest_dir.joinpath(f'{basename}-manifest.json')
            write_manifest(encoded_manifest, manifest_out)
            if concat:
                file_ext = encoder.file_extension
                if not concat_out:
                    concat_out = dest_dir.joinpath(f'{basename}.{file_ext}')
                concat_files(
                    encoding_dir,
                    encoded_manifest,
                    file_ext,
                    concat_out
                )
            if (copy or not concat) and copy_dir:
                copy_files(encoding_dir, encoded_manifest, copy_dir)
        except Exception:
            if copy_dir:
                copy_files(encoding_dir, encoded_manifest, copy_dir)
            raise


def read_text_manifest(inputfile: Path) -> tuple[str, Optional[Manifest]]:
    """Reads the text and optionally creates a manifest from the specified
        input file.

    Args:
        inputfile: The `Path` to the input file.

    Returns:
        A tuple containing the text and manifest from the specified input file.
    """
    with open(str(inputfile), 'r') as file:
        text = file.read()
        try:
            manifest = Manifest.model_validate_json(text)
        except ValueError:
            manifest = None
    return text, manifest


def read_voices(path: Optional[Path]) -> NamedVoices:
    """Reads the voices file at the specified path.

    Args:
        path: The `Path` to the voices file.

    Returns:
        The `NamedVoices` object.
    """
    named_voices = None
    if path:
        with open(str(path), 'r') as file:
            voices_json =  file.read()
        named_voices = NamedVoices.model_validate_json(voices_json)
    return named_voices or NamedVoices()


def write_cleaned(text: str, path: Path) -> None:
    """Writes the given manifest to the specified path.

    Args:
        manifest: The `Manifest` to be written.
        path: The `Path` to the output file where the manifest will be saved.
    """
    with open(str(path), 'w') as f:
        f.write(text)


def write_manifest(manifest: Manifest, path: Path) -> None:
    """Writes the given manifest to the specified path.

    Args:
        manifest: The `Manifest` to be written.
        path: The `Path` to the output file where the manifest will be saved.
    """
    with open(str(path), 'w') as f:
        f.write(manifest.model_dump_json())


if __name__ == '__main__':
    main()
