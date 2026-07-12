from argparse import Namespace
from collections import namedtuple
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from zaphodvox.chatterbox.encoder import DEFAULT_URL, ChatterboxEncoder
from zaphodvox.chatterbox.voice import ChatterboxVoice
from zaphodvox.manifest import Fragment, Manifest
from zaphodvox.voices import parse_voice

MockCB = namedtuple('MockCB', ['requests', 'post', 'response', 'write_bytes'])


@pytest.fixture
def mock_chatterbox() -> Iterator[MockCB]:
    with (
        patch('zaphodvox.chatterbox.encoder.requests') as mock_requests,
        patch('pathlib.Path.write_bytes', autospec=True) as mock_write_bytes,
    ):
        response = MagicMock()
        response.content = b'audio'
        mock_requests.post.return_value.__enter__.return_value = response
        yield MockCB(
            mock_requests, mock_requests.post, response, mock_write_bytes
        )


def args(**kwargs) -> Namespace:
    """The command-line arguments a Chatterbox voice is built from."""
    defaults = {
        'voice_id': None,
        'voice_ref_audio': None,
        'voice_ref_text': None,
        'voice_description': None,
        'voice_instruct': None,
        'voice_language': 'English',
        'voice_seed': None,
        'voice_temperature': None,
        'voice_exaggeration': None,
        'voice_cfg_weight': None,
        'voice_speed': None,
        'chatterbox_url': DEFAULT_URL,
        'chatterbox_audio_format': 'wav',
    }
    return Namespace(**{**defaults, **kwargs})


class TestChatterboxVoice():
    def test_requires_a_source(self):
        with pytest.raises(ValueError, match='requires a preset'):
            ChatterboxVoice()

    def test_rejects_two_sources(self):
        with pytest.raises(ValueError, match='exactly one'):
            ChatterboxVoice(voice_id='Ryan.wav', ref_audio='ref.wav')

    def test_from_args_preset(self):
        voice = ChatterboxVoice.from_args(
            args(voice_id='Ryan.wav', voice_exaggeration=0.7, voice_seed=42)
        )

        assert voice == ChatterboxVoice(
            voice_id='Ryan.wav', exaggeration=0.7, seed=42
        )

    def test_from_args_clone(self):
        voice = ChatterboxVoice.from_args(
            args(voice_ref_audio=Path('clips/n.wav'), voice_cfg_weight=0.5)
        )

        assert voice is not None
        assert voice.is_clone
        assert voice.ref_audio == 'clips/n.wav'
        assert voice.cfg_weight == 0.5

    def test_from_args_none(self):
        assert ChatterboxVoice.from_args(args()) is None

    def test_rejects_voice_design(self):
        # Chatterbox cannot design a voice. Better to say so than to synthesize
        # a whole book in a voice that quietly ignored the description.
        with pytest.raises(ValueError, match='cannot design a voice'):
            ChatterboxVoice.from_args(
                args(voice_id='Ryan.wav', voice_description='a warm woman')
            )

    def test_rejects_instruct(self):
        with pytest.raises(ValueError, match='no "--voice-instruct"'):
            ChatterboxVoice.from_args(
                args(voice_id='Ryan.wav', voice_instruct='calm, wry')
            )

    def test_rejects_ref_text(self):
        with pytest.raises(ValueError, match='no in-context clone mode'):
            ChatterboxVoice.from_args(
                args(voice_ref_audio=Path('n.wav'), voice_ref_text='hello')
            )

    def test_round_trips_through_a_voices_file(self):
        voice = ChatterboxVoice(voice_id='Ryan.wav', exaggeration=0.7)

        parsed = parse_voice(voice.model_dump(exclude_none=True))

        assert parsed == voice
        assert isinstance(parsed, ChatterboxVoice)


