from typing import Any, Optional

from pydantic import BaseModel, SerializeAsAny, field_validator

from zaphodvox.voice import Voice
from zaphodvox.voices import parse_voice


class NamedVoices(BaseModel):
    """A dictionary of named `Voice` configurations.

    The voices may belong to different encoders: each records its own, so one
    voices file can be a library for every engine.
    """

    voices: Optional[dict[str, SerializeAsAny[Voice]]] = None
    """The named voice configurations."""

    @field_validator('voices', mode='before')
    @classmethod
    def _coerce_voices(cls, value: Any) -> Any:
        """Deserializes each raw voice mapping into its encoder's concrete
        `Voice` subclass.

        Args:
            value: The raw `voices` field value.

        Returns:
            The name/`Voice` mapping, or `value` unchanged.
        """
        if isinstance(value, dict):
            return {k: parse_voice(v) for k, v in value.items()}
        return value

    def encoder_voices(self) -> dict[str, Optional[Voice]]:
        """Returns the named voices as a name/`Voice` mapping.

        Returns:
            The name/`Voice` pairs.
        """
        return dict(self.voices) if self.voices else {}

    def add_voices(self, voices: Optional[dict[str, Voice]]) -> None:
        """Adds the given voices into this instance.

        Args:
            voices: The voices to add.
        """
        if voices:
            self.voices = {**voices, **(self.voices or {})}
