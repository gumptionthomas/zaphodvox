from argparse import Namespace
from pathlib import Path
from typing import Literal, Optional, Tuple, cast, get_args

from google.cloud.texttospeech import (
    AudioEncoding,
    SynthesisInput,
    TextToSpeechClient,
)
from tenacity import Retrying, stop_after_attempt

from zaphodvox.encoder import Encoder
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.voice import Voice


AudioFormat = Literal[
    'linear16',
    'mp3_44100_32',
    'ogg_opus',
    'mulaw',
    'alaw',
]
"""The supported audio formats for the `GoogleEncoder`."""

AUDIO_INFO = {
    'linear16': ('wav', AudioEncoding.LINEAR16),
    'mp3_44100_32': ('mp3', AudioEncoding.MP3),
    'ogg_opus': ('ogg', AudioEncoding.OGG_OPUS),
    'mulaw': ('wav', AudioEncoding.MULAW),
    'alaw': ('wav', AudioEncoding.ALAW),
}
"""The file extension and `AudioEncoding` for supported audio formats."""


class GoogleEncoder(Encoder):
    """An `Encoder` subclass that uses the Google Text-to-Speech API to
    convert text to speech and save it as an audio file.
    """

    def __init__(
        self,
        service_account_filepath: Optional[Path] = None,
        audio_format: Optional[AudioFormat] = None
    ) -> None:
        """Initializes the GoogleEncoder object.

        Args:
            service_account_filepath: The `Path` to the service account file.
            audio_format: The audio format to be used.
                Defaults to `linear16`.
        """
        self.audio_format = audio_format or 'linear16'
        """The audio format to be used."""
        self._client: TextToSpeechClient
        """The Google `TextToSpeechClient`."""
        if service_account_filepath:
            self._client = TextToSpeechClient.from_service_account_file(
                str(service_account_filepath)
            )
        else:
            self._client = TextToSpeechClient()

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files.

        Raises:
            ValueError: If the specified audio format is not supported.
        """
        audio_info = AUDIO_INFO.get(self.audio_format, None)
        file_ext = audio_info[0] if audio_info else None
        if not file_ext:
            raise ValueError(
                f'Audio format "{self.audio_format}" is not supported by '
                f'GoogleEncoder. Use one of {get_args(AudioFormat)}.'
            )
        return file_ext

    @property
    def _audio_encoding(self) -> int:
        """The Google `AudioEncoding` enum value.

        Raises:
            ValueError: If the specified audio format is not supported.
        """
        audio_info = AUDIO_INFO.get(self.audio_format, None)
        encoding = audio_info[1] if audio_info else None
        if not encoding:
            raise ValueError(
                f'Audio format "{self.audio_format}" is not supported by '
                f'GoogleEncoder. Use one of {AUDIO_INFO.keys()}.'
            )
        return encoding

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to convert to speech.
            voice: The `Voice` to use for the speech synthesis.
            filepath: The `Path` of the generated audio file.
        """
        voice = cast(GoogleVoice, voice)
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
            with attempt:
                response = self._client.synthesize_speech(
                    request={
                        'input': SynthesisInput(text=text),
                        'voice': voice.voice_selection_params,
                        'audio_config': voice.get_audio_config(
                            self._audio_encoding
                        )
                    }
                )
                with open(str(filepath), 'wb') as out:
                    out.write(response.audio_content)

    @classmethod
    def from_args(
        cls, args: Namespace
    ) -> Tuple['GoogleEncoder', Optional[GoogleVoice]]:
        """Create an instance of the `GoogleEncoder` class and an optional
        `GoogleVoice` instance based on the provided arguments.

        Args:
            cls: The class object of the `GoogleEncoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing the `GoogleEncoder` instance and an optional
                `GoogleVoice` instance.
        """
        encoder = cls(
            service_account_filepath=args.service_account,
            audio_format=args.google_audio_format
        )
        voice = None
        if None not in [
            args.voice_id, args.voice_language,
            args.voice_region, args.voice_type
        ]:
            voice = GoogleVoice(
                voice_id=args.voice_id,
                language=args.voice_language,
                region=args.voice_region,
                type=args.voice_type,
                speaking_rate=args.voice_speaking_rate,
                pitch=args.voice_pitch,
                volume_gain_db=args.voice_volume_gain_db,
                sample_rate_hertz=args.voice_sample_rate_hertz,
                effects_profile_id=args.voice_effects_profile_id
            )
        return (encoder, voice)
