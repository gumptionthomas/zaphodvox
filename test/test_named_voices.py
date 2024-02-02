from unittest.mock import mock_open

from pathlib import Path

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.main import read_voices
from zaphodvox.googlecloud.voice import GoogleVoice


class TestLoadNamedVoices():
    def test_parse_voices_elevenlabs(
        self, mock_builtins_open, voices_json_data
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
            'voice_1': ElevenLabsVoice(voice_id='Ford'),
            'voice_2': ElevenLabsVoice(
                voice_id='Arthur', model='eleven_multilingual_v2'
            )
        }

    def test_parse_voices_google(self, mock_builtins_open, voices_json_data):
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
            'voice_1': GoogleVoice(
                voice_id='A',
                language='en',
                region='US',
                type='Wavenet'
            ),
            'voice_2': None
        }
