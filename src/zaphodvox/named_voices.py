from typing import Optional

from pydantic import BaseModel

from zaphodvox.qwen.voice import QwenVoice
from zaphodvox.voice import Voice


class NamedVoices(BaseModel):
    """A dictionary of named `QwenVoice` configurations."""

    voices: Optional[dict[str, QwenVoice]] = None
    """The named voice configurations."""

    def encoder_voices(self) -> dict[str, Optional[Voice]]:
        """Returns the named voices as a name/`Voice` mapping.

        Returns:
            The name/`Voice` pairs.
        """
        return dict(self.voices) if self.voices else {}

    def add_voices(self, voices: Optional[dict[str, QwenVoice]]) -> None:
        """Adds the given voices into this instance.

        Args:
            voices: The voices to add.
        """
        if voices:
            self.voices = {**voices, **(self.voices or {})}
