from typing import Optional

from pydantic import BaseModel

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.voice import Voice


class NamedVoicesConfiguration(BaseModel):
    """A named voice configuration."""

    google: Optional[GoogleVoice] = None
    """A `GoogleVoice` configuration."""
    elevenlabs: Optional[ElevenLabsVoice] = None
    """An `ElevenLabsVoice` configuration."""

    def encoder_voice(self, encoder_name: str) -> Optional[Voice]:
        """Returns the voice for the given encoder name.

        Args:
            encoder_name: The encoder name.

        Returns:
            The voice for the encoder name.
        """
        return getattr(self, encoder_name, None)


class NamedVoices(BaseModel):
    """A dictionary of named voice configurations."""

    voices: Optional[dict[str, NamedVoicesConfiguration]] = None
    """The named voice configurations."""

    def encoder_voices(self, encoder_name: Optional[str]) -> dict[str, Optional[Voice]]:
        """Returns the named voices for the given encoder name.

        Args:
            encoder_name: The encoder name.

        Returns:
            The name/`Voice` pairs for the encoder name.
        """
        voices: dict[str, Optional[Voice]] = {}
        if self.voices and encoder_name:
            voices = {
                k: v.encoder_voice(encoder_name)
                for k, v in self.voices.items()
            }
        return voices

    def add_voices(
        self, voices: Optional[dict[str, NamedVoicesConfiguration]]
    ) -> None:
        """Adds the given voices into this instance.

        Args:
            voices: The voices to add.
        """
        if voices:
            self.voices = {**voices, **(self.voices or {})}
