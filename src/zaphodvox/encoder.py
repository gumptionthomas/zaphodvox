from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from zaphodvox.audio import create_silence
from zaphodvox.manifest import Manifest
from zaphodvox.progress import ProgressBar
from zaphodvox.voice import Voice


class Encoder(ABC):
    """The Encoder class is responsible for converting text to speech using
    different voices and saving the audio files.
    """

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
        self, manifest: Manifest, encode_dir: Path,
        indexes: Optional[list[int]]=None,
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
        """
        voices = voices or {}
        indexes = indexes or list(range(len(manifest.fragments)))
        fragments = [manifest.fragments[i] for i in indexes]
        total_chars = sum([len(s.text) for s in fragments])
        with ProgressBar('Encode', total=total_chars) as bar:
            for fragment in fragments:
                if fragment.filename is not None:
                    filepath = encode_dir.joinpath(fragment.filename)
                    filepath = filepath.with_suffix(f'.{self.file_extension}')
                    duration = fragment.silence_duration
                    if silence_duration is not None:
                        duration = silence_duration
                    if (num_chars := len(fragment.text)) > 0:
                        named_voice = None
                        if fragment.voice_name:
                            named_voice = voices.get(fragment.voice_name)
                        voice = fragment.voice or named_voice
                        if voice is None:
                            raise ValueError('No voice specified.')
                        self.t2s(fragment.text, voice, filepath)
                        fragment.voice = voice
                        bar.next(n=num_chars)
                    elif duration:
                        create_silence(duration, filepath, self.file_extension)
                    fragment.encoded = datetime.now(timezone.utc)
                    fragment.filename = filepath.name
                    fragment.encoder = self.__class__.__name__
                    fragment.audio_format = self.audio_format
        return manifest
