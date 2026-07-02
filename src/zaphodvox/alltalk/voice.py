from typing import Optional

from argparse import Namespace

from zaphodvox.voice import Voice


class AllTalkVoice(Voice):
    """A `Voice` configuration subclass for ElevenLabs text-to-speech."""

    voice_id: str
    """The ID of the voice."""
    language_code: Optional[str] = 'en'
    """The language code to be used. Defaults to `en`."""

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['AllTalkVoice']:
        """Returns an `AllTalkVoice` instance from the given arguments.

        Args:
            args: The command-line arguments.

        Returns:
            An `AllTalkVoice` instance, `None` if insufficient arguments.
        """
        voice_id: str = args.voice_id
        language_code: Optional[str] = args.language_code

        if voice_id is None:
            return None
        return cls(
            voice_id=voice_id,
            language_code=language_code,
        )
