from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import pytest

from zaphodvox.arg_parser import parse_args
from zaphodvox.qwen.encoder import DEFAULT_URL


class TestArgParser():
    def test_defaults(self):
        args = parse_args(['test.txt'])

        # General
        assert args.inputfile == Path('test.txt')
        assert args.version is False
        assert args.out_dir is None
        assert args.encoder_name is None
        assert args.voices_file is None
        assert args.voice_name is None
        assert args.voice_id is None
        assert args.max_chars is None
        assert args.silence_duration is None
        assert args.basename is None
        assert args.indexes is None
        assert not args.clean
        assert not args.plan
        assert not args.encode
        assert not args.concat
        assert args.concat_out is None
        assert args.save_manifest is True
        assert args.manifest_out is None
        # Qwen
        assert args.voice_language == 'English'
        assert args.voice_instruct is None
        assert args.voice_ref_audio is None
        assert args.voice_ref_text is None
        assert args.voice_description is None
        assert args.voice_seed is None
        assert args.voice_temperature is None
        assert args.qwen_url == DEFAULT_URL
        assert args.qwen_audio_format == 'wav'
        # Proofing
        assert args.proof is False
        assert args.proof_out is None
        assert args.dict is None
        assert args.add_word is None
        assert args.dict_language == 'en'
        assert args.llm_url is None
        assert args.llm_model is None

    def test_llm_model_from_env(self, monkeypatch):
        monkeypatch.setenv('ZAPHODVOX_LLM_MODEL', 'qwen2.5-7b-instruct')
        args = parse_args(['--proof', 'book.txt'])
        assert args.llm_model == 'qwen2.5-7b-instruct'
        # An explicit flag still wins.
        args = parse_args(['--proof', '--llm-model=other', 'book.txt'])
        assert args.llm_model == 'other'

    def test_encoder_choice(self):
        args = parse_args(['--encoder=qwen', 'test.txt'])
        assert args.encoder_name == 'qwen'

    def test_qwen_options(self):
        sys_args = [
            '--voice-id=Serena',
            '--voice-language=Chinese',
            '--voice-instruct=calm, wry',
            '--voice-ref-audio=ref.wav',
            '--voice-ref-text=hello',
            '--voice-seed=42',
            '--voice-temperature=0.6',
            '--qwen-url=http://localhost:9999',
            '--qwen-audio-format=mp3',
            'test.txt',
        ]
        args = parse_args(sys_args)
        assert args.voice_id == 'Serena'
        assert args.voice_language == 'Chinese'
        assert args.voice_instruct == 'calm, wry'
        assert args.voice_ref_audio == Path('ref.wav')
        assert args.voice_ref_text == 'hello'
        assert args.voice_seed == 42
        assert args.voice_description is None
        assert args.voice_temperature == 0.6
        assert args.qwen_url == 'http://localhost:9999'
        assert args.qwen_audio_format == 'mp3'

    def test_invalid_encoder_choice(self):
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(['--encoder=google', 'test.txt'])

    def test_invalid_audio_format(self):
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(['--qwen-audio-format=ogg', 'test.txt'])


class TestTildeExpansion():
    """The shell expands a leading `~` in only some of the spellings people
    actually use, so the parser has to handle the rest itself.
    """

    @pytest.fixture
    def fake_home(self, tmp_path, monkeypatch) -> Path:
        monkeypatch.setenv('HOME', str(tmp_path))
        monkeypatch.setenv('USERPROFILE', str(tmp_path))
        return tmp_path

    def test_tilde_in_joined_option_is_expanded(self, fake_home):
        # `--out-dir ~/voices` is expanded by the shell, but `--out-dir=~/voices`
        # is not -- and would otherwise create a directory named `~`.
        args = parse_args([
            '--out-dir=~/voices',
            '--voice-ref-audio=~/clips/narrator.wav',
            '~/book.txt',
        ])

        assert args.out_dir == fake_home / 'voices'
        assert args.voice_ref_audio == fake_home / 'clips' / 'narrator.wav'
        assert args.inputfile == fake_home / 'book.txt'

    def test_tilde_from_env_var_default_is_expanded(
        self, fake_home, monkeypatch
    ):
        # A quoted assignment (ZAPHODVOX_VOICES_FILE="~/...") reaches us with the
        # tilde intact, because the shell only expands an unquoted one.
        monkeypatch.setenv(
            'ZAPHODVOX_VOICES_FILE', '~/voices/voices.json'
        )

        args = parse_args(['book.txt'])

        assert args.voices_file == fake_home / 'voices' / 'voices.json'

    def test_ordinary_paths_are_untouched(self, fake_home):
        args = parse_args(['--out-dir=out', 'book.txt'])

        assert args.out_dir == Path('out')
        assert args.inputfile == Path('book.txt')
