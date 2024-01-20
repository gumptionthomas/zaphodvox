from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

import pytest
from zaphodvox.parser import parse_args


class TestArgParser():
    def test_defaults(self):
        args = parse_args(['test.txt'])

        # General
        assert args.inputfile == Path('test.txt')
        assert args.encoder is None
        assert args.voices_file is None
        assert args.voice_id is None
        assert args.max_chars is None
        assert args.silence_duration == 500
        assert args.basename is None
        assert not args.clean
        assert not args.encode
        assert not args.copy
        assert args.copy_dir is None
        assert not args.concat
        assert args.concat_out is None
        assert args.manifest is True
        assert args.manifest_out is None
        assert not args.delete_history
        # Google
        assert args.voice_language == 'en'
        assert args.voice_region == 'US'
        assert args.voice_type == 'Wavenet'
        assert args.voice_speaking_rate is None
        assert args.voice_pitch is None
        assert args.voice_volume_gain_db is None
        assert args.voice_sample_rate_hertz is None
        assert args.voice_effects_profile_id is None
        assert args.google_audio_format == 'linear16'
        assert args.service_account is None
        # ElevenLabs
        assert args.voice_model == 'eleven_multilingual_v2'
        assert args.voice_stability is None
        assert args.voice_similarity_boost is None
        assert args.voice_style is None
        assert args.voice_use_speaker_boost is None
        assert args.elevenlabs_audio_format == 'mp3_44100_128'
        assert args.api_key is None

    def test_parser_scalar(self):
        sys_args = [
            '--voice-stability=0.5',
            'test.txt'
        ]
        args = parse_args(sys_args)
        assert args.voice_stability == 0.5

    def test_parser_large_scalar(self):
        sys_args = [
            '--voice-stability=42.42',
            'test.txt'
        ]
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(sys_args)

    def test_parser_small_scalar(self):
        sys_args = [
            '--voice-stability=-42.42',
            'test.txt'
        ]
        with (pytest.raises(SystemExit), redirect_stderr(StringIO())):
            parse_args(sys_args)
