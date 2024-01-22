from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.parser import parse_args


class TestElevenLabsVoice():
    def test_eq(self, elevenlabs_voice):
        other_voice = elevenlabs_voice.model_copy()
        assert elevenlabs_voice == other_voice

    def test_neq(self, elevenlabs_voice, google_voice):
        other_voice = elevenlabs_voice.model_copy()
        other_voice.voice_id = 'Arthur'
        assert elevenlabs_voice != other_voice
        assert elevenlabs_voice != google_voice

    def test_get_settings(self, mock_elevenlabs):
        # Setup
        mock_settings = MagicMock()
        mock_settings.stability = 0.0
        mock_settings.similarity_boost = 0.0
        mock_settings.style = 0.0
        mock_settings.use_speaker_boost = False
        mock_elevenlabs.from_voice_id.return_value = mock_settings

        # Run
        voice = ElevenLabsVoice(
            voice_id='Josh', stability=0.1, similarity_boost=0.2, style=0.3,
            use_speaker_boost=True
        )
        settings = voice.voice_settings

        # Verify
        mock_elevenlabs.from_voice_id.assert_called_once_with('Josh')
        assert settings.stability == 0.1
        assert settings.similarity_boost == 0.2
        assert settings.style == 0.3
        assert settings.use_speaker_boost


class TestElevenLabsEncoder():
    def test_t2s(self, text_to_encode, elevenlabs_voice, mock_elevenlabs):
        # Setup
        filepath = Path('/path/to/output.wav')
        encoder = ElevenLabsEncoder()

        # Run
        encoder.t2s(text_to_encode, elevenlabs_voice, filepath)

        # Verify
        mock_elevenlabs.from_voice_id.assert_called_once_with(
            elevenlabs_voice.voice_id
        )
        mock_elevenlabs.elvoice.assert_called_once_with(
            voice_id=elevenlabs_voice.voice_id,
            settings=mock_elevenlabs.from_voice_id.return_value
        )
        mock_elevenlabs.generate.assert_called_once_with(
            text=text_to_encode,
            voice=mock_elevenlabs.elvoice.return_value,
            output_format=encoder.audio_format,
            model=elevenlabs_voice.model
        )
        mock_elevenlabs.save.assert_called_once_with(
            mock_elevenlabs.generate.return_value, str(filepath)
        )

    def test_delete_history(self, mock_elevenlabs):
        # Setup
        mock_history_item = MagicMock()
        mock_elevenlabs.history.from_api.return_value = [mock_history_item]

        # Run
        ElevenLabsEncoder().delete_history()

        # Verify
        mock_elevenlabs.history.from_api.assert_called_once_with()
        mock_history_item.delete.assert_called_once_with()

    @patch('zaphodvox.elevenlabs.encoder.set_api_key')
    def test_from_args(self, set_api_key, elevenlabs_voice):
        # Setup
        args = parse_args([
            '--api-key=1234',
            f'--voice-id={elevenlabs_voice.voice_id}',
            'test.txt'
        ])

        # Run
        encoder, voice = ElevenLabsEncoder.from_args(args)

        # Verify
        set_api_key.assert_called_once_with('1234')
        assert isinstance(encoder, ElevenLabsEncoder)
        assert voice.voice_id == elevenlabs_voice.voice_id

    def test_t2s_wrong_voice(self):
        # Setup
        elevenlabs_encoder = ElevenLabsEncoder()
        text = "Hello, world!"
        voice = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        filepath = Path('/path/to/output.wav')

        # Run
        with pytest.raises(ValueError) as ve:
            elevenlabs_encoder.t2s(text, voice, filepath)

        # Verify
        assert str(ve.value) == 'Not an ElevenLabsVoice.'

    def test_invalid_audio_format(self):
        with pytest.raises(ValueError):
            encoder = ElevenLabsEncoder(audio_format='invalid_audio_format')
            _ = encoder.file_extension

    def test_file_extension(self):
        encoder = ElevenLabsEncoder()
        assert encoder.file_extension == 'mp3'
        encoder = ElevenLabsEncoder(audio_format='pcm_44100')
        assert encoder.file_extension == 'wav'
