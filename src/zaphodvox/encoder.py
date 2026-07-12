import re
from abc import ABC, abstractmethod
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zaphodvox.audio import AudioParams, audio_params, create_silence
from zaphodvox.manifest import Fragment, Manifest
from zaphodvox.progress import ProgressBar
from zaphodvox.voice import Voice


class Encoder(ABC):
    """The Encoder class is responsible for converting text to speech using
    different voices and saving the audio files.
    """

    name: Optional[str] = None
    """The name of the encoder."""

    @property
    @abstractmethod
    def audio_format(self) -> str:
        """The audio format to be used.

        Returns:
            The audio format.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """The file extension for the output audio files.

        Returns:
            The file extension.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_args(
        cls, args: Namespace
    ) -> tuple['Encoder', Optional[Voice]]:
        """Create an instance of the `Encoder` class and an optional
        `Voice` instance based on the provided arguments.

        Args:
            cls: The class object of the `Encoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing the `Encoder` instance and an optional
                `Voice` instance.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def clone_voice(
        cls, ref_audio: str, entry: dict, args: Namespace
    ) -> Voice:
        """Builds the `Voice` that `--adopt` writes into the voices file: a
        clone of an audition candidate.

        Args:
            ref_audio: The path of the adopted reference clip.
            entry: The audition index entry for the adopted candidate. Its
                `voice` key holds the settings of the voice that produced it.
            args: The command-line arguments, whose `--voice-*` options override
                what the audition recorded.

        Returns:
            The clone `Voice`.
        """
        raise NotImplementedError

    @abstractmethod
    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to be converted to speech.
            voice: The `Voice` to be used for the speech conversion.
            filepath: The `Path` of the generated audio file.
        """
        raise NotImplementedError

    @staticmethod
    def fragment_voice(
        fragment: Fragment, voices: dict[str, Optional[Voice]]
    ) -> Voice:
        """Resolve the `Voice` a fragment will be spoken with: its own inline
        voice, else the named voice it refers to.

        Args:
            fragment: The `Fragment` to resolve a `Voice` for.
            voices: A dictionary of name/`Voice` pairs.

        Returns:
            The `Voice` for the fragment.

        Raises:
            ValueError: If the fragment has no voice.
        """
        voice = fragment.voice
        if (not voice) and fragment.voice_name:
            voice = voices.get(fragment.voice_name)
        if voice is None:
            raise ValueError('No voice specified.')
        return voice

    def validate_voice(self, voice: Voice) -> None:
        """Check that a `Voice` can actually be synthesized, before any encoding
        begins. The default accepts every voice; subclasses override to verify
        whatever they depend on (a reference audio file, say).

        Args:
            voice: The `Voice` to validate.

        Raises:
            ValueError: If the voice cannot be used.
        """
        return None

    def encode_manifest(
        self, manifest: Manifest, encode_dir: Optional[Path] = None,
        indexes: Optional[list[int]] = None,
        voices: Optional[dict[str, Optional[Voice]]] = None,
        silence_duration: Optional[int] = None
    ) -> Manifest:
        """Encodes the given `Manifest` into audio files and saves them to the
        specified directory.

        Args:
            manifest: The `Manifest` to be encoded.
            encode_dir: The directory `Path` where the audio files will be
                saved.
            indexes: The list of indexes of the `SpeechAudioFile` objects
                to encode. Defaults to `None` which indicates all objects.
            voices: A dictionary of name/`Voice` pairs.
            silence_duration: The duration of silence in milliseconds.

        Returns:
            The `Manifest` with the encoded fragments info.
        """
        voices = voices or {}
        indexes = indexes or list(range(manifest.length))
        fragments = [manifest.fragments[i] for i in indexes]
        # Resolve and check every voice up front: a bad reference should fail
        # on the command line, not two hundred fragments into a long encode.
        for fragment in fragments:
            if fragment.filename is not None and fragment.text:
                self.validate_voice(self.fragment_voice(fragment, voices))
        total_chars = sum([len(s.text) for s in fragments])
        silences: list[tuple[int, Path]] = []
        with ProgressBar('Encoding', total=total_chars) as bar:
            for fragment in fragments:
                if fragment.filename is not None:
                    filepath = self.fragment_path(fragment.filename, encode_dir)
                    if (duration := silence_duration) is None:
                        duration = fragment.silence_duration
                    if (num_chars := len(fragment.text)) > 0:
                        if duration:
                            fragment.text = re.sub(
                                r'(\n{2,})',
                                self.break_tag(duration),
                                fragment.text
                            )
                        fragment.voice = self.fragment_voice(fragment, voices)
                        self.t2s(fragment.text, fragment.voice, filepath)
                        bar.next(n=num_chars)
                    elif duration:
                        # Held back until the speech exists to copy the sample
                        # format from -- see `silence_params()`.
                        silences.append((duration, filepath))
                    fragment.encoded = datetime.now(timezone.utc)
                    fragment.filename = filepath.name
                    fragment.encoder = self.name
                    fragment.silence_duration = duration
                    fragment.audio_format = self.audio_format
        if silences:
            params = self.silence_params(manifest, encode_dir)
            for duration, filepath in silences:
                create_silence(
                    duration, filepath, self.file_extension, params
                )
        return manifest

    def fragment_path(
        self, filename: str, encode_dir: Optional[Path] = None
    ) -> Path:
        """The `Path` a fragment's audio is written to.

        Args:
            filename: The fragment's file name.
            encode_dir: The directory `Path` the audio files are saved to.

        Returns:
            The `Path` of the fragment's audio file.
        """
        filepath = Path(filename)
        if encode_dir:
            filepath = encode_dir / filepath.name
        return filepath.with_suffix(f'.{self.file_extension}')

    def silence_params(
        self, manifest: Manifest, encode_dir: Optional[Path] = None
    ) -> Optional[AudioParams]:
        """The sample format to write silent fragments in: that of the speech
        they will sit between.

        Only the server knows what it returns audio as, so the answer is read
        off a fragment it has already produced. Matching it is what lets the
        whole book be concatenated by copying samples through untouched, rather
        than decoding and resampling every fragment.

        Args:
            manifest: The `Manifest` being encoded.
            encode_dir: The directory `Path` the audio files are saved to.

        Returns:
            The `AudioParams` of the first encoded speech fragment, or `None` if
            there is no speech to copy them from.
        """
        for fragment in manifest.fragments:
            if fragment.text and fragment.filename:
                filepath = self.fragment_path(fragment.filename, encode_dir)
                if filepath.is_file():
                    return audio_params(filepath)
        return None

    def break_tag(self, duration: int) -> Callable[[re.Match], str]:
        """Create a function to replace multiple newlines with plain-text
        pauses. The default renders paragraph breaks as sentence stops, which
        suits plain-text engines; subclasses may override to emit SSML.

        Args:
            duration: The duration of the break in milliseconds (unused by the
                default; pauses are expressed as sentence stops).

        Returns:
            A function that takes a `re.Match` object and returns a string.
        """

        def _break_tag(match: re.Match) -> str:
            """Replace multiple newlines with plain-text sentence stops.

            Args:
                match: The `re.Match` object.

            Returns:
                The pause string.
            """
            return ' . ' * (len(match.group(1)) - 1)

        return _break_tag
