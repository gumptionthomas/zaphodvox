import pytest

from zaphodvox.qwen.voice import QwenVoice
from zaphodvox.voices import parse_voice

from fake_encoder import FakeVoice


class TestParseVoice():
    """The on-disk half of the multi-encoder seam: a serialized voice is read
    back as the subclass that wrote it.

    One backend ships today, so the second subject here is the test-only
    `FakeVoice` -- see `test/fake_encoder.py` for why it exists.
    """

    def test_reads_a_tagged_voice_as_its_own_subclass(self):
        qwen = parse_voice({'encoder': 'qwen', 'voice_id': 'Ryan'})
        fake = parse_voice({'encoder': 'fake', 'voice_id': 'Fake'})

        assert isinstance(qwen, QwenVoice)
        assert isinstance(fake, FakeVoice)

    def test_an_untagged_voice_is_a_qwen_voice(self):
        # A file written before the tag existed has none, and Qwen was the only
        # backend at the time.
        voice = parse_voice({'voice_id': 'Ryan', 'language': 'English'})

        assert isinstance(voice, QwenVoice)

    def test_a_foreign_setting_is_not_silently_dropped(self):
        # The load-bearing case for `extra='forbid'`: untagged, and carrying a
        # setting only the other engine has. Without it this would validate as a
        # QwenVoice -- succeeding, while quietly discarding `accent`.
        voice = parse_voice({'voice_id': 'Fake', 'accent': 'west country'})

        assert isinstance(voice, FakeVoice)
        assert voice.accent == 'west country'

    def test_a_voice_passes_through_unchanged(self):
        voice = QwenVoice(voice_id='Ryan')

        assert parse_voice(voice) is voice

    def test_a_voice_for_no_encoder_is_reported(self):
        with pytest.raises(ValueError) as e:
            parse_voice({'voice_id': 'Ryan', 'nonsense': True})

        # The error names every subclass it tried, so the reader can see which
        # engine they meant to write for.
        message = str(e.value)
        assert 'QwenVoice' in message and 'FakeVoice' in message
