import subprocess
import wave
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple, Optional

from pydub import AudioSegment

from zaphodvox.manifest import Manifest
from zaphodvox.progress import ProgressBar


class AudioParams(NamedTuple):
    """The sample format of an audio file. Files must agree on all three to be
    concatenated without resampling.
    """

    channels: int
    sample_width: int
    frame_rate: int


DEFAULT_PARAMS = AudioParams(channels=1, sample_width=2, frame_rate=24000)
"""The sample format to fall back on when there is no encoded speech to copy it
from (a manifest that is nothing but silence). Matches what Qwen3-TTS returns."""

_CHUNK_FRAMES = 1 << 14
"""How many frames to move at a time when copying audio, so that a long book is
never held in memory all at once."""


def audio_params(filepath: Path) -> Optional[AudioParams]:
    """Reads the sample format of an audio file.

    Args:
        filepath: The `Path` of the audio file.

    Returns:
        The file's `AudioParams`, or `None` if it cannot be read.
    """
    try:
        with wave.open(str(filepath), 'rb') as w:
            return AudioParams(
                channels=w.getnchannels(),
                sample_width=w.getsampwidth(),
                frame_rate=w.getframerate(),
            )
    except (OSError, wave.Error):
        pass
    try:
        segment = AudioSegment.from_file(str(filepath))
    except Exception:
        return None
    return AudioParams(
        channels=segment.channels,
        sample_width=segment.sample_width,
        frame_rate=segment.frame_rate,
    )


