from pathlib import Path

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
    def test_eq(self, google_voice):
        other_voice = google_voice.model_copy()
        assert google_voice == other_voice

    def test_neq(self, google_voice, elevenlabs_voice):
        other_voice = google_voice.model_copy()
        other_voice.voice_id = 'B'
        assert google_voice != other_voice
        assert google_voice != elevenlabs_voice


class TestGoogleEncoder():
    def test_t2s(self, text_to_encode, mock_builtins_open, mock_google):
        # Setup
        google_encoder = GoogleEncoder()
        voice = GoogleVoice(
            voice_id='A', language='en',
            region='US', type='Wavenet',
            speaking_rate=1.0, pitch=0.0, volume_gain_db=1.0,
            sample_rate_hertz=16000,
            effects_profile_id=['headphone-class-device']
        )
        filepath = Path('/path/to/output.wav')

        # Run
        google_encoder.t2s(text_to_encode, voice, filepath)

        # Verify
        mock_google.client_cls.assert_called_once_with()
        mock_builtins_open.assert_called_once_with(str(filepath), 'wb')
        mock_builtins_open().write.assert_called_once_with(
            mock_google.audio_content
        )
        mock_google.client.synthesize_speech.assert_called_once_with(
            request={
                'input': SynthesisInput(text=text_to_encode),
                'voice': VoiceSelectionParams(
                    language_code=f'{voice.language}-{voice.region}',
                    name=(
                        f'{voice.language}-{voice.region}-'
                        f'{voice.type}-{voice.voice_id}'
                    )
                ),
                'audio_config': AudioConfig(
                    audio_encoding=AudioEncoding.LINEAR16,
                    speaking_rate=voice.speaking_rate,
                    pitch=voice.pitch,
                    volume_gain_db=voice.volume_gain_db,
                    sample_rate_hertz=voice.sample_rate_hertz,
                    effects_profile_id=voice.effects_profile_id
                )
            }
        )

    def test_from_args(self, mock_google):
        # Setup
        args = parse_args([
            '--service-account=/path/to/service_account.json',
            '--voice-id=A',
            'test.txt'
        ])

        # Run
        encoder, voice = GoogleEncoder.from_args(args)

        # Verify
        mock_call = mock_google.client_cls.from_service_account_file
        mock_call.assert_called_once_with('/path/to/service_account.json')
        assert isinstance(encoder, GoogleEncoder)
        assert voice.voice_id == 'A'

    def test_invalid_audio_format(self, mock_google):
        # Run
        with pytest.raises(ValueError):
            encoder = GoogleEncoder(
                service_account_filepath=None,
                audio_format='invalid_audio_format'
            )
            _ = encoder._audio_encoding

        # Verify
        mock_google.client_cls.assert_called_once()
        mock_google.client_cls.reset_mock()

        # Run
        with pytest.raises(ValueError):
            encoder = GoogleEncoder(
                service_account_filepath=None,
                audio_format='invalid_audio_format'
            )
            _ = encoder.file_extension

        # Verify
        mock_google.client_cls.assert_called_once_with()

    def test_t2s_wrong_voice(self, mock_google):
        # Setup
        google_encoder = GoogleEncoder()
        text = "Hello, world!"
        voice = ElevenLabsVoice(voice_id='TxGEqnHWrfWFTfGW9XjX')
        filepath = Path('/path/to/output.wav')

        # Run
        with pytest.raises(ValueError) as ve:
            google_encoder.t2s(text, voice, filepath)

        # Verify
        mock_google.client_cls.assert_called_once_with()
        assert str(ve.value) == 'Not a GoogleVoice.'
