from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.parser import parse_args


class TestElevenLabsVoice():
    def test_eq(self):
        voice1 = ElevenLabsVoice(
            voice_id='Josh', model='eleven_multilingual_v2'
        )
        voice2 = ElevenLabsVoice(
            voice_id='Josh', model='eleven_multilingual_v2'
        )
        assert voice1 == voice2

    def test_neq(self):
        voice1 = ElevenLabsVoice(
            voice_id='Josh', model='eleven_multilingual_v2'
        )
        voice2 = ElevenLabsVoice(
            voice_id='Bella', model='eleven_multilingual_v2'
        )
        assert voice1 != voice2
        voice3 = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        assert voice1 != voice3

    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    def test_get_settings(
        self, mock_voice_settings_from_voice_id, *args
    ):
        mock_settings = MagicMock()
        mock_settings.stability = 0.0
        mock_settings.similarity_boost = 0.0
        mock_settings.style = 0.0
        mock_settings.use_speaker_boost = False
        mock_voice_settings_from_voice_id.return_value = mock_settings

        voice = ElevenLabsVoice(
            voice_id='Josh', stability=0.1, similarity_boost=0.2, style=0.3,
            use_speaker_boost=True
        )
        settings = voice.voice_settings
        mock_voice_settings_from_voice_id.assert_called_once_with('Josh')
        assert settings.stability == 0.1
        assert settings.similarity_boost == 0.2
        assert settings.style == 0.3
        assert settings.use_speaker_boost


class TestElevenLabsEncoder():
    @patch('zaphodvox.elevenlabs.encoder.ELVoice')
    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    @patch('zaphodvox.elevenlabs.encoder.save')
    @patch('zaphodvox.elevenlabs.encoder.generate')
    def test_t2s(
        self, mock_generate, mock_save,
        mock_voice_settings_from_voice_id, *args
    ):
        mock_voice_settings_from_voice_id.return_value = MagicMock()
        text = "Hello, world!"
        voice = ElevenLabsVoice(voice_id='Josh', model='multilingual_v2')
        filepath = Path('/path/to/output.wav')

        ElevenLabsEncoder().t2s(text, voice, filepath)

        mock_generate.assert_called_once()
        mock_save.assert_called_once()

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.elevenlabs.encoder.History')
    def test_delete_history(self, mock_history, *args):
        mock_history_item = MagicMock()
        mock_history.from_api.return_value = [mock_history_item]

        ElevenLabsEncoder().delete_history()

        mock_history.from_api.assert_called_once()
        mock_history_item.delete.assert_called_once()

    @patch('zaphodvox.elevenlabs.encoder.ELVoice')
    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    @patch('zaphodvox.elevenlabs.encoder.set_api_key')
    def test_from_args(
        self, set_api_key, mock_voice_settings_from_voice_id,
        *args
    ):
        mock_voice_settings_from_voice_id.return_value = MagicMock()
        args = parse_args(['--api-key=1234', '--voice-id=Josh', 'test.txt'])

        encoder, voice = ElevenLabsEncoder.from_args(args)

        set_api_key.assert_called_once_with('1234')
        assert isinstance(encoder, ElevenLabsEncoder)
        assert voice.voice_id == 'Josh'

    def test_invalid_audio_format(self):
        with pytest.raises(ValueError):
            encoder = ElevenLabsEncoder(audio_format='invalid_audio_format')
            _ = encoder.file_extension

    def test_file_extension(self):
        encoder = ElevenLabsEncoder()
        assert encoder.file_extension == 'mp3'