def create_silence(
    duration: int, filepath: Path, format: str,
    params: Optional[AudioParams] = None
) -> None:
    """Creates a silent audio file and exports it to a specified file.

    The silence is written in the same sample format as the speech it will sit
    between. That is not a detail: concatenation can only copy audio through
    untouched if every fragment agrees on the format, and silence that disagrees
    would force the whole book to be decoded and resampled.

    A silent `wav` is written directly, without `pydub` or `ffmpeg` -- silence is
    just zeroed samples, and there is nothing to encode.

    Args:
        duration: The duration of the silent audio in milliseconds.
        filepath: The `Path` to the output file.
        format: The format of the silent audio export.
        params: The `AudioParams` to write the silence in. Defaults to `None`
            (`DEFAULT_PARAMS`).
    """
    params = params or DEFAULT_PARAMS
    if format == 'wav':
        frames = int(params.frame_rate * duration / 1000)
        with wave.open(str(filepath), 'wb') as w:
            w.setnchannels(params.channels)
            w.setsampwidth(params.sample_width)
            w.setframerate(params.frame_rate)
            w.writeframes(
                bytes(frames * params.sample_width * params.channels)
            )
        return
    silence = AudioSegment.silent(
        duration=duration, frame_rate=params.frame_rate
    )
    silence = silence.set_channels(params.channels)
    silence = silence.set_sample_width(params.sample_width)
    silence.export(str(filepath), format=format)


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

    Raises:
        FileNotFoundError: If any fragment's audio file is missing.
    """
    filepaths = [
        audio_dir / fragment.filename
        for fragment in manifest.fragments if fragment.filename
    ]
    speech = [
        audio_dir / fragment.filename
        for fragment in manifest.fragments
        if fragment.filename and fragment.text
    ]
    # A fragment that was never encoded -- an interrupted `--encode` -- is a
    # hole in the book, not something to work around. Concatenating what is
    # there would hand back a finished-looking audiobook with the missing
    # fragments silently dropped out of it.
    if missing := [f for f in filepaths if not f.is_file()]:
        listed = ', '.join(f.name for f in missing[:5])
        if len(missing) > 5:
            listed += f', and {len(missing) - 5} more'
        raise FileNotFoundError(
            f'{len(missing)} fragment(s) have no audio file: {listed}. '
            'Re-encode them (--encode --indexes ...) before concatenating.'
        )
    if format == 'wav':
        _concat_wav(filepaths, speech, output_filepath)
    else:
        _concat_encoded(filepaths, output_filepath, format)


def _concat_wav(
    filepaths: list[Path], speech: list[Path], output_filepath: Path
) -> None:
    """Concatenates `wav` files by copying their samples straight through.

    Nothing is decoded, re-encoded or held in memory: the frames of each
    fragment are appended to the output as they are read. A fragment whose
    sample format differs from the rest (an older silence file, say) is the one
    case that has to be converted, and only that fragment is.

    Args:
        filepaths: The `Path`s of the audio files to concatenate, in order.
        speech: The `Path`s of the fragments that are speech rather than
            silence, whose sample format the output takes.
        output_filepath: The `Path` of the concatenated output file.
    """
    # Take the output format from the *speech*, never from a silent fragment: a
    # book encoded before silence matched the speech has 11 kHz silence in it,
    # and a book that opens with a blank line would otherwise be downsampled to
    # 11 kHz in its entirety -- correct length, ruined quality, no error.
    target = next(
        (p for p in (audio_params(f) for f in speech) if p),
        next(
            (p for p in (audio_params(f) for f in filepaths) if p),
            DEFAULT_PARAMS
        )
    )
    with ProgressBar('Concatinating', total=len(filepaths)) as bar:
        with wave.open(str(output_filepath), 'wb') as out:
            out.setnchannels(target.channels)
            out.setsampwidth(target.sample_width)
            out.setframerate(target.frame_rate)
            for filepath in filepaths:
                try:
                    _append_wav(filepath, out, target)
                except Exception as e:
                    bar.console.print(f'Skipping {filepath.name}: {e}')
                bar.next()


def _append_wav(
    filepath: Path, out: wave.Wave_write, target: AudioParams
) -> None:
    """Appends one audio file's samples to an open `wav` file.

    Args:
        filepath: The `Path` of the audio file to append.
        out: The open `wave.Wave_write` to append to.
        target: The `AudioParams` the output is being written in.

    Raises:
        Exception: If the file cannot be read.
    """
    try:
        with wave.open(str(filepath), 'rb') as w:
            if audio_params(filepath) == target:
                while frames := w.readframes(_CHUNK_FRAMES):
                    out.writeframes(frames)
                return
    except wave.Error:
        pass
    segment = AudioSegment.from_file(str(filepath))
    segment = segment.set_frame_rate(target.frame_rate)
    segment = segment.set_channels(target.channels)
    segment = segment.set_sample_width(target.sample_width)
    out.writeframes(segment.raw_data)


def _concat_encoded(
    filepaths: list[Path], output_filepath: Path, format: str
) -> None:
    """Concatenates encoded (e.g. `mp3`) files in a single `ffmpeg` pass.

    `ffmpeg`'s concat demuxer reads the fragments itself, so the audio is
    decoded and re-encoded exactly once, in one process -- rather than once per
    fragment. Stream-copying instead (`-c copy`) would be faster still, but each
    `mp3` carries its own encoder padding, which would add a small gap of
    silence at every fragment boundary.

    Args:
        filepaths: The `Path`s of the audio files to concatenate, in order.
        output_filepath: The `Path` of the concatenated output file.
        format: The format of the audio files.
    """
    with ProgressBar('Concatinating', total=None) as bar:
        with TemporaryDirectory() as tmp:
            listfile = Path(tmp) / 'concat.txt'
            listfile.write_text(
                ''.join(
                    f"file '{f.resolve().as_posix()}'\n"
                    for f in filepaths if f.is_file()
                ),
                encoding='utf-8'
            )
            subprocess.run(
                [
                    AudioSegment.converter, '-v', 'error', '-y',
                    '-f', 'concat', '-safe', '0', '-i', str(listfile),
                    '-f', format, str(output_filepath),
                ],
                check=True,
                capture_output=True,
            )
        bar.stop()
