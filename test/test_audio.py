from pathlib import Path
from unittest.mock import call, patch

from zaphodvox.audio import concat_files
from zaphodvox.manifest import Fragment, Manifest


class TestConcat():
    @patch('zaphodvox.audio.ProgressBar')
    def test_concat(self, mock_progress_bar, mock_audio):
        # Setup
        audio_path = Path('/path/to/audio')
        filenames = [f'audio-file-0000{i}.wav' for i in range(3)]
        output_filepath = Path('/path/to/output.wav')
        fragments = [
            Fragment(filename=f, text=str(f)) for f in filenames
        ]
        manifest = Manifest(fragments=fragments)
        mock_audio_segment_cls, mock_audio_segment = mock_audio

        # Run
        concat_files(audio_path, manifest, 'wav', output_filepath)

        # Verify
        mock_progress_bar.assert_called_once_with(
            'Concat', total=len(filenames)+1
        )
        mock_audio_segment_cls.empty.assert_called_once()
        expected_calls = [
            call(str(audio_path / f), format='wav') for f in filenames
        ]
        mock_audio_segment_cls.from_file.assert_has_calls(expected_calls)
        mock_audio_segment.export.assert_called_once_with(
            str(output_filepath), format='wav'
        )
