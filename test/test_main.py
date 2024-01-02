from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from zaphodvox.main import main
from zaphodvox.parser import parse_args


class TestMain():
    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.tempfile.TemporaryDirectory')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        *args
    ):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        mock_segments = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segments
        mock_audio_segment.from_file.return_value = mock_segments
        mock_segments.__add__.return_value = mock_segments
        mock_segments.__iadd__.return_value = mock_segments

        main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_t2s.assert_called_once()
        mock_segments.export.assert_called_once()
        mock_copy.assert_called_once()

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.main.tempfile.TemporaryDirectory')
    @patch('zaphodvox.elevenlabs.encoder.ELVoice')
    @patch('zaphodvox.elevenlabs.encoder.save')
    @patch('zaphodvox.elevenlabs.encoder.generate')
    @patch('zaphodvox.elevenlabs.encoder.History')
    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.elevenlabs.encoder.ElevenLabsEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main_elevenlabs(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        mock_voice_settings_from_voice_id, *args
    ):
        sys_args = [
            '--encoder=elevenlabs',
            '--voice-id=TxGEqnHWrfWFTfGW9XjX',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        mock_voice_settings_from_voice_id.return_value = MagicMock()
        mock_segments = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segments
        mock_audio_segment.from_file.return_value = mock_segments
        mock_segments.__add__.return_value = mock_segments
        mock_segments.__iadd__.return_value = mock_segments

        main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_t2s.assert_called_once()
        mock_segments.export.assert_called_once()
        mock_copy.assert_called_once()

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.tempfile.TemporaryDirectory')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main_concat_exception(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        *args
    ):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        mock_segments = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segments
        mock_segments.__add__.return_value = mock_segments
        mock_audio_segment.from_file.side_effect = Exception('from_file error')

        with pytest.raises(Exception):
            main(sys_args)

        mock_t2s.assert_called_once()
        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        assert not mock_segments.export.called
        mock_copy.assert_called_once()

    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_nothing_to_do(self, *args):
        sys_args = ['test.txt']

        with pytest.raises(SystemExit) as se:
            main(raw_args=sys_args)

        assert se.value.code == 0

    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_no_encoder(self, *args):
        sys_args = ['--encoder=google', '--encode', 'test.txt']
        args = parse_args(sys_args)
        args.encoder = 'NotARealEncoder'

        with pytest.raises(ValueError):
            main(preparsed_args=args)

    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_clean(self, mock_builtins_open, *args):
        sys_args = ['--clean', 'test.txt']

        main(sys_args)

        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        mock_builtins_open().write.assert_called_once_with('Hello, world!\n\n')

    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_clean_max_chars(self, mock_builtins_open, *args):
        sys_args = ['--clean', '--max-chars=7', 'test.txt']

        main(sys_args)

        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        mock_builtins_open().write.assert_called_once_with(
            'Hello,\n\nworld!\n\n'
        )
