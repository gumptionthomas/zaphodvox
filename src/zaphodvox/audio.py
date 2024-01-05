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
    AudioSegment.silent(duration=duration).export(str(filepath), format=format)


def concat_files(
    audio_dir: Path,
    manifest: Manifest,
    format: str,
    output_filepath: Path
) -> None:
    """Concatenates fragment audio files together and exports the result
    to a specified output file.

    Args:
        audio_dir: The directory `Path` containing the fragment audio files.
        manifest: The `Manifest` containing the fragment audio files to
            concatenate.
        format: The format of the fragment audio files.
        output_filepath: The `Path` to the output file where the
            concatenated audio will be saved.
    """
    filepaths = [
        audio_dir.joinpath(fragment.filename)
        for fragment in manifest.fragments if fragment.filename
    ]
    with ProgressBar('Concat', total=len(filepaths)) as bar:
        segments: AudioSegment = AudioSegment.empty()
        for filepath in filepaths:
            segments += AudioSegment.from_file(
                str(audio_dir.joinpath(filepath)),
                format=format
            )
            bar.next()
        segments.export(str(output_filepath), format=format)


def copy_files(audio_dir: Path, manifest: Manifest, copy_path: Path) -> None:
    """Copies the encoded files from the audio directory to the current
    working directory.

    Args:
        audio_dir: The directory `Path` containing the fragment audio files.
        manifest: The `Manifest` containing the fragment audio files to copy.
        copy_path: The `Path` to the directory where the fragment audio files
            will be copied.
    """
    filepaths = [
        audio_dir.joinpath(fragment.filename)
        for fragment in manifest.fragments if fragment.filename
    ]
    with ProgressBar('Copy', total=len(filepaths)) as bar:
        for filepath in filepaths:
            if filepath.exists():
                shutil.copy(str(filepath), str(copy_path))
            bar.next()
