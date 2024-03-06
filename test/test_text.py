import pytest

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
    def test_parse(self, google_voice, google_voice_2):
        # Setup
        full_text = (
            "Paragraph 1\nZVOX: Trillian\nParagraph 2\n"
            "Paragraph 3"
        )

        # Run
        text_fragments = parse_text(
            full_text, voice=google_voice, voices={'Trillian': google_voice_2}
        )

        # Verify
        assert len(text_fragments) == 3
        assert text_fragments[0].text == 'Paragraph 1'
        assert text_fragments[0].voice == google_voice
        assert text_fragments[1].text == 'Paragraph 2'
        assert text_fragments[1].voice == google_voice_2
        assert text_fragments[2].text == 'Paragraph 3'
        assert text_fragments[2].voice == google_voice_2

    def test_parse_max_chars(self, google_voice, google_voice_2):
        # Setup
        full_text = (
            "Paragraph 1\nZVOX: Trillian\nParagraph 2\n\n"
            "Paragraph 3\n\nParagraph 4"
        )

        # Run
        text_fragments = parse_text(
            full_text,
            voice=google_voice,
            voices={'Trillian': google_voice_2},
            max_chars=30
        )

        # Verify
        assert len(text_fragments) == 3
        assert text_fragments[0].text == 'Paragraph 1\n'
        assert text_fragments[0].voice == google_voice
        assert text_fragments[1].text == 'Paragraph 2\n\nParagraph 3\n\n'
        assert text_fragments[1].voice == google_voice_2
        assert text_fragments[2].text == 'Paragraph 4'
        assert text_fragments[2].voice == google_voice_2

    def test_encode_no_voice(self):
        with pytest.raises(ValueError):
            parse_text("Paragraph 1", voice=None)
