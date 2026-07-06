from unittest.mock import mock_open

from pathlib import Path

from zaphodvox.main import read_voices


class TestLoadNamedVoices():
    def test_parse_voices_elevenlabs(
        self, elevenlabs_voice, elevenlabs_voice_2, mock_builtins_open,
        voices_json_data
    ):
        # Setup
        mock_builtins_open.return_value = mock_open(
            read_data=voices_json_data
        ).return_value

        filepath = Path('/path/to/voices.json')

        # Run
        voices = read_voices(filepath, None)

        # Verify
        mock_builtins_open.assert_called_once_with(str(filepath), 'r')
        encoder_voices = voices.encoder_voices('elevenlabs')
        assert encoder_voices == {
            'voice_1': elevenlabs_voice,
            'voice_2': elevenlabs_voice_2
        }

    def test_parse_voices_google(
        self, google_voice, mock_builtins_open, voices_json_data
    ):
        # Setup
        mock_builtins_open.return_value = mock_open(
            read_data=voices_json_data
        ).return_value
        filepath = Path('/path/to/voices.json')

        # Run
        voices = read_voices(filepath, None)

        # Verify
        mock_builtins_open.assert_called_once_with(str(filepath), 'r')
        encoder_voices = voices.encoder_voices('google')
        assert encoder_voices == {
            'voice_1': google_voice,
            'voice_2': None
        }
