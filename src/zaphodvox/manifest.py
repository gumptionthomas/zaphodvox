from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, SerializeAsAny, field_validator

from zaphodvox.voice import Voice
from zaphodvox.voices import parse_voice


class Fragment(BaseModel):
    """The settings to generate a text-to-speech audio file fragment."""

    text: str
    """The text converted to speech."""
    filename: Optional[str] = None
    """The file name of the audio file."""
    voice: Optional[SerializeAsAny[Voice]] = None
    """The `Voice` settings for the speech."""
    voice_name: Optional[str] = None
    """The name of the voice used for the speech."""

    @field_validator('voice', mode='before')
    @classmethod
    def _coerce_voice(cls, value: Any) -> Any:
        """Deserializes a raw voice mapping into the concrete `Voice` subclass
        its encoder uses, so an inline (unnamed) manifest voice round-trips
        instead of collapsing to a fieldless base `Voice`. Instances are passed
        through unchanged.

        Args:
            value: The raw `voice` field value (a mapping from JSON, a `Voice`
                instance, or `None`).

        Returns:
            The concrete `Voice` if given a mapping, otherwise `value` unchanged.
        """
        if value is None:
            return None
        return parse_voice(value)
    silence_duration: Optional[int] = None
    """The duration of the silence in seconds for empty lines."""
    encoder: Optional[str] = None
    """The name of the encoder for the speech conversion."""
    audio_format: Optional[str] = None
    """The audio format for the speech conversion."""
    encoded: Optional[datetime] = None
    """The date/time of the speech conversion."""


class Manifest(BaseModel):
    """A list of settings to generate text-to-speech audio file fragments."""

    fragments: list[Fragment] = []
    """The list of audio file fragments and their settings."""
    voices: Optional[dict[str, SerializeAsAny[Voice]]] = None
    """The named voice configurations."""

    @field_validator('voices', mode='before')
    @classmethod
    def _coerce_voices(cls, value: Any) -> Any:
        """Deserializes each raw voice mapping into its encoder's concrete
        `Voice` subclass, so a manifest stays self-contained.

        Args:
            value: The raw `voices` field value.

        Returns:
            The name/`Voice` mapping, or `value` unchanged.
        """
        if isinstance(value, dict):
            return {k: parse_voice(v) for k, v in value.items()}
        return value

    @property
    def length(self) -> int:
        """The number of audio file fragments in the manifest.

        Returns:
            The number of audio file fragments.
        """
        return len(self.fragments)

    @property
    def file_extension(self) -> Optional[str]:
        """The file extension of the audio file fragments.

        Returns:
            The file extension of the audio file fragments.
        """
        file_ext = None
        for fragment in self.fragments:
            if fragment.filename:
                file_ext = Path(fragment.filename).suffix[1:]
                break
        return file_ext

    def set_used_voices(
        self, voices: Optional[dict[str, Voice]]
    ) -> None:
        """Sets the used voices for the audio file fragments.

        Args:
            voices: The named voice configurations.
        """
        used_voice_names = set(
            f.voice_name for f in self.fragments if f.voice_name is not None
        )
        self.voices = None
        if voices:
            self.voices = {
                name: voices[name] for name in used_voice_names
                if voices.get(name)
            } or None

    @classmethod
    def plan(
        cls, fragments: list[Fragment], basename: str, file_ext: str,
        silence_duration: Optional[int] = None
    ) -> 'Manifest':
        """Generates an encoding plan manifest for the given text fragments
        using the specified default `Voice`.

        Args:
            fragments: The list of audio file fragments and their settings.
            basename: The base name for the output audio files.
            file_ext: The file extension for the output audio files.
            silence_duration: The duration of the silence in seconds for empty
                lines. Defaults to `None` which indicates no silence.
        """
        manifest = Manifest()
        for i, fragment in enumerate(fragments):
            filename = fragment.filename or f'{basename}-{i:05}.{file_ext}'
            filename = str(Path(filename).with_suffix(f'.{file_ext}'))
            new_fragment = Fragment(
                text=fragment.text,
                filename=filename,
                voice=fragment.voice,
                voice_name=fragment.voice_name
            )
            if not new_fragment.text:
                new_fragment.voice = None
                new_fragment.voice_name = None
                new_fragment.silence_duration = silence_duration
            manifest.fragments.append(new_fragment)
        return manifest
