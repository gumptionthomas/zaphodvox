from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, PrivateAttr

from zaphodvox.paths import resolve_ref


class Voice(BaseModel):
    """Represents a voice configuration used for text-to-speech conversion.

    Each encoder has its own subclass, since the engines take genuinely different
    settings and there is nothing to gain from pretending otherwise. What they do
    share lives here: a voice may clone a reference audio file, and it knows
    which encoder it belongs to.

    Extra fields are rejected, and that is load-bearing: it is what lets a
    serialized voice be read back as the right subclass. Without it a voice for
    one engine would quietly validate as a voice for another, silently dropping
    every setting the other does not recognize.
    """

    model_config = ConfigDict(extra='forbid')

    voice_id: Optional[str] = None
    """The built-in preset speaker the server offers (what the server calls it:
    `Ryan` for Qwen, `Ryan.wav` for Chatterbox). See `--list-voices`."""
    ref_audio: Optional[str] = None
    """The path to a reference audio file to clone. A relative path is resolved
    against the directory of the file that declared it (see `anchor`)."""
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

    def anchor(self, base_dir: Optional[Path]) -> 'Voice':
        """Anchors a relative `ref_audio` to the directory of the file that
        declared this voice, so it no longer depends on the working directory the
        command happens to be run from.

        A voice with no `ref_audio` has nothing to anchor, and anchoring it anyway
        would make two otherwise identical preset voices compare unequal purely
        because they were read from different files.

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
    def label(self) -> str:
        """A short human-readable description of the voice, for the console.

        Returns:
            The description of the voice.
        """
        if self.ref_audio:
            return f'clone of "{self.ref_audio}"'
        return type(self).__name__
