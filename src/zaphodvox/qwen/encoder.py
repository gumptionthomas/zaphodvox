from argparse import Namespace
from pathlib import Path
from typing import Optional

import requests
from tenacity import Retrying, stop_after_attempt

from zaphodvox.encoder import Encoder, PresetVoice
from zaphodvox.paths import abspath
from zaphodvox.qwen.voice import QwenVoice
from zaphodvox.voice import Voice

DEFAULT_URL = 'http://127.0.0.1:4123'
"""The default base URL of the Qwen3-TTS server."""

FILE_EXTENSIONS = {'wav': 'wav', 'mp3': 'mp3'}
"""The file extension for supported audio formats (`response_format`s)."""


class QwenEncoder(Encoder):
    """An `Encoder` subclass that uses a locally-hosted Qwen3-TTS server to
    convert text to speech and save it as an audio file.
    """

    name: Optional[str] = 'qwen'
    """The name of the Qwen3-TTS encoder."""

    def __init__(
        self,
        url: Optional[str] = None,
        audio_format: Optional[str] = None,
    ) -> None:
        """Initializes the `QwenEncoder` object.

        Args:
            url: The base URL of the Qwen3-TTS server. Defaults to
                `DEFAULT_URL`.
            audio_format: The audio format (`response_format`) to request.
                Defaults to `wav`.
        """
        self._url = (url or DEFAULT_URL).rstrip('/')
        """The base URL of the Qwen3-TTS server."""
        self._audio_format = audio_format or 'wav'
        """The audio format (`response_format`) to request."""

    @property
    def audio_format(self) -> str:
        """The audio format to be used.

        Returns:
            The audio format.
        """
        return self._audio_format

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files.

        Raises:
            ValueError: If the specified audio format is not supported.
        """
        file_ext = FILE_EXTENSIONS.get(self.audio_format)
        if not file_ext:
            raise ValueError(
                f'Audio format "{self.audio_format}" is not supported by '
                f'QwenEncoder. Use one of {list(FILE_EXTENSIONS.keys())}.'
            )
        return file_ext

    def validate_voice(self, voice: Voice) -> None:
        """Check that a clone voice's reference audio actually exists, before
        any encoding begins.

        Args:
            voice: The `Voice` to validate.

        Raises:
            ValueError: If `voice` is not a `QwenVoice`, or if it clones a
                reference audio file that cannot be found.
        """
        if not isinstance(voice, QwenVoice):
            raise ValueError('Not a QwenVoice.')
        ref_audio = voice.resolved_ref_audio
        if ref_audio is not None and not ref_audio.is_file():
            anchor = abspath(voice.base_dir or Path.cwd())
            raise ValueError(
                f'Reference audio "{voice.ref_audio}" not found at '
                f'"{abspath(ref_audio)}" (relative paths are resolved '
                f'against "{anchor}").'
            )

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to convert to speech.
            voice: The `QwenVoice` to use for the speech conversion.
            filepath: The `Path` of the generated audio file.

        Raises:
            ValueError: If `voice` is not a `QwenVoice`.
        """
        if not isinstance(voice, QwenVoice):
            raise ValueError('Not a QwenVoice.')
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
            with attempt:
                if voice.is_clone:
                    self._t2s_clone(text, voice, filepath)
                elif voice.is_design:
                    self._t2s_design(text, voice, filepath)
                else:
                    self._t2s_preset(text, voice, filepath)

    def _t2s_preset(
        self, text: str, voice: QwenVoice, filepath: Path
    ) -> None:
        """Synthesize a built-in preset voice via `POST /v1/audio/speech`.

        Args:
            text: The text to convert to speech.
            voice: The preset `QwenVoice` to use.
            filepath: The `Path` of the generated audio file.
        """
        payload: dict = {
            'input': text,
            'voice': voice.voice_id,
            'language': voice.language,
            'response_format': self.audio_format,
        }
        if voice.instruct:
            payload['instruct'] = voice.instruct
        if voice.seed is not None:
            payload['seed'] = voice.seed
        if voice.temperature is not None:
            payload['temperature'] = voice.temperature
        with requests.post(
            f'{self._url}/v1/audio/speech', json=payload
        ) as r:
            r.raise_for_status()
            filepath.write_bytes(r.content)

    def _t2s_clone(
        self, text: str, voice: QwenVoice, filepath: Path
    ) -> None:
        """Synthesize a cloned voice via `POST /v1/audio/speech/upload`.

        Args:
            text: The text to convert to speech.
            voice: The clone `QwenVoice` to use.
            filepath: The `Path` of the generated audio file.
        """
        ref_audio = voice.resolved_ref_audio
        assert ref_audio is not None
        data = {
            'input': text,
            'language': voice.language,
            'response_format': self.audio_format,
        }
        if voice.ref_text:
            data['ref_text'] = voice.ref_text
        else:
            data['x_vector_only'] = 'true'
        if voice.seed is not None:
            data['seed'] = str(voice.seed)
        if voice.temperature is not None:
            data['temperature'] = str(voice.temperature)
        with open(str(ref_audio), 'rb') as ref:
            with requests.post(
                f'{self._url}/v1/audio/speech/upload',
                data=data,
                files={'voice_file': ref},
            ) as r:
                r.raise_for_status()
                filepath.write_bytes(r.content)

    def _t2s_design(
        self, text: str, voice: QwenVoice, filepath: Path
    ) -> None:
        """Synthesize a designed voice via `POST /v1/audio/speech/design`.

        Args:
            text: The text to convert to speech.
            voice: The design `QwenVoice` to use.
            filepath: The `Path` of the generated audio file.
        """
        payload: dict = {
            'input': text,
            'voice_description': voice.description,
            'language': voice.language,
            'response_format': self.audio_format,
        }
        if voice.seed is not None:
            payload['seed'] = voice.seed
        if voice.temperature is not None:
            payload['temperature'] = voice.temperature
        with requests.post(
            f'{self._url}/v1/audio/speech/design', json=payload
        ) as r:
            r.raise_for_status()
            filepath.write_bytes(r.content)

    @classmethod
    def from_args(
        cls, args: Namespace
    ) -> tuple[Encoder, Optional[Voice]]:
        """Create an instance of `QwenEncoder` and an optional `QwenVoice`
        instance based on the provided arguments.

        Args:
            cls: The class object of the `QwenEncoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing the `QwenEncoder` instance and an optional
                `QwenVoice` instance.
        """
        encoder = cls(url=args.qwen_url, audio_format=args.qwen_audio_format)
        voice = QwenVoice.from_args(args)
        return (encoder, voice)

    def list_voices(self) -> list[PresetVoice]:
        """The built-in preset speakers the Qwen server offers.

        The server reports a lowercase `voice_id` but accepts the capitalized
        `name`, which is what the docs and `--voice-id` examples use.

        Returns:
            The available `PresetVoice`s.
        """
        with requests.get(f'{self._url}/v1/voices') as r:
            r.raise_for_status()
            voices = r.json().get('voices', [])
        return [
            PresetVoice(
                voice_id=v.get('name') or v.get('voice_id', ''),
                description=v.get('description', ''),
            )
            for v in voices
        ]

    @classmethod
    def clone_voice(
        cls, ref_audio: str, entry: dict, args: Namespace
    ) -> Voice:
        """Builds the clone `QwenVoice` that `--adopt` writes into the voices
        file.

        The candidate's own text becomes the clone's `ref_text`, so the adopted
        voice uses the higher-quality in-context (ICL) mode: we know exactly what
        was said in the clip, because we asked for it.

        Args:
            ref_audio: The path of the adopted reference clip.
            entry: The audition index entry for the adopted candidate.
            args: The command-line arguments.

        Returns:
            The clone `QwenVoice`.
        """
        source = entry.get('voice') or {}
        temperature = args.voice_temperature
        if temperature is None:
            temperature = source.get('temperature')
        seed = args.voice_seed
        if seed is None:
            seed = entry.get('seed')
        return QwenVoice(
            ref_audio=ref_audio,
            ref_text=entry.get('text'),
            language=source.get('language', 'English'),
            seed=seed,
            temperature=temperature,
        )
