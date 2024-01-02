from typing import Optional

from elevenlabs import VoiceSettings

from zaphodvox.voice import Voice


class ElevenLabsVoice(Voice):
    """A `Voice` configuration subclass for ElevenLabs text-to-speech."""

    voice_id: str
    """The ID of the voice."""
    model: Optional[str] = 'eleven_multilingual_v2'
    """The model to be used. Defaults to `eleven_multilingual_v2`."""
    stability: Optional[float] = None
    """The stability scalar."""
    similarity_boost: Optional[float] = None
    """The similarity boost scalar."""
    style: Optional[float] = None
    """The style scalar."""
    use_speaker_boost: Optional[bool] = None
    """Whether to use speaker boost."""

    @property
    def voice_settings(self) -> VoiceSettings:
        """Retrieves the voice settings for the current instance.

        Returns:
            The `VoiceSettings` object.
        """
        settings = VoiceSettings.from_voice_id(self.voice_id)
        if self.stability is not None:
            settings.stability = self.stability
        if self.similarity_boost is not None:
            settings.similarity_boost = self.similarity_boost
        if self.style is not None:
            settings.style = self.style
        if self.use_speaker_boost is not None:
            settings.use_speaker_boost = self.use_speaker_boost
        return settings
