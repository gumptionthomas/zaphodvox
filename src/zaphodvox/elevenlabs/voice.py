from typing import Optional

from argparse import Namespace
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

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['ElevenLabsVoice']:
        """Returns an `ElevenLabsVoice` instance from the given arguments.

        Args:
            args: The command-line arguments.

        Returns:
            An `ElevenLabsVoice` instance, `None` if insufficient arguments.
        """
        voice_id: Optional[str] = args.voice_id
        voice_model: Optional[str] = args.voice_model
        voice_stability: Optional[float] = args.voice_stability
        voice_similarity_boost: Optional[float] = args.voice_similarity_boost
        voice_style: Optional[float] = args.voice_style
        voice_use_speaker_boost: Optional[bool] = args.voice_use_speaker_boost

        if voice_id is None:
            return None
        return cls(
            voice_id=voice_id,
            model=voice_model,
            stability=voice_stability,
            similarity_boost=voice_similarity_boost,
            style=voice_style,
            use_speaker_boost=voice_use_speaker_boost
        )
