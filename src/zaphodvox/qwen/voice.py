from argparse import Namespace
from typing import Literal, Optional

from pydantic import model_validator

from zaphodvox.voice import Voice


class QwenVoice(Voice):
    """A `Voice` configuration subclass for a Qwen3-TTS server.

    A voice is one of: a *preset* (a built-in speaker named by `voice_id`), a
    *clone* (a zero-shot clone of the reference audio at `ref_audio`), or a
    *design* (a voice generated from the natural-language `description`).
    Exactly one of `voice_id`, `ref_audio`, or `description` must be set.
    """

    encoder: Literal['qwen'] = 'qwen'
    """The encoder this voice belongs to. Defaults to `qwen`, so a voices file
    or manifest written before there was a second backend still reads back as
    what it was."""
    language: str = 'English'
    """The language of the text (e.g. `English`). Defaults to `English`."""
    instruct: Optional[str] = None
    """An optional style/emotion direction for a preset voice (e.g. `calm,
    wry`). Ignored for cloned/designed voices."""
    ref_text: Optional[str] = None
    """The transcript of `ref_audio`. If set, the higher-quality in-context
    (ICL) clone mode is used; otherwise a true zero-shot clone is used."""
    description: Optional[str] = None
    """A natural-language description of a voice to design (e.g. `a warm
    elderly woman`). Mutually exclusive with `voice_id`/`ref_audio`."""

    @model_validator(mode='after')
    def _check_voice_source(self) -> 'QwenVoice':
        """Ensures the voice specifies exactly one source (preset, clone, or
        design).

        Raises:
            ValueError: If none or more than one of `voice_id`, `ref_audio`,
                or `description` is set.
        """
        sources = [self.voice_id, self.ref_audio, self.description]
        set_count = sum(source is not None for source in sources)
        if set_count == 0:
            raise ValueError(
                'A QwenVoice requires one of a preset "voice_id", a clone '
                '"ref_audio", or a "description".'
            )
        if set_count > 1:
            raise ValueError(
                'A QwenVoice must specify exactly one of "voice_id", '
                '"ref_audio", or "description".'
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
            if not self.ref_text:
                label += '  ·  [dim]zero-shot (no --voice-ref-text)[/dim]'
        elif self.is_design:
            label = f'designed voice: "{self.description}"'
        else:
            label = f'"{self.voice_id}"'
            if self.instruct:
                label += f'  ·  instruct: "{self.instruct}"'
        return f'{label}  ·  {self.language}'

    @property
    def is_design(self) -> bool:
        """Whether this voice is designed from a description.

        Returns:
            `True` if the voice is generated from `description`.
        """
        return self.description is not None

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
        description: Optional[str] = args.voice_description

        if not any([voice_id, ref_audio, description]):
            return None
        return cls(
            voice_id=voice_id,
            language=args.voice_language,
            instruct=args.voice_instruct,
            ref_audio=ref_audio.as_posix() if ref_audio else None,
            ref_text=args.voice_ref_text,
            description=description,
            seed=args.voice_seed,
            temperature=args.voice_temperature,
        )
