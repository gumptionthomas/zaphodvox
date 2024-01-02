import json
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.parser import parse_voices, parse_args


class TestArgParser():
    def test_defaults(self):
        args = parse_args(['test.txt'])

        # General
        assert args.textfile == Path('test.txt')
        assert args.encoder == 'google'
        assert args.voices is None
        assert args.voice_id is None
        assert args.max_chars is None
        assert args.silence_duration == 500
        assert args.basename is None
        assert not args.clean
        assert not args.encode
        assert not args.copy
        assert not args.concat
        assert args.concat_out is None
        assert args.manifest is True
        assert args.manifest_out is None
        assert not args.delete_history
        # Google
        assert args.voice_language == 'en'
        assert args.voice_region == 'US'
        assert args.voice_type == 'Wavenet'
        assert args.voice_speaking_rate is None
        assert args.voice_pitch is None
        assert args.voice_volume_gain_db is None
        assert args.voice_sample_rate_hertz is None
        assert args.voice_effects_profile_id is None
        assert args.google_audio_format == 'linear16'
        assert args.service_account is None
        # ElevenLabs
        assert args.voice_model == 'multilingual_v2'
        assert args.voice_stability is None
        assert args.voice_similarity_boost is None
        assert args.voice_style is None
        assert args.voice_use_speaker_boost is None
        assert args.elevenlabs_audio_format == 'mp3_44100_128'
        assert args.api_key is None

    def test_parser_scalar(self):
        sys_args = [
            '--voice-stability=0.5',
            'test.txt'
        ]
        args = parse_args(sys_args)
        assert args.voice_stability == 0.5

    def test_parser_large_scalar(self):
        sys_args = [
            '--voice-stability=42.42',
            'test.txt'
        ]
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(sys_args)

    def test_parser_small_scalar(self):
        sys_args = [
            '--voice-stability=-42.42',
            'test.txt'
        ]
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(sys_args)


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

        voices = parse_voices(ElevenLabsEncoder(), filepath)

        mock_builtins_open.assert_called_once_with(str(filepath), 'r')
        assert voices == {
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
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    def test_parse_voices_google(self, mock_t2s_client, mock_builtins_open):
        filepath = Path('/path/to/voices.json')
        service_account_filepath = Path('/path/to/service_account.json')
        google_encoder = GoogleEncoder(
            service_account_filepath=service_account_filepath
        )
        mock_t2s_client.from_service_account_file.assert_called_once_with(
            str(service_account_filepath)
        )

        voices = parse_voices(google_encoder, filepath)

        mock_builtins_open.assert_called_once_with(str(filepath), 'r')
        assert voices == {
            'voice_1': GoogleVoice(
                voice_id='A',
                language='en',
                region='US',
                type='Wavenet'
            ),
            'voice_2': None
        }
