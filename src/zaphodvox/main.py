import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from typing import Optional

from zaphodvox.audio import concat_files, copy_files
from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.parser import parse_args, parse_voices
from zaphodvox.text import clean_text
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
    if not args.clean and not args.encode and not args.delete_history:
        sys.exit(0)
    with open(str(args.textfile), 'r') as file:
        text = file.read()
    basename = args.basename or args.textfile.stem
    if args.clean:
        text = clean_text(text, max_chars=args.max_chars)
        clean_out = args.clean_out or f'{basename}-clean.txt'
        with open(clean_out, 'w') as clean_file:
            clean_file.write(text)
    encoder: Optional[GoogleEncoder | ElevenLabsEncoder] = None
    voice: Optional[Voice] = None
    if args.encoder:
        if args.encoder == 'google':
            encoder, voice = GoogleEncoder.from_args(args)
        if args.encoder == 'elevenlabs':
            encoder, voice = ElevenLabsEncoder.from_args(args)
        if not encoder:
            raise ValueError(f'Encoder "{args.encoder}" not found.')
    if args.encode and encoder:
        voices = parse_voices(encoder, args.voices) if args.voices else None
        file_ext = encoder.file_extension
        with tempfile.TemporaryDirectory() as temp_pathname:
            try:
                temp_path = Path(temp_pathname)
                manifest = encoder.encode(
                    text, basename, temp_path,
                    voice=voice,
                    voices=voices,
                    max_chars=args.max_chars,
                    silence_duration=args.silence_duration
                )
                for speech_audio_file in manifest.speech_audio_files:
                    speech_audio_file.encoder = args.encoder
                    speech_audio_file.audio_format = encoder.audio_format
                manifest_out = (
                    args.manifest_out or f'{basename}-manifest.json'
                )
                with open(manifest_out, 'w') as f:
                    f.write(manifest.model_dump_json())
                if args.concat:
                    concat_files(
                        temp_path, manifest, file_ext,
                        args.concat_out or Path(f'{basename}.{file_ext}')
                    )
                if args.copy or not args.concat:
                    copy_files(temp_path, manifest)
            except Exception:
                copy_files(temp_path, manifest)
                raise
    if args.delete_history and encoder:
        if isinstance(encoder, ElevenLabsEncoder):
            encoder.delete_history()

if __name__ == '__main__':
    main()
