import os
from argparse import Namespace
from pathlib import Path
from typing import Optional

import requests
from tenacity import Retrying, stop_after_attempt

from zaphodvox.chatterbox.voice import ChatterboxVoice
from zaphodvox.encoder import Encoder
from zaphodvox.voice import Voice

DEFAULT_URL = 'http://127.0.0.1:8004'
"""The default base URL of the Chatterbox TTS server."""

FILE_EXTENSIONS = {'wav': 'wav', 'mp3': 'mp3', 'opus': 'opus'}
"""The file extension for each supported audio format."""


class ChatterboxEncoder(Encoder):
    """An `Encoder` that talks to a locally-hosted Chatterbox TTS server
    (https://github.com/devnen/Chatterbox-TTS-Server).

    A thin HTTP client, like `QwenEncoder`. Two differences worth knowing:

    It speaks the server's native `POST /tts` rather than the OpenAI-compatible
    `/v1/audio/speech`, which wants a meaningless `model` field and does its own
    text chunking -- `zaphodvox` has already decided where the fragments are, so
    `split_text` is off.

    Cloning is two requests, not one: the reference clip is uploaded to the
    server (`POST /upload_reference`) and then referred to by name. The upload is
    done once per clip and remembered, rather than re-sent with every fragment of
    a book.
    """

    name = 'chatterbox'

    def __init__(
        self, url: str = DEFAULT_URL, audio_format: str = 'wav'
    ) -> None:
        """Initializes a `ChatterboxEncoder`.

        Args:
            url: The base URL of the Chatterbox TTS server.
            audio_format: The audio format of the generated speech.
        """
        self._url = url.rstrip('/')
        self._audio_format = audio_format
        self._uploaded: dict[str, str] = {}

    @property
    def audio_format(self) -> str:
        """The audio format of the generated speech.

        Returns:
            The audio format.
        """
        return self._audio_format

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files.

        Returns:
            The file extension.

        Raises:
            ValueError: If the audio format is not supported.
        """
        file_ext = FILE_EXTENSIONS.get(self.audio_format)
        if not file_ext:
            raise ValueError(
                f'Audio format "{self.audio_format}" is not supported by '
                f'ChatterboxEncoder. Use one of {list(FILE_EXTENSIONS.keys())}.'
            )
        return file_ext

    def validate_voice(self, voice: Voice) -> None:
        """Check that a clone voice's reference audio actually exists, before
        any encoding begins.

        Args:
            voice: The `Voice` to validate.

        Raises:
            ValueError: If `voice` is not a `ChatterboxVoice`, or if it clones a
                reference audio file that cannot be found.
        """
        if not isinstance(voice, ChatterboxVoice):
            raise ValueError('Not a ChatterboxVoice.')
        ref_audio = voice.resolved_ref_audio
        if ref_audio is not None and not ref_audio.is_file():
            anchor = voice.base_dir or Path.cwd()
            raise ValueError(
                f'Reference audio "{voice.ref_audio}" not found at '
                f'"{ref_audio}" (relative paths are resolved against '
                f'"{anchor}").'
            )

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to convert to speech.
            voice: The `ChatterboxVoice` to use for the speech conversion.
            filepath: The `Path` of the generated audio file.

        Raises:
            ValueError: If `voice` is not a `ChatterboxVoice`.
        """
        if not isinstance(voice, ChatterboxVoice):
            raise ValueError('Not a ChatterboxVoice.')
        payload: dict = {
            'text': text,
            'output_format': self.audio_format,
            # zaphodvox has already decided where the fragments are; letting the
            # server split them again would fight the manifest.
            'split_text': False,
        }
        if voice.is_clone:
            payload['voice_mode'] = 'clone'
            payload['reference_audio_filename'] = self._reference(voice)
        else:
            payload['voice_mode'] = 'predefined'
            payload['predefined_voice_id'] = voice.voice_id
        for field in ('temperature', 'exaggeration', 'cfg_weight',
                      'speed_factor', 'seed'):
            value = getattr(voice, field)
            if value is not None:
                payload[field] = value
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
            with attempt:
                with requests.post(f'{self._url}/tts', json=payload) as r:
                    r.raise_for_status()
                    filepath.write_bytes(r.content)

    def _reference(self, voice: ChatterboxVoice) -> str:
        """The server-side filename of a clone voice's reference clip, uploading
        it the first time it is asked for.

        The server holds reference clips itself and refers to them by name, so a
        clip has to be sent before it can be cloned. It is sent once per clip,
        not once per fragment: a book is thousands of fragments and the clip does
        not change.

        Args:
            voice: The clone `ChatterboxVoice`.

        Returns:
            The reference clip's filename on the server.
        """
        ref_audio = voice.resolved_ref_audio
        assert ref_audio is not None
        key = str(ref_audio)
        if key not in self._uploaded:
            for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
                with attempt:
                    with open(str(ref_audio), 'rb') as ref:
                        with requests.post(
                            f'{self._url}/upload_reference',
                            files={'files': (ref_audio.name, ref)},
                        ) as r:
                            r.raise_for_status()
            self._uploaded[key] = ref_audio.name
        return self._uploaded[key]

    @classmethod
    def from_args(
        cls, args: Namespace
    ) -> tuple[Encoder, Optional[Voice]]:
        """Create an instance of `ChatterboxEncoder` and an optional
        `ChatterboxVoice` based on the provided arguments.

        Args:
            cls: The class object of the `ChatterboxEncoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing the `ChatterboxEncoder` instance and an optional
                `ChatterboxVoice` instance.
        """
        encoder = cls(
            url=args.chatterbox_url,
            audio_format=args.chatterbox_audio_format,
        )
        voice = ChatterboxVoice.from_args(args)
        return (encoder, voice)

    @classmethod
    def clone_voice(
        cls, ref_audio: str, entry: dict, args: Namespace
    ) -> Voice:
        """Builds the clone `ChatterboxVoice` that `--adopt` writes into the
        voices file.

        Args:
            ref_audio: The path of the adopted reference clip.
            entry: The audition index entry for the adopted candidate.
            args: The command-line arguments.

        Returns:
            The clone `ChatterboxVoice`.
        """
        source = entry.get('voice') or {}

        def setting(name: str, override: Optional[float]) -> Optional[float]:
            return override if override is not None else source.get(name)

        seed = args.voice_seed
        if seed is None:
            seed = entry.get('seed')
        return ChatterboxVoice(
            ref_audio=ref_audio,
            seed=seed,
            temperature=setting('temperature', args.voice_temperature),
            exaggeration=setting('exaggeration', args.voice_exaggeration),
            cfg_weight=setting('cfg_weight', args.voice_cfg_weight),
            speed_factor=setting('speed_factor', args.voice_speed),
        )


def default_url() -> str:
    """The base URL of the Chatterbox server, from the environment.

    Returns:
        The base URL.
    """
    return os.environ.get('ZAPHODVOX_CHATTERBOX_URL', DEFAULT_URL)
