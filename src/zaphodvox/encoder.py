from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from zaphodvox.audio import create_silence
from zaphodvox.manifest import Manifest, SpeechAudioFile
from zaphodvox.progress import ProgressBar
from zaphodvox.text import parse_text
from zaphodvox.voice import Voice


class Encoder(ABC):
    """The Encoder class is responsible for converting text to speech using
    different voices and saving the audio files.
    """

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

    def encode(
        self, text: str, basename: str, path: Path,
        voice: Optional[Voice] = None,
        voices: Optional[Dict[str, Optional[Voice]]] = None,
        max_chars: Optional[int] = None,
        silence_duration: Optional[int] = None
    ) -> Manifest:
        """Encodes the given text into audio files using the specified
            default `Voice` and saves them to the specified path.

        Args:
            text: The text to be encoded.
            basename: The base name for the output audio files.
            path: The directory `Path` where the audio files will be saved.
            voice: The default `Voice` to be used for encoding.
            voices: A dictionary of name/`Voice` pairs.
            max_chars: The maximum number of characters per block. Defaults to
                `None` which indicates one block per line.
            silence_duration: The duration of the silence in seconds for empty
                lines. Defaults to `None` which indicates no silence.

        Returns:
            A `Manifest` object containing the list of `SpeechAudioFile` objects
            that were created.
        """
        text_blocks = parse_text(
            text, voice=voice, voices=voices, max_chars=max_chars
        )
        total_chars = sum([len(p[0]) for p in text_blocks])
        file_ext = self.file_extension
        manifest = Manifest(speech_audio_files=[])
        with ProgressBar('Encode', total=total_chars) as bar:
            for i, (block_text, block_voice) in enumerate(text_blocks):
                filepath = path.joinpath(f'{basename}-{i:05}.{file_ext}')
                if (num_chars := len(block_text)) > 0:
                    self.t2s(block_text, block_voice, filepath)
                    bar.next(n=num_chars)
                elif silence_duration:
                    create_silence(silence_duration, filepath, file_ext)
                manifest.speech_audio_files.append(
                    SpeechAudioFile(
                        text=block_text,
                        filename=filepath.name,
                        voice=block_voice if block_text else None,
                        silence_duration=(
                            silence_duration if not block_text else None
                        )
                    )
                )
        return manifest
