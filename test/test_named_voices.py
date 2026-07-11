from pathlib import Path
from unittest.mock import mock_open

from zaphodvox.main import read_voices


class TestLoadNamedVoices():
    def test_parse_voices(
        self, qwen_voice, qwen_voice_2, mock_builtins_open, voices_json_data
    ):
        # Setup
        mock_builtins_open.return_value = mock_open(
            read_data=voices_json_data
        ).return_value
        filepath = Path('/path/to/voices.json')

        # Run
        voices = read_voices(filepath, None)

        # Verify
        mock_builtins_open.assert_called_once_with(
            str(filepath), 'r', encoding='utf-8'
        )
        encoder_voices = voices.encoder_voices()
        assert encoder_voices == {
            'voice_1': qwen_voice,
            'voice_2': qwen_voice_2,
        }

    def test_encoder_voices_empty(self):
        from zaphodvox.named_voices import NamedVoices

        assert NamedVoices().encoder_voices() == {}

    def test_add_voices(self, qwen_voice, qwen_voice_2):
        from zaphodvox.named_voices import NamedVoices

        named = NamedVoices(voices={'voice_1': qwen_voice})
        named.add_voices({'voice_2': qwen_voice_2})
        assert named.encoder_voices() == {
            'voice_1': qwen_voice,
            'voice_2': qwen_voice_2,
        }
