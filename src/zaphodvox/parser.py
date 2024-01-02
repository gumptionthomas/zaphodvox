from argparse import Action, ArgumentParser, BooleanOptionalAction, Namespace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, get_args

from pydantic import BaseModel

from zaphodvox.elevenlabs.encoder import AudioFormat as ElevenLabsAudioFormat
from zaphodvox.elevenlabs.encoder import ElevenLabsEncoder
from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.encoder import Encoder
from zaphodvox.googlecloud.encoder import AudioFormat as GoogleAudioFormat
from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.voice import Voice


class NamedVoicesConfiguration(BaseModel):
    """A named voice configuration."""

    google: Optional[GoogleVoice] = None
    """A `GoogleVoice` configuration."""
    elevenlabs: Optional[ElevenLabsVoice] = None
    """An `ElevenLabsVoice` configuration."""


class NamedVoices(BaseModel):
    """A dictionary of named voice configurations."""

    voices: Dict[str, NamedVoicesConfiguration]
    """The named voice configurations."""


def parse_voices(
    encoder: Encoder, filepath: Path
) -> Dict[str, Optional[Voice]]:
    """Parses the named voices for the encoder from the given JSON file.

    Args:
        encoder: The `Encoder` instance.
        filepath: The `Path` to the JSON file.

    Returns:
        The name/`Voice` pairs for the `encoder`.
    """
    voices: Dict[str, Optional[Voice]] = {}
    with open(str(filepath), 'r') as f:
        voices_json = f.read()
    named_voices = NamedVoices.model_validate_json(voices_json)
    if isinstance(encoder, GoogleEncoder):
        voices = {k: v.google for k, v in named_voices.voices.items()}
    if isinstance(encoder, ElevenLabsEncoder):
        voices = {k: v.elevenlabs for k, v in named_voices.voices.items()}
    return voices


