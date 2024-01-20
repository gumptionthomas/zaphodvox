import json
from unittest.mock import mock_open, patch

from pathlib import Path

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.main import read_voices
from zaphodvox.googlecloud.voice import GoogleVoice


class TestLoadNamedVoices():
    @patch(
        'builtins.open',
        new_callable=mock_open,
        read_data = json.dumps({
            'voices': {
                'voice_1': {
                    'google': {
                        'voice_id': 'A',
                        'language': 'en',
                        'region': 'US',
                        'type': 'Wavenet'
                    },
                    'elevenlabs': {'voice_id': 'Josh'}
                },
                'voice_2': {
                    'elevenlabs': {
                        'voice_id': 'Adam',
                        'model': 'multilingual_v2'
                    }
                }
            }
        })
    )
    def test_parse_voices_elevenlabs(self, mock_builtins_open, *args):
        filepath = Path('/path/to/voices.json')

        voices = read_voices(filepath)

        mock_builtins_open.assert_called_once_with(str(filepath), 'r')
        encoder_voices = voices.encoder_voices('elevenlabs')
        assert encoder_voices == {
            'voice_1': ElevenLabsVoice(voice_id='Josh'),
            'voice_2': ElevenLabsVoice(voice_id='Adam', model='multilingual_v2')
        }

    @patch(
        'builtins.open',
        new_callable=mock_open,
        read_data = json.dumps({
            'voices': {
                'voice_1': {
                    'google': {
                        'voice_id': 'A',
                        'language': 'en',
                        'region': 'US',
                        'type': 'Wavenet'
                    },
                    'elevenlabs': {'voice_id': 'Josh'}
                },
                'voice_2': {
                    'elevenlabs': {'voice_id': 'Adam'}
                }
            }
        })
    )
    def test_parse_voices_google(self, mock_builtins_open):
        filepath = Path('/path/to/voices.json')

        voices = read_voices(filepath)

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
