from typing import Any, Optional

from argparse import Namespace
from google.cloud.texttospeech import AudioConfig, VoiceSelectionParams

from zaphodvox.voice import Voice


class GoogleVoice(Voice):
    """A `Voice` configuration subclass for Google text-to-speech."""

    voice_id: str
    """The ID of the voice."""
    language: str
    """The language."""
    region: str
    """The region."""
    type: str
    """The type of voice."""
    speaking_rate: Optional[float] = None
    """The speaking rate."""
    pitch: Optional[float] = None
    """The pitch."""
    volume_gain_db: Optional[float] = None
    """The volume gain in decibels."""
    sample_rate_hertz: Optional[int] = None
    """The sample rate in hertz."""
    effects_profile_id: Optional[list[str]] = None

    @property
    def voice_selection_params(self) -> VoiceSelectionParams:
        """Retrieves the voice selection parameters for the current instance.

        Returns:
            The `VoiceSelectionParams` object.
        """
        language_code = f'{self.language}-{self.region}'
        return VoiceSelectionParams(
            language_code=language_code,
            name=f'{language_code}-{self.type}-{self.voice_id}'
        )

    def get_audio_config(self, audio_encoding: int) -> AudioConfig:
        """Retrieves the audio configuration for the current instance.

        Args:
            audio_encoding: The audio encoding to be used.

        Returns:
            The `AudioConfig` object.
        """
        audio_config_kwargs: dict[str, Any] = {}
        audio_config_kwargs['audio_encoding'] = audio_encoding
        if (speaking_rate := self.speaking_rate) is not None:
            audio_config_kwargs['speaking_rate'] = speaking_rate
        if (pitch := self.pitch) is not None:
            audio_config_kwargs['pitch'] = pitch
        if (volume_gain_db := self.volume_gain_db) is not None:
            audio_config_kwargs['volume_gain_db'] = volume_gain_db
        if (sample_rate_hertz := self.sample_rate_hertz) is not None:
            audio_config_kwargs['sample_rate_hertz'] = sample_rate_hertz
        if (effects_profile_id := self.effects_profile_id) is not None:
            audio_config_kwargs['effects_profile_id'] = effects_profile_id
        return AudioConfig(**audio_config_kwargs)

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['GoogleVoice']:
        """Create an instance of `GoogleVoice` based on the provided arguments.

        Args:
            cls: The class object of the `GoogleVoice`.
            args: The command-line arguments.

        Returns:
            An `GoogleVoice` instance, `None` if insufficient arguments.
        """
        voice = None
        if None not in [
            args.voice_id, args.voice_language,
            args.voice_region, args.voice_type
        ]:
            voice = cls(
                voice_id=args.voice_id,
                language=args.voice_language,
                region=args.voice_region,
                type=args.voice_type,
                speaking_rate=args.voice_speaking_rate,
                pitch=args.voice_pitch,
                volume_gain_db=args.voice_volume_gain_db,
                sample_rate_hertz=args.voice_sample_rate_hertz,
                effects_profile_id=args.voice_effects_profile_id
            )
        return voice