def parse_args(args: list) -> Namespace:
    """Parses command-line arguments for `zaphodvox`.

    Args:
        args: The list of command-line arguments.

    Returns:
        The parsed command-line arguments.
    """
    class ScalarAction(Action):
        """Custom action class for handling scalar values.

        This class validates that the provided value is within the range of
        0.0 to 1.0. If the value is outside this range, it raises an error.

        Args:
            parser (ArgumentParser): The argument parser object.
            namespace (Namespace): The namespace object.
            values (Optional[str | Sequence[Any]]): The value(s) provided for
                the action.
            option_string (Optional[str]): The option string associated with
                the action.

        Raises:
            ArgumentTypeError: If the value is outside the range of 0.0 to 1.0.
        """
        def __call__(
            self, parser: ArgumentParser, namespace: Namespace,
            values: Optional[str | Sequence[Any]],
            option_string: Optional[str] = None
        ) -> None:
            if values is not None and float(str(values)) < 0.0:
                parser.error(f'Minimum value for {option_string} is 0.0')
            if values is not None and float(str(values)) > 1.0:
                parser.error(f'Maximum value for {option_string} is 1.0')
            setattr(namespace, self.dest, values)

    parser = ArgumentParser(
        description='Encode a text file to synthetic speech audio file(s)'
    )
    parser.add_argument(
        'textfile',
        type=Path,
        help='The textfile to encode (e.g. "gone_bananas.txt")'
    )
    parser.add_argument(
        '--encoder',
        choices=['google', 'elevenlabs'],
        default='google',
        help='The encoder to use (default: google)'
    )
    parser.add_argument(
        '--voices',
        type=Path,
        default=None,
        help='A JSON file containing named voices'
    )
    parser.add_argument(
        '--voice-id',
        default=None,
        help='The voice ID to use'
    )
    parser.add_argument(
        '--max-chars',
        type=int,
        default=None,
        help=(
            'The maximum number of characters per block '
            '(default: one block per line)'
        )
    )
    parser.add_argument(
        '--silence-duration',
        type=int,
        default=500,
        help=(
            'The milliseconds of silence to use for empty strings '
            '(default: 500)'
        )
    )
    parser.add_argument(
        '--basename',
        default=None,
        help=(
            'The basename of any output file(s) '
            '(default: <basename of textfile> e.g. "gone_bananas")'
        )
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        default=False,
        help='Clean the input text (before encoding) and write to file'
    )
    parser.add_argument(
        '--clean-out',
        type=Path,
        default=None,
        help='The clean text output file (default: [basename]-clean.txt)'
    )
    parser.add_argument(
        '--encode',
        action='store_true',
        default=False,
        help='Encode the text to audio file(s)'
    )
    parser.add_argument(
        '--copy',
        action='store_true',
        default=False,
        help='Copy the encoded segment files to the working directory'
    )
    parser.add_argument(
        '--concat',
        action='store_true',
        default=False,
        help='Concatenate the encoded segment files into one audio file'
    )
    parser.add_argument(
        '--concat-out',
        type=Path,
        default=None,
        help=(
            'The concatenated audio output file '
            '(default: [basename].[wav|ogg|mp3])'
        )
    )
    parser.add_argument(
        '--no-manifest',
        action='store_false',
        dest='manifest',
        default=True,
        help='Do not create a manifest file'
    )
    parser.add_argument(
        '--manifest-out',
        type=Path,
        default=None,
        help=(
            'The manifest output file '
            '(default: [basename]-manifest.json)'
        )
    )
    google_group = parser.add_argument_group(
        'google options',
        description=(
            'Google Text-to-Speech options '
            '(see: https://cloud.google.com/text-to-speech/docs)'
        )
    )
    google_group.add_argument(
        '--voice-language',
        default='en',
        help='The Google language to use (default: en)'
    )
    google_group.add_argument(
        '--voice-region',
        default='US',
        help='The Google language region to use (default: US)'
    )
    google_group.add_argument(
        '--voice-type',
        default='Wavenet',
        help='The Google voice type to use (default: Wavenet)'
    )
    google_group.add_argument(
        '--voice-speaking-rate',
        type=float,
        default=None,
        help='The Google speaking rate'
    )
    google_group.add_argument(
        '--voice-pitch',
        type=float,
        default=None,
        help='The Google pitch'
    )
    google_group.add_argument(
        '--voice-volume-gain-db',
        type=float,
        default=None,
        help='The Google volume gain'
    )
    google_group.add_argument(
        '--voice-sample-rate-hertz',
        type=int,
        default=None,
        help='The Google sample rate in hertz'
    )
    google_group.add_argument(
        '--voice-effects-profile-id',
        nargs='+',
        default=None,
        help='The Google effects profile ID(s)'
    )
    google_group.add_argument(
        '--google-audio-format',
        choices=get_args(GoogleAudioFormat),
        default='linear16',
        help='The Google audio output format (default: linear16)'
    )
    google_group.add_argument(
        '--service-account',
        type=Path,
        default=None,
        help='The service account file to use for Google auth'
    )
    eleven_group = parser.add_argument_group(
        'elevenlabs options',
        description=(
            'ElevenLabs Text-to-Speech options '
            '(see: https://elevenlabs.io/docs)'
        )
    )
    eleven_group.add_argument(
        '--voice-model',
        choices=['multilingual_v2', 'monolingual_v1'],
        default='multilingual_v2',
        help='The ElevenLabs model to use (default: multilingual_v2)'
    )
    eleven_group.add_argument(
        '--voice-stability',
        type=float,
        action=ScalarAction,
        default=None,
        help='The ElevenLabs voice stability'
    )
    eleven_group.add_argument(
        '--voice-similarity-boost',
        type=float,
        action=ScalarAction,
        default=None,
        help='The ElevenLabs voice similarity boost'
    )
    eleven_group.add_argument(
        '--voice-style',
        type=float,
        action=ScalarAction,
        default=None,
        help='The ElevenLabs voice style'
    )
    eleven_group.add_argument(
        '--voice-use-speaker-boost',
        type=bool,
        action=BooleanOptionalAction,
        default=None,
        help='Use ElevenLabs voice speaker boost'
    )
    eleven_group.add_argument(
        '--elevenlabs-audio-format',
        choices=get_args(ElevenLabsAudioFormat),
        default='mp3_44100_128',
        help='The ElevenLabs audio output format (default: mp3_44100_128)'
    )
    eleven_group.add_argument(
        '--delete-history',
        action='store_true',
        default=False,
        help='Delete all history items after encoding'
    )
    eleven_group.add_argument(
        '--api-key',
        default=None,
        help='The API key to use for ElevenLabs auth'
    )
    return parser.parse_args(args)
