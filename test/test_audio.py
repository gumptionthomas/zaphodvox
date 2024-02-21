from pathlib import Path
from unittest.mock import call

from zaphodvox.audio import concat_files
from zaphodvox.manifest import Fragment, Manifest


class TestConcat():
    def test_concat(self, mock_progress_bar, mock_audio):
        # Setup
        audio_path = Path('/path/to/audio')
        filenames = [f'audio-file-{i:05d}.wav' for i in range(3)]
        output_filepath = Path('/path/to/output.wav')
        manifest = Manifest(fragments=[
            Fragment(filename=f, text=str(f)) for f in filenames
        ])
        mock_audio_segment_cls, mock_audio_segment = mock_audio

        # Run
        concat_files(audio_path, manifest, 'wav', output_filepath)

        # Verify
        assert mock_progress_bar.audio.call_count == 2
        mock_progress_bar.audio.assert_any_call(
            'Concatinating', total=len(filenames)
        )
        mock_audio_segment_cls.empty.assert_called_once()
        assert mock_audio_segment_cls.from_file.call_count == len(filenames)
        mock_audio_segment_cls.from_file.assert_has_calls([
            call(str(audio_path / f), format='wav') for f in filenames
        ])
        mock_progress_bar.audio.assert_any_call('Exporting', total=None)
        mock_audio_segment.export.assert_called_once_with(
            str(output_filepath), format='wav'
        )
