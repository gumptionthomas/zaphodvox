from pathlib import Path
from unittest.mock import call, patch

from zaphodvox.audio import concat_files
from zaphodvox.manifest import Fragment, Manifest


class TestConcat():
    @patch('zaphodvox.audio.ProgressBar')
    @patch('zaphodvox.audio.AudioSegment')
    def test_concat(self, mock_audio_segment, mock_progress_bar, *args):
        audio_path = Path('/path/to/audio')
        filenames = [f'audio-file-0000{i}.wav' for i in range(3)]
        output_filepath = Path('/path/to/output.wav')
        fragments = [
            Fragment(filename=f, text=str(f)) for f in filenames
        ]
        manifest = Manifest(fragments=fragments)
        mock_segments = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segments
        mock_audio_segment.from_file.return_value = mock_segments
        mock_segments.__add__.return_value = mock_segments
        mock_segments.__iadd__.return_value = mock_segments

        concat_files(audio_path, manifest, 'wav', output_filepath)

        mock_progress_bar.assert_called_once_with(
            'Concat', total=len(filenames)
        )
        mock_progress_bar.return_value.__enter__.assert_called_once()
        mock_progress_bar.return_value.__exit__.assert_called_once()
        mock_audio_segment.empty.assert_called_once()
        expected_calls = [
            call(str(audio_path.joinpath(f)), format='wav')
            for f in filenames
        ]
        mock_audio_segment.from_file.assert_has_calls(expected_calls)
        mock_segments.export.assert_called_once_with(
            str(output_filepath), format='wav'
        )
