import shutil
from pathlib import Path

from pydub import AudioSegment

from zaphodvox.manifest import Manifest
from zaphodvox.progress import ProgressBar


def create_silence(duration: int, filepath: Path, format: str) -> None:
    """Creates a silent audio segment and exports it to a specified file.

    Args:
        duration: The duration of the silent audio segment in milliseconds.
        filepath: The `Path` to the output file where the silent audio
            segment will be exported.
        format: The format of the silent audio segment export.
    """
    AudioSegment.silent(duration=duration).export(filepath, format=format)


def concat_files(
    audio_path: Path,
    manifest: Manifest,
    format: str,
    output_filepath: Path
) -> None:
    """Concatenates audio segments together and exports the result to a
    specified output file.

    Args:
        audio_path: The directory `Path` containing the audio segments.
        manifest: The `Manifest` containing the audio segments to
            concatenate.
        format: The format of the audio segments.
        output_filepath: The `Path` to the output file where the
            concatenated audio will be saved.
    """
    filepaths = [
        audio_path.joinpath(audio_file.filename)
        for audio_file in manifest.speech_audio_files
    ]
    filepaths.sort()
    with ProgressBar('Concat', total=len(filepaths)) as bar:
        segments: AudioSegment = AudioSegment.empty()
        for filepath in filepaths:
            segments += AudioSegment.from_file(
                str(audio_path.joinpath(filepath)),
                format=format
            )
            bar.next()
        segments.export(str(output_filepath), format=format)


def copy_files(audio_path: Path, manifest: Manifest) -> None:
    """Copies the encoded files from the audio directory to the current
    working directory.

    Args:
        audio_path: The directory `Path` containing the audio files.
        manifest: The `Manifest` containing the audio files to copy.
    """
    filepaths = [
        audio_path.joinpath(audio_file.filename)
        for audio_file in manifest.speech_audio_files
    ]
    with ProgressBar('Copy', total=len(filepaths)) as bar:
        for filepath in filepaths:
            shutil.copy(str(filepath), str(Path.cwd()))
            bar.next()
