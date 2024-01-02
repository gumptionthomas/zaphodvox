import pytest

from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.text import clean_text, parse_text


class TestCleanText():
    def test_clean_text(self):
        text = "Hello, world!"
        assert clean_text(text) == text+'\n\n'
        text = "Hello, world!\n"
        assert clean_text(text) == text+'\n'
        text = "Hello, world,\nit's me."
        assert clean_text(text) == "Hello, world, it's me.\n\n"
        text = "012345678."
        assert clean_text(text, max_chars=5) == "01234\n\n5678.\n\n"
        text = "0123456789"
        assert clean_text(text, max_chars=5) == "01234\n\n56789 "
        text = "'0123?' '4567.' 89.\n"
        assert clean_text(text, max_chars=7) == "'0123?'\n\n'4567.'\n\n89.\n\n"


class TestTextParser():
    def test_parse(self):
        full_text = (
            "Paragraph 1\nZVOX: Joe\nParagraph 2\n"
            "ZVOX: Josh\nParagraph 3"
        )
        voice = GoogleVoice(
            voice_id='A', language='en', region='UK', type='Wavenet'
        )
        parsed_voice = GoogleVoice(
            voice_id='B', language='en', region='US', type='Wavenet'
        )

        text_blocks = parse_text(
            full_text, voice=voice, voices={'Joe': parsed_voice}
        )

        assert len(text_blocks) == 3
        assert text_blocks[0] == ('Paragraph 1', voice)
        assert (text_blocks[1][0], text_blocks[1][1]) == \
            ('Paragraph 2', parsed_voice)
        assert (text_blocks[2][0], text_blocks[2][1]) == \
            ('Paragraph 3', parsed_voice)

    def test_parse_max_chars(self):
        full_text = (
            "Paragraph 1\nZVOX: Joe\nParagraph 2\n\n"
            "ZVOX: Josh\nParagraph 3\n"
        )
        voice = GoogleVoice(
            voice_id='A', language='en', region='UK', type='Wavenet'
        )
        parsed_voice = GoogleVoice(
            voice_id='B', language='en', region='US', type='Wavenet'
        )

        text_blocks = parse_text(
            full_text, voice=voice, voices={'Joe': parsed_voice}, max_chars=25
        )

        assert len(text_blocks) == 2
        assert text_blocks[0] == ('Paragraph 1', voice)
        assert (text_blocks[1][0], text_blocks[1][1]) == \
            ('Paragraph 2\n\nParagraph 3\n', parsed_voice)

    def test_encode_no_voice(self, *args):
        with pytest.raises(ValueError):
            parse_text("Paragraph 1", voice=None)
