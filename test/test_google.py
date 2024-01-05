from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from google.cloud.texttospeech import (
    AudioConfig,
    AudioEncoding,
    SynthesisInput,
    VoiceSelectionParams,
)
from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.parser import parse_args


class TestGoogleVoice():
    def test_eq(self):
        voice1 = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        voice2 = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        assert voice1 == voice2

    def test_neq(self):
        voice1 = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        voice2 = GoogleVoice(
            voice_id='B', language='en', region='US', type='Wavenet'
        )
        assert voice1 != voice2
        voice3 = ElevenLabsVoice(voice_id='Josh')
        assert voice1 != voice3


@patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
class TestGoogleEncoder():
    @patch('builtins.open', new_callable=mock_open)
    def test_t2s(self, mock_builtins_open, *args):
        google_encoder = GoogleEncoder()
        text = "Hello, world!"
        voice = GoogleVoice(
            voice_id='A', language='en',
            region='US', type='Wavenet',
            speaking_rate=1.0, pitch=0.0, volume_gain_db=1.0,
            sample_rate_hertz=16000,
            effects_profile_id=['headphone-class-device']
        )
        filepath = Path('/path/to/output.wav')
        synthesis_input = SynthesisInput(text=text)
        voice_params = VoiceSelectionParams(
            language_code=f'{voice.language}-{voice.region}',
            name=(
                f'{voice.language}-{voice.region}-'
                f'{voice.type}-{voice.voice_id}'
            )
        )
        audio_config = AudioConfig(
            audio_encoding=AudioEncoding.LINEAR16,
            speaking_rate=voice.speaking_rate,
            pitch=voice.pitch,
            volume_gain_db=voice.volume_gain_db,
            sample_rate_hertz=voice.sample_rate_hertz,
            effects_profile_id=voice.effects_profile_id
        )

        google_encoder.t2s(text, voice, filepath)

        mock_builtins_open.assert_called_once_with(str(filepath), 'wb')
        mock_builtins_open().write.assert_called_once()
        google_encoder._client.synthesize_speech.assert_called_once()
        google_encoder._client.synthesize_speech.assert_called_with(
            request={
                'input': synthesis_input,
                'voice': voice_params,
                'audio_config': audio_config
            }
        )

    def test_from_args(self, mock_t2s_client):
        args = parse_args([
            '--service-account=/path/to/service_account.json',
            '--voice-id=A',
            'test.txt'
        ])

        encoder, voice = GoogleEncoder.from_args(args)

        mock_t2s_client.from_service_account_file.assert_called_once_with(
            '/path/to/service_account.json'
        )
        assert isinstance(encoder, GoogleEncoder)
        assert voice.voice_id == 'A'

    def test_invalid_audio_format(self, mock_t2s_client):
        with pytest.raises(ValueError):
            encoder = GoogleEncoder(
                service_account_filepath=None,
                audio_format='invalid_audio_format'
            )
            _ = encoder._audio_encoding
        with pytest.raises(ValueError):
            encoder = GoogleEncoder(
                service_account_filepath=None,
                audio_format='invalid_audio_format'
            )
            _ = encoder.file_extension

    def test_t2s_wrong_voice(self, *args):
        google_encoder = GoogleEncoder()
        text = "Hello, world!"
        voice = ElevenLabsVoice(voice_id='TxGEqnHWrfWFTfGW9XjX')
        filepath = Path('/path/to/output.wav')

        with pytest.raises(ValueError) as ve:
            google_encoder.t2s(text, voice, filepath)
        assert str(ve.value) == 'Not a GoogleVoice.'
