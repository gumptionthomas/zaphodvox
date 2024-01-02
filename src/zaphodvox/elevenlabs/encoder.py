from argparse import Namespace
from pathlib import Path
from typing import Literal, Optional, Tuple, cast, get_args


from elevenlabs import History, generate, save, set_api_key
from elevenlabs import Voice as ELVoice
from tenacity import Retrying, stop_after_attempt

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.encoder import Encoder
from zaphodvox.progress import ProgressBar
from zaphodvox.voice import Voice


AudioFormat = Literal[
    'mp3_44100_64',
    'mp3_44100_96',
    'mp3_44100_128',
    'mp3_44100_192',
    'pcm_16000',
    'pcm_22050',
    'pcm_24000',
    'pcm_44100',
    'ulaw_8000',
]
"""The supported audio formats for the `ElevenLabsEncoder`."""

FILE_EXTENSIONS = {
    'mp3_44100_64': 'mp3',
    'mp3_44100_96': 'mp3',
    'mp3_44100_128': 'mp3',
    'mp3_44100_192': 'mp3',
    'pcm_16000': 'wav',
    'pcm_22050': 'wav',
    'pcm_24000': 'wav',
    'pcm_44100': 'wav',
    'ulaw_8000': 'wav',
}
"""The file extension for supported audio formats."""


class ElevenLabsEncoder(Encoder):
    """An `Encoder` subclass that uses the ElevenLabs Text-to-Speech API to
    convert text to speech and save it as an audio file.
    """

    def __init__(self,audio_format: Optional[AudioFormat] = None) -> None:
        """Initialize the `ElevenLabsEncoder` object.

        Args:
            audio_format: The audio format to be used.
                Defaults to `mp3_44100_128`.
        """
        self.audio_format = audio_format or 'mp3_44100_128'
        """The audio format to be used."""

    @property
    def file_extension(self) -> str:
        """The file extension for the output audio files.

        Raises:
            ValueError: If the specified audio format is not supported.
        """
        file_ext = FILE_EXTENSIONS.get(self.audio_format, None)
        if not file_ext:
            raise ValueError(
                f'Audio format "{self.audio_format}" is not supported by '
                f'ElevenLabsEncoder. Use one of {get_args(AudioFormat)}.'
            )
        return file_ext

    def t2s(self, text: str, voice: Voice, filepath: Path) -> None:
        """Convert text to speech using the specified voice and save it to the
        given filepath.

        Args:
            text: The text to convert to speech.
            voice: The `Voice` to use for the speech conversion.
            filepath: The `Path` of the generated audio file.
        """
        voice = cast(ElevenLabsVoice, voice)
        elevenlabs_voice = ELVoice(
            voice_id=voice.voice_id, settings=voice.voice_settings
        )
        generate_kwargs = {
            'text': text,
            'voice': elevenlabs_voice,
            'output_format': self.audio_format
        }
        if model := voice.model:
            generate_kwargs['model'] = model
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
            with attempt:
                save(generate(**generate_kwargs), str(filepath))

    @classmethod
    def delete_history(cls) -> None:
        """Delete all history items.

        This method retrieves the history items from the API, and then deletes
        each item one by one. It displays a progress bar to track the deletion
        progress.

        Args:
            cls: The class object of the Encoder.
        """
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(5)):
            with attempt:
                history_items = [i for i in History.from_api()]
                with ProgressBar(
                    'Deleting History', total=len(history_items)
                ) as bar:
                    for i in history_items:
                        i.delete()
                        bar.next()

    @classmethod
    def from_args(
        cls, args: Namespace
    ) -> Tuple['ElevenLabsEncoder', Optional[ElevenLabsVoice]]:
        """Create an instance of `ElevenLabsEncoder` and an optional
        `ElevenLabsVoice` instance based on the provided arguments.

        Args:
            cls: The class object of the `ElevenLabsEncoder`.
            args: The command-line arguments.

        Returns:
            A tuple containing an instance of the `ElevenLabsEncoder` class
                and an optional `ElevenLabsVoice` instance.
        """
        if args.api_key:
            set_api_key(args.api_key)
        encoder = cls(audio_format=args.elevenlabs_audio_format)
        voice = None
        if args.voice_id is not None:
            voice_model = args.voice_model
            model = 'eleven_' + voice_model if voice_model else None
            voice = ElevenLabsVoice(
                voice_id=args.voice_id,
                model=model,
                stability=args.voice_stability,
                similarity_boost=args.voice_similarity_boost,
                style=args.voice_style,
                use_speaker_boost=args.voice_use_speaker_boost
            )
        return (encoder, voice)
