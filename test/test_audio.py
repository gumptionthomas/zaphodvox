import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from zaphodvox.audio import (
    DEFAULT_PARAMS,
    AudioParams,
    audio_params,
    concat_files,
    create_silence,
)
from zaphodvox.manifest import Fragment, Manifest

SPEECH = AudioParams(channels=1, sample_width=2, frame_rate=24000)
"""What the Qwen3-TTS server returns."""

LEGACY_SILENCE = AudioParams(channels=1, sample_width=2, frame_rate=11025)
"""What silence used to be written as: pydub's default, which does not match the
speech it sits between."""


def write_wav(
    filepath: Path, params: AudioParams, ms: int, value: int = 0
) -> None:
    """Writes a `wav` file of a given length and sample format."""
    frames = int(params.frame_rate * ms / 1000)
    sample = value.to_bytes(params.sample_width, 'little', signed=True)
    with wave.open(str(filepath), 'wb') as w:
        w.setnchannels(params.channels)
        w.setsampwidth(params.sample_width)
        w.setframerate(params.frame_rate)
        w.writeframes(sample * frames * params.channels)


def read_wav(filepath: Path) -> tuple[AudioParams, float]:
    """Reads back a `wav` file's sample format and duration in seconds."""
    with wave.open(str(filepath), 'rb') as w:
        params = AudioParams(
            channels=w.getnchannels(),
            sample_width=w.getsampwidth(),
            frame_rate=w.getframerate(),
        )
        return params, w.getnframes() / w.getframerate()


class TestAudioParams():
    def test_reads_a_wav_header(self, tmp_path):
        filepath = tmp_path / 'a.wav'
        write_wav(filepath, SPEECH, 100)

        assert audio_params(filepath) == SPEECH

    def test_unreadable_file_is_none(self, tmp_path):
        filepath = tmp_path / 'not-audio.wav'
        filepath.write_text('this is not a wav file', encoding='utf-8')

        assert audio_params(filepath) is None


class TestCreateSilence():
    def test_silence_matches_the_given_sample_format(self, tmp_path):
        # The whole point: silence has to agree with the speech around it, or
        # the book cannot be concatenated without resampling every fragment.
        filepath = tmp_path / 'silence.wav'

        create_silence(500, filepath, 'wav', SPEECH)

        params, seconds = read_wav(filepath)
        assert params == SPEECH
        assert seconds == pytest.approx(0.5)

    def test_silence_is_actually_silent(self, tmp_path):
        filepath = tmp_path / 'silence.wav'

        create_silence(100, filepath, 'wav', SPEECH)

        with wave.open(str(filepath), 'rb') as w:
            assert set(w.readframes(w.getnframes())) == {0}

    def test_silence_falls_back_to_the_default_format(self, tmp_path):
        # A manifest with no speech to copy a format from.
        filepath = tmp_path / 'silence.wav'

        create_silence(100, filepath, 'wav', None)

        params, _ = read_wav(filepath)
        assert params == DEFAULT_PARAMS

    def test_encoded_silence_is_exported_with_the_given_format(
        self, tmp_path, mock_audio
    ):
        # mp3 has to go through an encoder; only wav can be written directly.
        segment_cls, segment = mock_audio

        create_silence(100, tmp_path / 'silence.mp3', 'mp3', SPEECH)

        segment_cls.silent.assert_called_once_with(
            duration=100, frame_rate=SPEECH.frame_rate
        )
        segment.set_channels.assert_called_once_with(SPEECH.channels)


class TestConcatWav():
    def _manifest(self, filenames: list[str]) -> Manifest:
        return Manifest(fragments=[
            Fragment(filename=f, text='x') for f in filenames
        ])

    def test_concatenates_by_copying_samples(
        self, tmp_path, mock_progress_bar
    ):
        # Setup: three one-second fragments, all in the same sample format.
        for i in range(3):
            write_wav(tmp_path / f'f-{i}.wav', SPEECH, 1000, value=i + 1)
        manifest = self._manifest([f'f-{i}.wav' for i in range(3)])
        out = tmp_path / 'book.wav'

        # Run
        concat_files(tmp_path, manifest, 'wav', out)

        # Verify: the samples arrive in order, untouched.
        params, seconds = read_wav(out)
        assert params == SPEECH
        assert seconds == pytest.approx(3.0)
        with wave.open(str(out), 'rb') as w:
            frames = w.readframes(w.getnframes())
        third = len(frames) // 3
        assert frames[:third] == (1).to_bytes(2, 'little') * 24000
        assert frames[third:2 * third] == (2).to_bytes(2, 'little') * 24000

    def test_converts_a_fragment_in_a_different_format(
        self, tmp_path, mock_progress_bar
    ):
        # Setup: a book encoded before silence matched the speech -- the fix
        # cannot break the fragments people already have on disk.
        write_wav(tmp_path / 'f-0.wav', SPEECH, 1000)
        write_wav(tmp_path / 'f-1.wav', LEGACY_SILENCE, 1000)
        write_wav(tmp_path / 'f-2.wav', SPEECH, 1000)
        manifest = self._manifest(['f-0.wav', 'f-1.wav', 'f-2.wav'])
        out = tmp_path / 'book.wav'

        # Run
        concat_files(tmp_path, manifest, 'wav', out)

        # Verify: the odd fragment is resampled rather than spliced in at the
        # wrong rate, which would have played it at the wrong speed.
        params, seconds = read_wav(out)
        assert params == SPEECH
        assert seconds == pytest.approx(3.0, abs=0.01)

    def test_skips_an_unreadable_fragment(self, tmp_path, mock_progress_bar):
        # Setup
        write_wav(tmp_path / 'f-0.wav', SPEECH, 1000)
        (tmp_path / 'f-1.wav').write_text('not audio', encoding='utf-8')
        write_wav(tmp_path / 'f-2.wav', SPEECH, 1000)
        manifest = self._manifest(['f-0.wav', 'f-1.wav', 'f-2.wav'])
        out = tmp_path / 'book.wav'

        # Run
        concat_files(tmp_path, manifest, 'wav', out)

        # Verify: the rest of the book still gets made.
        _, seconds = read_wav(out)
        assert seconds == pytest.approx(2.0)


class TestConcatEncoded():
    def test_mp3_is_concatenated_in_one_ffmpeg_pass(
        self, tmp_path, mock_progress_bar
    ):
        # Setup: decoding and re-encoding once, in one process, rather than
        # spawning ffmpeg per fragment.
        filenames = [f'f-{i}.mp3' for i in range(3)]
        for f in filenames:
            (tmp_path / f).write_bytes(b'ID3fake')
        manifest = Manifest(fragments=[
            Fragment(filename=f, text='x') for f in filenames
        ])
        out = tmp_path / 'book.mp3'
        listed = []

        def capture(cmd, **kwargs):
            listfile = Path(cmd[cmd.index('-i') + 1])
            listed.append(listfile.read_text(encoding='utf-8'))
            return None

        # Run
        with patch('zaphodvox.audio.subprocess.run', side_effect=capture) as run:
            concat_files(tmp_path, manifest, 'mp3', out)

        # Verify
        assert run.call_count == 1
        cmd = run.call_args.args[0]
        assert '-f' in cmd and 'concat' in cmd
        assert str(out) == cmd[-1]
        # Every fragment, in order, is handed to the one ffmpeg call.
        for f in filenames:
            assert str((tmp_path / f).resolve().as_posix()) in listed[0]
