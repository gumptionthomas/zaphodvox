"""A second encoder that exists only for the tests.

`zaphodvox` ships one backend, but the seam it sits behind is deliberate, and
several of its properties are only meaningful with more than one implementation:
`Encoder`'s subclass registration, the `encoder` tag a serialized voice carries,
`voices.parse_voice()` reading a voice back as the right subclass, and
`extra='forbid'` stopping one engine's voice from quietly validating as
another's. Chatterbox used to be the second subject for those tests. This is
what replaces it, so the seam keeps being exercised rather than merely existing
until a real second backend turns up.

Importing this module registers both classes for the rest of the session --
`Voice.__subclasses__()` and `Encoder.__subclasses__()` are process-global -- so
they are built to be inert. The `Literal` encoder tag plus the inherited
`extra='forbid'` mean a fake voice can never validate as a Qwen one, or the
reverse. The one visible effect is that `--encoder-name` accepts `fake` while
the tests are running, which is what lets the seam be driven from the command
line with no server at all.
"""

from argparse import Namespace
from pathlib import Path
from typing import Literal, Optional

from zaphodvox.encoder import Encoder, PresetVoice
from zaphodvox.voice import Voice

FAKE_AUDIO = b'RIFFfake'
"""What `FakeEncoder.t2s()` writes, in place of a server's response."""


class FakeVoice(Voice):
    """A `Voice` for an engine that does not exist.

    `accent` is a setting no other engine has, which is the point: it is what
    proves `extra='forbid'` keeps this voice from being read back as a Qwen one.
    """

    encoder: Literal['fake'] = 'fake'
    """The encoder this voice belongs to."""
    accent: Optional[str] = None
    """A setting that exists on no other engine."""

    @classmethod
    def from_args(cls, args: Namespace) -> Optional['FakeVoice']:
        """Returns a `FakeVoice` from the given arguments, mirroring the real
            encoders: a preset `--voice-id` or a clone `--voice-ref-audio`.

        Args:
            args: The command-line arguments.

        Returns:
            A `FakeVoice`, or `None` if neither was given.
        """
        ref_audio = args.voice_ref_audio
        if not any([args.voice_id, ref_audio]):
            return None
        return cls(
            voice_id=args.voice_id,
            ref_audio=ref_audio.as_posix() if ref_audio else None,
            seed=args.voice_seed,
            temperature=args.voice_temperature,
        )


class FakeEncoder(Encoder):
    """An `Encoder` that writes bytes instead of talking to a server."""

    name: Optional[str] = 'fake'
    """The name `--encoder-name fake` selects."""

    @property
    def audio_format(self) -> str:
        """The audio format to be used."""
        return 'wav'

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files."""
        return 'wav'

    def validate_voice(self, voice: Voice) -> None:
        """Checks a clone's reference audio exists, as the real encoders do.

        Args:
            voice: The `Voice` to validate.

        Raises:
            ValueError: If `voice` is not a `FakeVoice`, or clones a reference
                audio file that cannot be found.
        """
        if not isinstance(voice, FakeVoice):
            raise ValueError('Not a FakeVoice.')
        ref_audio = voice.resolved_ref_audio
        if ref_audio is not None and not ref_audio.is_file():
            raise ValueError(f'Reference audio "{voice.ref_audio}" not found.')

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Writes fixed bytes to `filepath`, in place of synthesis.

        Args:
            text: The text that would have been spoken.
            voice: The `FakeVoice` to use.
            filepath: The `Path` of the generated audio file.

        Raises:
            ValueError: If `voice` is not a `FakeVoice`.
        """
        if not isinstance(voice, FakeVoice):
            raise ValueError('Not a FakeVoice.')
        filepath.write_bytes(FAKE_AUDIO)

    @classmethod
    def from_args(cls, args: Namespace) -> tuple[Encoder, Optional[Voice]]:
        """Creates a `FakeEncoder` and an optional `FakeVoice`.

        Args:
            args: The command-line arguments.

        Returns:
            The `FakeEncoder` and the `FakeVoice` (if one was described).
        """
        return (cls(), FakeVoice.from_args(args))

    def list_voices(self) -> list[PresetVoice]:
        """The presets this encoder pretends to offer.

        Returns:
            The available `PresetVoice`s.
        """
        return [PresetVoice(voice_id='Fake', description='A fake voice.')]

    @classmethod
    def clone_voice(
        cls, ref_audio: str, entry: dict, args: Namespace
    ) -> Voice:
        """Builds the clone `FakeVoice` that `--adopt` writes into a voices
            file.

        Args:
            ref_audio: The path of the adopted reference clip.
            entry: The audition index entry for the adopted candidate.
            args: The command-line arguments.

        Returns:
            The clone `FakeVoice`.
        """
        return FakeVoice(
            ref_audio=ref_audio,
            seed=args.voice_seed if args.voice_seed is not None
            else entry.get('seed'),
            temperature=args.voice_temperature,
        )
