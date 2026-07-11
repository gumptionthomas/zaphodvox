from argparse import Namespace
from pathlib import Path
from typing import Optional

from pydantic import PrivateAttr, model_validator

from zaphodvox.paths import resolve_ref
from zaphodvox.voice import Voice


class QwenVoice(Voice):
    """A `Voice` configuration subclass for a Qwen3-TTS server.

    A voice is one of: a *preset* (a built-in speaker named by `voice_id`), a
    *clone* (a zero-shot clone of the reference audio at `ref_audio`), or a
    *design* (a voice generated from the natural-language `description`).
    Exactly one of `voice_id`, `ref_audio`, or `description` must be set.
    """

    voice_id: Optional[str] = None
    """The built-in preset speaker name (e.g. `Ryan`). Mutually exclusive with
    `ref_audio`/`description`."""
    language: str = 'English'
    """The language of the text (e.g. `English`). Defaults to `English`."""
    instruct: Optional[str] = None
    """An optional style/emotion direction for a preset voice (e.g. `calm,
    wry`). Ignored for cloned/designed voices."""
    ref_audio: Optional[str] = None
    """The path to a reference audio file to clone. Mutually exclusive with
    `voice_id`/`description`."""
    ref_text: Optional[str] = None
    """The transcript of `ref_audio`. If set, the higher-quality in-context
    (ICL) clone mode is used; otherwise a true zero-shot clone is used."""
    description: Optional[str] = None
    """A natural-language description of a voice to design (e.g. `a warm
    elderly woman`). Mutually exclusive with `voice_id`/`ref_audio`."""
    seed: Optional[int] = None
    """A fixed RNG seed for reproducible synthesis. When set, every fragment
    using this voice is generated from the same seed, which keeps the voice
    consistent across chunks (and across re-encodes). Defaults to `None`
    (non-deterministic)."""
    temperature: Optional[float] = None
    """The sampling temperature: how much the delivery varies from run to run
    (lower is steadier and more repeatable, higher is more varied), not an
    expressiveness control. Defaults to `None` (the server's default)."""

    _base_dir: Optional[Path] = PrivateAttr(default=None)
    """The directory of the file this voice was read from, which a relative
    `ref_audio` is resolved against. Deliberately private: it is a property of
    *where the voice was read from*, not of the voice, and must never be
    serialized back out."""

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

    def anchor(self, base_dir: Optional[Path]) -> 'QwenVoice':
        """Anchors a relative `ref_audio` to the directory of the file that
        declared this voice, so it no longer depends on the working directory
        the command happens to be run from.

        A voice with no `ref_audio` has nothing to anchor, and anchoring it
        anyway would make two otherwise identical preset voices compare unequal
        purely because they were read from different files.

        Args:
            base_dir: The directory `Path` of the voices file or manifest this
                voice was read from. `None` anchors to the current working
                directory (for a voice given on the command line).

        Returns:
            This voice, for chaining.
        """
        if self.ref_audio is not None:
            self._base_dir = base_dir
        return self

    @property
    def base_dir(self) -> Optional[Path]:
        """The directory this voice's relative `ref_audio` is anchored to.

        Returns:
            The anchor directory `Path`, or `None` for the working directory.
        """
        return self._base_dir

    @property
    def resolved_ref_audio(self) -> Optional[Path]:
        """The `ref_audio` path resolved against this voice's anchor.

        Returns:
            The resolved reference audio `Path`, or `None` if not a clone.
        """
        if self.ref_audio is None:
            return None
        return resolve_ref(self.ref_audio, self._base_dir)

    @property
    def is_clone(self) -> bool:
        """Whether this voice is a clone of a reference audio file.

        Returns:
            `True` if the voice clones `ref_audio`.
        """
        return self.ref_audio is not None

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
