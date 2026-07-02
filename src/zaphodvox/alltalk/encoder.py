from argparse import Namespace
from pathlib import Path
import re
from typing import Callable, Optional

import requests

from zaphodvox.alltalk.voice import AllTalkVoice
from zaphodvox.encoder import Encoder
from zaphodvox.voice import Voice


API_ADDRESS = 'http://gardner.local:7851'


class AllTalkEncoder(Encoder):
    """An `Encoder` subclass that uses the AllTalk TTS API to
    convert text to speech and save it as an audio file.
    """

    name: Optional[str] = 'alltalk'
    """The name of the AllTalk TTS encoder."""

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files."""
        return 'wav'

    @property
    def audio_format(self) -> str:
        """The audio format to be used.

        Returns:
            The audio format.
        """
        return 'wav'

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to convert to speech.
            voice: The `Voice` to use for the speech conversion.
            filepath: The `Path` of the generated audio file.
        """
        if not isinstance(voice, AllTalkVoice):
            raise ValueError('Not an AllTalkVoice.')

        with requests.post(
            f'{API_ADDRESS}/api/tts-generate',
            data={
                'text_input': text,
                'character_voice_gen': voice.voice_id,
                'language': voice.language_code,
            }
        ) as r:
            r.raise_for_status()
            response = r.json()
            if response['status'] != 'generate-success':
                raise ValueError(f"Unsuccessful: {response['status']}")

        with requests.get(
            f"{API_ADDRESS}{response['output_file_url']}", stream=True
        ) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

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
            return ' . ' * (len(match.group(1)) - 1)

        return _break_tag

    @classmethod
    def from_args(
        cls, args: Namespace
    ) -> tuple[Encoder, Optional[Voice]]:
        """Create an instance of `AllTalkEncoder` and an optional
        `AllTalkVoice` instance based on the provided arguments.

        Args:
            cls: The class object of the `AllTalkEncoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing an instance of the `AllTalkEncoder` class
                and an optional `AllTalkVoice` instance.
        """
        return (cls(), AllTalkVoice.from_args(args))
