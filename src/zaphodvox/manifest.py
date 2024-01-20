from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.named_voices import NamedVoicesConfiguration
from zaphodvox.voice import Voice


class Fragment(BaseModel):
    """The settings to generate a text-to-speech audio file fragment."""

    text: str
    """The text converted to speech."""
    filename: Optional[str] = None
    """The file name of the audio file."""
    voice: Optional[GoogleVoice | ElevenLabsVoice | Voice] = None
    """The `Voice` settings for the speech."""
    voice_name: Optional[str] = None
    """The name of the voice used for the speech."""
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
    voices: Optional[dict[str, NamedVoicesConfiguration]] = None
    """The named voice configurations."""

    def set_used_voices(
        self, voices: Optional[dict[str, NamedVoicesConfiguration]]
    ) -> None:
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
            new_fragment = Fragment(
                text=fragment.text,
                filename=f'{basename}-{i:05}.{file_ext}',
                voice=fragment.voice,
                voice_name=fragment.voice_name
            )
            if not new_fragment.text:
                new_fragment.voice = None
                new_fragment.voice_name = None
                new_fragment.silence_duration = silence_duration
            manifest.fragments.append(new_fragment)
        return manifest
