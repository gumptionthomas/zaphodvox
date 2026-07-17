import os
from argparse import ArgumentParser, Namespace

from zaphodvox.chatterbox.encoder import DEFAULT_URL as CHATTERBOX_DEFAULT_URL
from zaphodvox.chatterbox.encoder import ChatterboxEncoder  # noqa: F401
from zaphodvox.chatterbox.encoder import default_url as chatterbox_url
from zaphodvox.encoder import Encoder
from zaphodvox.http import DEFAULT_READ_TIMEOUT, default_timeout
from zaphodvox.paths import expanded_path
from zaphodvox.qwen.encoder import DEFAULT_URL, QwenEncoder  # noqa: F401


def parse_args(args: list) -> Namespace:
    """Parses command-line arguments for `zaphodvox`.

    Args:
        args: The list of command-line arguments.

    Returns:
        The parsed command-line arguments.
    """

    parser = ArgumentParser(
        description=(
            'Encode a text file or manifest json file into synthetic speech '
            'audio file(s)'
        )
    )
    parser.add_argument(
        'inputfile',
        type=expanded_path,
        nargs='?',
        help=(
            'The text file or manifest to encode '
            '(e.g. "gone_bananas.txt" or "gone_bananas-manifest.json")'
        )
    )
    parser.add_argument(
        '-v',
        '--version',
        action='store_true',
        default=False,
        help='Print the version number and exit'
    )
    parser.add_argument(
        '-o',
        '--out-dir',
        type=expanded_path,
        default=None,
        help=(
            'The directory in which to save all files '
            '(default: the current directory)'
        )
    )
    parser.add_argument(
        '-e',
        '--encoder-name',
        choices=[e.name for e in Encoder.__subclasses__()],
        default=None,
        help='The name of the encoder to use'
    )
    parser.add_argument(
        '-f',
        '--voices-file',
        type=expanded_path,
        default=os.environ.get('ZAPHODVOX_VOICES_FILE'),
        help=(
            'A JSON file containing named voices; a relative voice '
            '"ref_audio" in it is resolved against its own directory, so it '
            'can be a shared library used from any project '
            '(default: $ZAPHODVOX_VOICES_FILE)'
        )
    )
    parser.add_argument(
        '-n',
        '--voice-name',
        default=None,
        help='The voice name in the `voices-file` to use'
    )
    parser.add_argument(
        '--clips-dir',
        type=expanded_path,
        default=os.environ.get('ZAPHODVOX_CLIPS_DIR'),
        help=(
            'The directory --adopt copies a reference clip into, created if '
            "needed; a relative path is taken from the --voices-file's own "
            'directory, so "clips" keeps a voices library tidy '
            '(default: $ZAPHODVOX_CLIPS_DIR, else beside the voices file)'
        )
    )
    parser.add_argument(
        '-m',
        '--max-chars',
        type=int,
        default=None,
        help=(
            'The maximum number of characters per fragment '
            '(default: one line per fragment)'
        )
    )
    parser.add_argument(
        '-s',
        '--silence-duration',
        type=int,
        default=None,
        help=(
            'The milliseconds of silence to use for empty strings '
            '(default: no silence)'
        )
    )
    parser.add_argument(
        '-b',
        '--basename',
        default=None,
        help=(
            'The basename of any output file(s) '
            '(default: [basename of inputfile] e.g. "gone_bananas")'
        )
    )
    parser.add_argument(
        '-i',
        '--indexes',
        default=None,
        help=(
            'The comma-delimited list of manifest audio file indexes '
            '(0-based, \'-\' delimited ranges) to encode '
            '(default: all indexes)'
        )
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=default_timeout(),
        metavar='SECONDS',
        help=(
            'How long to wait for a response from a TTS or LLM server before '
            'giving up and retrying; raise it if a first request has to load a '
            'model, lower it to notice a dead server sooner, or set 0 to wait '
            f'forever (default: $ZAPHODVOX_TIMEOUT or {DEFAULT_READ_TIMEOUT:g})'
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
        type=expanded_path,
        default=None,
        help=(
            'The clean text output file '
            '(default: [out-dir]/[basename]-clean.txt)'
        )
    )
    parser.add_argument(
        '--plan',
        action='store_true',
        default=False,
        help='Generate an encoding plan manifest for the input text'
    )
    parser.add_argument(
        '--plan-out',
        type=expanded_path,
        default=None,
        help=(
            'The encoding plan manifest output file '
            '(default: [out-dir]/[basename]-plan.txt)'
        )
    )
    parser.add_argument(
        '--encode',
        action='store_true',
        default=False,
        help='Encode the text to audio file(s)'
    )
    parser.add_argument(
        '--concat',
        action='store_true',
        default=False,
        help='Concatenate the encoded segment audio files into one audio file'
    )
    parser.add_argument(
        '--audition',
        default=None,
        metavar='SEEDS',
        help=(
            'Generate candidate reference clips of a preset --voice-id, a '
            '--voice-description, or a clone --voice-ref-audio (which re-clones '
            'it, to re-anchor a noisy recording to clean audio) for the given '
            'seeds to audition, specified like --indexes (e.g. "5", "1-5", '
            '"3,9,20")'
        )
    )
    parser.add_argument(
        '--audition-text',
        default=None,
        help=(
            'The sample sentence(s) to speak when auditioning '
            '(default: the first line of the inputfile)'
        )
    )
    parser.add_argument(
        '--list-voices',
        action='store_true',
        default=False,
        help="List the server's built-in preset voices and exit"
    )
    parser.add_argument(
        '--add-voice',
        default=None,
        metavar='NAME',
        help=(
            'Add (or update) the voice described by the --voice-* options to '
            '--voices-file under NAME; a reference clip from outside the '
            'library is copied into --clips-dir'
        )
    )
    parser.add_argument(
        '--adopt',
        type=int,
        default=None,
        metavar='SEED',
        help=(
            'Adopt the audition candidate with the given seed (from an '
            'audition index inputfile) as a clone voice named --voice-name '
            'in --voices-file'
        )
    )
    proof_group = parser.add_argument_group('proofing options')
    proof_group.add_argument(
        '--proof',
        action='store_true',
        default=False,
        help='Proofread the input text and write a report of issues'
    )
    proof_group.add_argument(
        '--proof-out',
        type=expanded_path,
        default=None,
        help=(
            'The proof report output file '
            '(default: [out-dir]/[basename]-proof.json)'
        )
    )
    proof_group.add_argument(
        '--dict',
        type=expanded_path,
        default=None,
        help=(
            'A project wordlist file of accepted spellings '
            '(default: [basename].dict)'
        )
    )
    proof_group.add_argument(
        '--add-word',
        nargs='+',
        default=None,
        metavar='WORD',
        help='Add word(s) to the --dict wordlist and exit'
    )
    proof_group.add_argument(
        '--dict-language',
        default='en',
        help='The spell-check dictionary language (default: en)'
    )
    proof_group.add_argument(
        '--llm-url',
        default=os.environ.get('ZAPHODVOX_LLM_URL'),
        help=(
            'Base URL of a local OpenAI-compatible LLM server (e.g. LM Studio) '
            'to add contextual proofreading (default: $ZAPHODVOX_LLM_URL; '
            'omit to skip the LLM pass)'
        )
    )
    proof_group.add_argument(
        '--llm-model',
        default=os.environ.get('ZAPHODVOX_LLM_MODEL'),
        help=(
            'The LLM model id to use (default: $ZAPHODVOX_LLM_MODEL, else the '
            "server's loaded model)"
        )
    )
    parser.add_argument(
        '--concat-out',
        type=expanded_path,
        default=None,
        help=(
            'The concatenated audio output file '
            '(default: [out-dir]/[basename].[wav|mp3])'
        )
    )
    parser.add_argument(
        '--no-manifest',
        action='store_false',
        dest='save_manifest',
        default=True,
        help='Do not create a manifest file'
    )
    parser.add_argument(
        '--manifest-out',
        type=expanded_path,
        default=None,
        help=(
            'The manifest output file (default: '
            '[path of inputfile] if inputfile is a manifest, '
            'otherwise [out-dir]/[basename]-manifest.json)'
        )
    )
    parser.add_argument(
        '--voice-id',
        default=None,
        help='The built-in preset voice/speaker to use (e.g. "Ryan")'
    )
    qwen_group = parser.add_argument_group(
        'qwen options',
        description=(
            'Qwen3-TTS options (a locally-hosted Qwen3-TTS server, e.g. '
            'https://github.com/gumptionthomas/eddie-tts)'
        )
    )
    qwen_group.add_argument(
        '--voice-language',
        default='English',
        help='The language of the text (default: English)'
    )
    qwen_group.add_argument(
        '--voice-instruct',
        default=None,
        help='An optional style/emotion direction for a preset voice'
    )
    qwen_group.add_argument(
        '--voice-ref-audio',
        type=expanded_path,
        default=None,
        help='A reference audio file to clone (instead of a preset --voice-id)'
    )
    qwen_group.add_argument(
        '--voice-description',
        default=None,
        help=(
            'A natural-language description of a voice to design '
            '(e.g. "a warm elderly woman"), instead of --voice-id/--voice-ref-audio'
        )
    )
    qwen_group.add_argument(
        '--voice-ref-text',
        default=None,
        help=(
            'The transcript of --voice-ref-audio for higher-quality (ICL) '
            'cloning (default: zero-shot clone with no transcript)'
        )
    )
    qwen_group.add_argument(
        '--voice-seed',
        type=int,
        default=None,
        help=(
            'A fixed RNG seed for reproducible synthesis; keeps the voice '
            'consistent across chunks (default: non-deterministic)'
        )
    )
    qwen_group.add_argument(
        '--voice-temperature',
        type=float,
        default=None,
        help=(
            'The sampling temperature; run-to-run variability, not '
            'expressiveness (lower is steadier, higher is more varied; '
            'default: the server default)'
        )
    )
    qwen_group.add_argument(
        '--qwen-url',
        default=os.environ.get('ZAPHODVOX_QWEN_URL', DEFAULT_URL),
        help=(
            'The base URL of the Qwen3-TTS server '
            f'(default: $ZAPHODVOX_QWEN_URL or {DEFAULT_URL})'
        )
    )
    qwen_group.add_argument(
        '--qwen-audio-format',
        choices=['wav', 'mp3'],
        default='wav',
        help='The audio output format (default: wav)'
    )
    cb_group = parser.add_argument_group(
        'chatterbox options',
        description=(
            'Chatterbox options (a locally-hosted Chatterbox TTS server, '
            'https://github.com/devnen/Chatterbox-TTS-Server). Chatterbox has '
            'no voice design and no in-context cloning, and steers delivery '
            'numerically rather than with --voice-instruct.'
        )
    )
    cb_group.add_argument(
        '--voice-exaggeration',
        type=float,
        default=None,
        help=(
            'How expressive the delivery is (0.25-2.0); unlike '
            '--voice-temperature this really is an expressiveness dial '
            '(default: the server default)'
        )
    )
    cb_group.add_argument(
        '--voice-cfg-weight',
        type=float,
        default=None,
        help=(
            'How closely the delivery follows the reference voice, at the cost '
            'of expressiveness (default: the server default)'
        )
    )
    cb_group.add_argument(
        '--voice-speed',
        type=float,
        default=None,
        help=(
            'How fast the speech is, as a multiple of normal pace '
            '(default: the server default)'
        )
    )
    cb_group.add_argument(
        '--chatterbox-url',
        default=chatterbox_url(),
        help=(
            'The base URL of the Chatterbox TTS server '
            f'(default: $ZAPHODVOX_CHATTERBOX_URL or {CHATTERBOX_DEFAULT_URL})'
        )
    )
    cb_group.add_argument(
        '--chatterbox-audio-format',
        choices=['wav', 'mp3', 'opus'],
        default='wav',
        help='The audio output format (default: wav)'
    )

    return parser.parse_args(args)
