from argparse import Namespace
from typing import Literal, Optional

from pydantic import model_validator

from zaphodvox.voice import Voice


class ChatterboxVoice(Voice):
    """A `Voice` configuration subclass for a Chatterbox TTS server.

    A voice is one of: a *preset* (a built-in speaker named by `voice_id`) or a
    *clone* (of the reference audio at `ref_audio`). Exactly one must be set.

    Chatterbox has no natural-language voice *design*, and no in-context clone
    mode -- there is no `description` or `ref_text` here, and asking for either
    is an error rather than a silently ignored setting. It steers delivery
    numerically instead: `exaggeration` for expressiveness, `cfg_weight` for how
    closely it follows the reference, and `speed_factor` for pace.
    """

    encoder: Literal['chatterbox'] = 'chatterbox'
    """The encoder this voice belongs to."""
    exaggeration: Optional[float] = None
    """How expressive the delivery is (0.25-2.0). Unlike Qwen's `temperature`,
    this really is an expressiveness dial. Defaults to `None` (the server's
    default)."""
    cfg_weight: Optional[float] = None
    """The classifier-free guidance weight: how closely the delivery follows the
    reference voice, at the cost of expressiveness. Defaults to `None` (the
    server's default)."""
    speed_factor: Optional[float] = None
    """How fast the speech is, as a multiple of normal pace. Defaults to `None`
    (the server's default)."""

    @model_validator(mode='after')
    def _check_voice_source(self) -> 'ChatterboxVoice':
        """Ensures the voice specifies exactly one source (preset or clone).

        Raises:
            ValueError: If neither or both of `voice_id` and `ref_audio` are set.
        """
        sources = [self.voice_id, self.ref_audio]
        set_count = sum(source is not None for source in sources)
        if set_count == 0:
            raise ValueError(
                'A ChatterboxVoice requires a preset "voice_id" or a clone '
                '"ref_audio".'
            )
        if set_count > 1:
            raise ValueError(
                'A ChatterboxVoice must specify exactly one of "voice_id" or '
                '"ref_audio".'
            )
        return self

    @property
    def label(self) -> str:
        """A short human-readable description of the voice, for the console.

        Returns:
            The description of the voice.
        """
        if self.is_clone:
            label = f'clone of "{self.ref_audio}"'
        else:
            label = f'"{self.voice_id}"'
        if self.exaggeration is not None:
            label += f'  ·  exaggeration: {self.exaggeration}'
        return label

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['ChatterboxVoice']:
        """Returns a `ChatterboxVoice` instance from the given arguments.

        Args:
            args: The command-line arguments.

        Returns:
            A `ChatterboxVoice` instance, `None` if insufficient arguments.

        Raises:
            ValueError: If given a setting Chatterbox does not have.
        """
        voice_id: Optional[str] = args.voice_id
        ref_audio = args.voice_ref_audio

        if not any([voice_id, ref_audio]):
            return None
        # Fail loudly rather than synthesize a whole book in a voice that
        # quietly ignored what was asked for.
        if args.voice_description:
            raise ValueError(
                'Chatterbox cannot design a voice from a description. Use a '
                'preset "--voice-id" or a clone "--voice-ref-audio" (a Qwen '
                'design can be auditioned and adopted as a clone, which '
                'Chatterbox can then use).'
            )
        if args.voice_instruct:
            raise ValueError(
                'Chatterbox has no "--voice-instruct". Use '
                '"--voice-exaggeration" to make the delivery more expressive.'
            )
        if args.voice_ref_text:
            raise ValueError(
                'Chatterbox has no in-context clone mode, so '
                '"--voice-ref-text" would be ignored. Omit it.'
            )
        return cls(
            voice_id=voice_id,
            ref_audio=ref_audio.as_posix() if ref_audio else None,
            seed=args.voice_seed,
            temperature=args.voice_temperature,
            exaggeration=args.voice_exaggeration,
            cfg_weight=args.voice_cfg_weight,
            speed_factor=args.voice_speed,
        )