class TestChatterboxEncoder():
    def test_preset_synthesis(self, mock_chatterbox):
        encoder = ChatterboxEncoder()
        voice = ChatterboxVoice(
            voice_id='Ryan.wav', exaggeration=0.7, seed=42, speed_factor=1.1
        )

        encoder.t2s('Hello there.', voice, Path('out.wav'))

        mock_chatterbox.post.assert_called_once_with(
            f'{DEFAULT_URL}/tts',
            json={
                'text': 'Hello there.',
                'output_format': 'wav',
                # zaphodvox decides where the fragments are, not the server.
                'split_text': False,
                'voice_mode': 'predefined',
                'predefined_voice_id': 'Ryan.wav',
                'exaggeration': 0.7,
                'speed_factor': 1.1,
                'seed': 42,
            },
        )
        mock_chatterbox.write_bytes.assert_called_once_with(
            Path('out.wav'), b'audio'
        )

    def test_clone_uploads_the_reference_once(
        self, mock_chatterbox, tmp_path, mock_progress_bar
    ):
        # Setup: a book of three fragments in a cloned voice. The clip has to be
        # uploaded before it can be cloned -- but only once, not once per
        # fragment.
        ref = tmp_path / 'narrator.wav'
        # Not `write_bytes`: the fixture patches it, to catch the audio the
        # encoder writes.
        with open(str(ref), 'wb') as f:
            f.write(b'RIFFfake')
        voice = ChatterboxVoice(ref_audio=str(ref))
        manifest = Manifest(fragments=[
            Fragment(text=f'Line {i}.', filename=f'f-{i}.wav', voice=voice)
            for i in range(3)
        ])

        # Run
        ChatterboxEncoder().encode_manifest(manifest, encode_dir=tmp_path)

        # Verify
        urls = [c.args[0] for c in mock_chatterbox.post.call_args_list]
        assert urls.count(f'{DEFAULT_URL}/upload_reference') == 1
        assert urls.count(f'{DEFAULT_URL}/tts') == 3
        for call in mock_chatterbox.post.call_args_list:
            if call.args[0].endswith('/tts'):
                assert call.kwargs['json']['voice_mode'] == 'clone'
                assert call.kwargs['json']['reference_audio_filename'] == (
                    'narrator.wav'
                )

    def test_missing_reference_fails_before_encoding(
        self, mock_chatterbox, tmp_path, mock_progress_bar
    ):
        voice = ChatterboxVoice(ref_audio=str(tmp_path / 'gone.wav'))
        manifest = Manifest(fragments=[
            Fragment(text='Hello.', filename='f-0.wav', voice=voice)
        ])

        with pytest.raises(ValueError, match='not found'):
            ChatterboxEncoder().encode_manifest(manifest, encode_dir=tmp_path)

        assert not mock_chatterbox.post.called

    def test_rejects_a_qwen_voice(self, mock_chatterbox):
        from zaphodvox.qwen.voice import QwenVoice

        with pytest.raises(ValueError, match='Not a ChatterboxVoice'):
            ChatterboxEncoder().t2s(
                'Hello.', QwenVoice(voice_id='Ryan'), Path('out.wav')
            )

    def test_unsupported_audio_format(self):
        with pytest.raises(ValueError, match='not supported'):
            ChatterboxEncoder(audio_format='flac').file_extension

    def test_from_args(self):
        encoder, voice = ChatterboxEncoder.from_args(
            args(voice_id='Ryan.wav', chatterbox_url='http://gardner:8004')
        )

        assert isinstance(encoder, ChatterboxEncoder)
        assert encoder.audio_format == 'wav'
        assert voice == ChatterboxVoice(voice_id='Ryan.wav')

    def test_clone_voice_carries_the_audition_settings(self):
        # What `--adopt` writes into the voices file.
        entry = {
            'seed': 5,
            'text': 'A sample sentence.',
            'voice': {
                'encoder': 'chatterbox',
                'voice_id': 'Ryan.wav',
                'exaggeration': 0.7,
                'temperature': 0.6,
            },
        }

        voice = ChatterboxEncoder.clone_voice('Narrator.wav', entry, args())

        assert voice == ChatterboxVoice(
            ref_audio='Narrator.wav',
            seed=5,
            temperature=0.6,
            exaggeration=0.7,
        )

    def test_clone_voice_overrides_from_the_command_line(self):
        entry = {'seed': 5, 'voice': {'exaggeration': 0.7}}

        voice = ChatterboxEncoder.clone_voice(
            'Narrator.wav', entry, args(voice_exaggeration=1.2, voice_seed=9)
        )

        assert voice.exaggeration == 1.2
        assert voice.seed == 9
