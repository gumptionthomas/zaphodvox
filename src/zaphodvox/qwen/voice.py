from argparse import Namespace
from typing import Optional

from pydantic import model_validator

from zaphodvox.voice import Voice


class QwenVoice(Voice):
    """A `Voice` configuration subclass for a Qwen3-TTS server.

    A voice is either a *preset* (a built-in speaker named by `voice_id`) or a
    *clone* (a zero-shot clone of the reference audio at `ref_audio`). Exactly
    one of `voice_id` or `ref_audio` must be set.
    """

    voice_id: Optional[str] = None
    """The built-in preset speaker name (e.g. `Ryan`). Mutually exclusive with
    `ref_audio`."""
    language: str = 'English'
    """The language of the text (e.g. `English`). Defaults to `English`."""
    instruct: Optional[str] = None
    """An optional style/emotion direction for a preset voice (e.g. `calm,
    wry`). Ignored for cloned voices."""
    ref_audio: Optional[str] = None
    """The path to a reference audio file to clone. Mutually exclusive with
    `voice_id`."""
    ref_text: Optional[str] = None
    """The transcript of `ref_audio`. If set, the higher-quality in-context
    (ICL) clone mode is used; otherwise a true zero-shot clone is used."""
    seed: Optional[int] = None
    """A fixed RNG seed for reproducible synthesis. When set, every fragment
    using this voice is generated from the same seed, which keeps the voice
    consistent across chunks (and across re-encodes). Defaults to `None`
    (non-deterministic)."""

    @model_validator(mode='after')
    def _check_preset_or_clone(self) -> 'QwenVoice':
        """Ensures the voice is either a preset or a clone, but not neither.

        Raises:
            ValueError: If neither `voice_id` nor `ref_audio` is set.
        """
        if not self.voice_id and not self.ref_audio:
            raise ValueError(
                'A QwenVoice requires either a preset "voice_id" or a clone '
                '"ref_audio".'
            )
        return self

    @property
    def is_clone(self) -> bool:
        """Whether this voice is a clone of a reference audio file.

        Returns:
            `True` if the voice clones `ref_audio`, `False` if it is a preset.
        """
        return self.ref_audio is not None

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['QwenVoice']:
        """Returns a `QwenVoice` instance from the given arguments.

        Args:
            args: The command-line arguments.

        Returns:
            A `QwenVoice` instance, `None` if insufficient arguments.
        """
        voice_id: Optional[str] = args.voice_id
        ref_audio = args.voice_ref_audio

        if not voice_id and not ref_audio:
            return None
        return cls(
            voice_id=voice_id,
            language=args.voice_language,
            instruct=args.voice_instruct,
            ref_audio=str(ref_audio) if ref_audio else None,
            ref_text=args.voice_ref_text,
            seed=args.voice_seed,
        )
