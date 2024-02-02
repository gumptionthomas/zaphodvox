import sys
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from rich.console import Console

from zaphodvox import __version__
from zaphodvox.audio import concat_files, copy_files
from zaphodvox.encoder import Encoder
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
    console = Console(highlight=False)
    handle_version_and_ntd(args, console)
    try:
        validate(args)
        if not args.basename and args.inputfile:
            args.basename = args.inputfile.stem
        args.parent_dir = None
        if args.inputfile:
            args.parent_dir = Path(args.inputfile.parent)
        args.copy_dir = args.copy_dir or Path.cwd()
        args.encoder, args.voice = encoder_voice(args)
        text, manifest = read_text_manifest(args.inputfile)
        args.named_voices = read_voices(args.voices_file, manifest)
        plan_manifest = clean_plan(args, text, manifest)
        args.indexes = args.indexes if manifest else None
        if manifest:
            args.encode_dir = args.encode_dir or args.parent_dir
        if args.encode_dir and args.copy_dir.samefile(args.encode_dir):
            args.copy_dir = None
        encode_concat_copy(args, plan_manifest)
        if args.delete_history:
            if delete := getattr(args.encoder, 'delete_history', None):
                delete()
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
    copy: bool = args.copy
    delete_history: bool = args.delete_history

    if args.version:
        console.print(f'{Path(sys.argv[0]).stem}, version {__version__}')
        sys.exit(0)
    if not any([clean, plan, encode, concat, copy, delete_history]):
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
    delete_history: bool = args.delete_history
    encoder_name: Optional[str] = args.encoder_name
    encode: bool = args.encode

    if not (inputfile or delete_history):
        raise ValueError('No input file specified.')
    if delete_history and encoder_name != 'elevenlabs':
        raise ValueError(
            'The "elevenlabs" encoder must be specified to delete history.'
        )
    if encode and not encoder_name:
        raise ValueError('No encoder specified.')


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
    voice_name: Optional[str] = args.voice_name

    if clean and not manifest:
        text = clean_text(text, max_chars=max_chars)
        filename = f'{basename}-clean.txt'
        clean_out = file_path(clean_out, filename, parent_dir)
        write_cleaned(text, clean_out)
    plan_manifest = None
    if plan or encode:
        encoder_voices = named_voices.encoder_voices(encoder_name)
        if not voice and voice_name:
            voice = encoder_voices.get(voice_name)
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
        file_ext = file_extension(manifest, encoder)
        plan_manifest = Manifest.plan(
            fragments, basename, file_ext, silence_duration=silence_duration
        )
        plan_manifest.set_used_voices(named_voices.voices)
        if plan:
            filename = f'{basename}-plan.json'
            plan_out = file_path(plan_out, filename, parent_dir)
            write_manifest(plan_manifest, plan_out)
    plan_manifest = plan_manifest or manifest or Manifest()
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
    encode: bool = args.encode
    encoder: Encoder = args.encoder
    encoder_name: str = args.encoder_name
    encode_dir: Optional[Path] = args.encode_dir
    indexes: Optional[list[int]] = args.indexes
    manifest_out: Optional[Path] = args.manifest_out
    named_voices: NamedVoices = args.named_voices
    silence_duration: Optional[int] = args.silence_duration
    save_manifest: bool = args.save_manifest

    with TemporaryDirectory() as temp_pathname:
        encoding_dir = encode_dir or Path(temp_pathname)
        dest_dir = copy_dir or encoding_dir
        encoder_voices = named_voices.encoder_voices(encoder_name)
        try:
            if encode:
                manifest = encoder.encode_manifest(
                    manifest,
                    encoding_dir,
                    indexes=indexes,
                    voices=encoder_voices,
                    silence_duration=silence_duration
                )
                manifest.set_used_voices(named_voices.voices)
                if save_manifest:
                    filename = f'{basename}-manifest.json'
                    manifest_out = file_path(manifest_out, filename, dest_dir)
                    write_manifest(manifest, manifest_out)
            if concat:
                file_ext = file_extension(manifest, encoder)
                filename = f'{basename}.{file_ext}'
                concat_out = file_path(concat_out, filename, dest_dir)
                concat_files(encoding_dir, manifest, file_ext, concat_out)
            if (copy or (encode and not concat)) and copy_dir:
                copy_files(encoding_dir, manifest, copy_dir)
        except Exception:
            if copy_dir:
                copy_files(encoding_dir, manifest, copy_dir)
            raise


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


def file_path(
    path: Optional[Path], filename: str, default_dir: Path
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
            directory, the directory joined with the specified filename.
            Otherwise the default directory joined with the specified filename.
    """
    if path and path.is_dir():
        path = path / filename
    if not path:
        path = default_dir / filename
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
