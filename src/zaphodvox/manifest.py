from typing import Optional

from pydantic import BaseModel

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.voice import Voice


class SpeechAudioFile(BaseModel):
    """The settings used to generate a text-to-speech audio file."""

    text: str
    """The text that was converted to speech."""
    filename: str
    """The name of the audio file."""
    voice: Optional[GoogleVoice | ElevenLabsVoice | Voice] = None
    """The `Voice` settings used for the speech."""
    encoder: Optional[str] = None
    """The name of the encoder used for the speech conversion."""
    audio_format: Optional[str] = None
    """The audio format used for the speech conversion."""
    silence_duration: Optional[int] = None
    """The duration of the silence in seconds for empty lines."""

class Manifest(BaseModel):
    """A list of settings used to generate text-to-speech audio files."""

    speech_audio_files: list[SpeechAudioFile]
    """The list of audio files and their settings."""
