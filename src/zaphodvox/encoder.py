import re
from abc import ABC, abstractmethod
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from zaphodvox.audio import create_silence
from zaphodvox.manifest import Manifest
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
        total_chars = sum([len(s.text) for s in fragments])
        with ProgressBar('Encoding', total=total_chars) as bar:
            for fragment in fragments:
                if fragment.filename is not None:
                    filepath = Path(fragment.filename)
                    if encode_dir:
                        filepath = encode_dir / filepath.name
                    filepath = filepath.with_suffix(f'.{self.file_extension}')
                    if (duration := silence_duration) is None:
                        duration = fragment.silence_duration
                    if (num_chars := len(fragment.text)) > 0:
                        if duration:
                            fragment.text = re.sub(
                                r'(\n{2,})',
                                self.break_tag(duration),
                                fragment.text
                            )
                        if (not fragment.voice) and fragment.voice_name:
                            fragment.voice = voices.get(fragment.voice_name)
                        if fragment.voice is None:
                            raise ValueError('No voice specified.')
                        self.t2s(fragment.text, fragment.voice, filepath)
                        bar.next(n=num_chars)
                    elif duration:
                        create_silence(duration, filepath, self.file_extension)
                    fragment.encoded = datetime.now(timezone.utc)
                    fragment.filename = filepath.name
                    fragment.encoder = self.name
                    fragment.silence_duration = duration
                    fragment.audio_format = self.audio_format
        return manifest

    def break_tag(self, duration: int) -> Callable[[re.Match], str]:
        """Create a function to replace multiple newlines with a break tag.

        Args:
            duration: The duration of the break in milliseconds.

        Returns:
            A function that takes a `re.Match` object and returns a string.
        """

        def _break_tag(match: re.Match) -> str:
            """Replace multiple newlines with a break tag.

            Args:
                match: The `re.Match` object.

            Returns:
                The break tag string.
            """
            breaks = len(match.group(1)) - 1
            seconds = min(3.0, (breaks * duration) / 1000.0)
            return f' <break time="{seconds:.3f}s" /> '

        return _break_tag
