from unittest.mock import call

import pytest
from pydantic import ValidationError

from zaphodvox.manifest import Manifest
from zaphodvox.qwen.encoder import DEFAULT_URL, QwenEncoder
from zaphodvox.qwen.voice import QwenVoice
from zaphodvox.text import parse_text
from zaphodvox.voice import Voice


def speech_call(text, voice_id='Ryan', url=DEFAULT_URL, audio_format='wav',
                language='English', instruct=None):
    json = {
        'input': text,
        'voice': voice_id,
        'language': language,
        'response_format': audio_format,
    }
    if instruct:
        json['instruct'] = instruct
    return call(f'{url}/v1/audio/speech', json=json)


class TestEncoder():
    def test_encode(
        self, qwen_voice, mock_audio, mock_qwen, mock_progress_bar, tmp_path
    ):
        # Setup
        full_text = "Paragraph 1\n\nParagraph 2\nParagraph 3"
        basename = 'output'
        fragments = parse_text(full_text, voice=qwen_voice)
        manifest = Manifest.plan(
            fragments, basename, 'wav', silence_duration=100
        )
        mock_segment_cls, mock_segment = mock_audio

        # Run
        QwenEncoder().encode_manifest(
            manifest, tmp_path, silence_duration=100
        )

        # Verify
        # Three text fragments were synthesized.
        assert mock_qwen.post.call_count == 3
        # Fragment #0
        mock_qwen.post.assert_has_calls([speech_call('Paragraph 1')])
        mock_qwen.write_bytes.assert_any_call(
            tmp_path / f'{basename}-00000.wav', b'audio'
        )
        # Fragment #1 (silence)
        mock_segment_cls.silent.assert_called_once_with(duration=100)
        mock_segment.export.assert_called_once_with(
            str(tmp_path / f'{basename}-00001.wav'), format='wav'
        )
        # Fragment #2
        mock_qwen.post.assert_has_calls([speech_call('Paragraph 2')])
        mock_qwen.write_bytes.assert_any_call(
            tmp_path / f'{basename}-00002.wav', b'audio'
        )
        # Fragment #3
        mock_qwen.post.assert_has_calls([speech_call('Paragraph 3')])
        mock_qwen.write_bytes.assert_any_call(
            tmp_path / f'{basename}-00003.wav', b'audio'
        )
        # Each synthesized fragment wrote the response bytes.
        assert mock_qwen.write_bytes.call_count == 3
        # Progress bar
        mock_progress_bar.encoder.assert_called_once_with(
            'Encoding', total=sum(len(t) for t in full_text.split('\n'))
        )

    def test_encode_max_chars(
        self, qwen_voice, mock_audio, mock_qwen, mock_progress_bar, tmp_path
    ):
        # Setup
        full_text = "Paragraph 1\n\nParagraph 2\nParagraph 3"
        basename = 'output'
        fragments = parse_text(full_text, voice=qwen_voice, max_chars=30)
        manifest = Manifest.plan(
            fragments, basename, 'wav', silence_duration=100
        )
        mock_segment_cls, mock_segment = mock_audio

        # Run
        QwenEncoder().encode_manifest(
            manifest, tmp_path, silence_duration=100
        )

        # Verify
        assert mock_qwen.post.call_count == 2
        mock_segment_cls.silent.assert_not_called()
        mock_segment.export.assert_not_called()
        # Fragment #0: the paragraph break becomes a plain-text sentence stop.
        mock_qwen.post.assert_has_calls([
            speech_call('Paragraph 1 . Paragraph 2')
        ])
        mock_qwen.write_bytes.assert_any_call(
            tmp_path / f'{basename}-00000.wav', b'audio'
        )
        # Fragment #1
        mock_qwen.post.assert_has_calls([speech_call('Paragraph 3')])
        mock_qwen.write_bytes.assert_any_call(
            tmp_path / f'{basename}-00001.wav', b'audio'
        )
        assert mock_qwen.write_bytes.call_count == 2
        # Progress bar
        mock_progress_bar.encoder.assert_called_once_with(
            'Encoding', total=(
                sum(len(t) for t in full_text.split('\n')) + 2  # newlines
            )
        )

    def test_encode_preset_instruct(self, mock_qwen, tmp_path):
        # Setup: preset voice with instruct, custom url (trailing slash) and
        # mp3 output format.
        voice = QwenVoice(voice_id='Ryan', instruct='calm')
        encoder = QwenEncoder(
            url='http://localhost:9999/', audio_format='mp3'
        )
        filepath = tmp_path / 'out.mp3'

        # Run
        encoder.t2s('Hello', voice, filepath)

        # Verify
        mock_qwen.post.assert_called_once_with(
            'http://localhost:9999/v1/audio/speech',
            json={
                'input': 'Hello',
                'voice': 'Ryan',
                'language': 'English',
                'response_format': 'mp3',
                'instruct': 'calm',
            }
        )
        mock_qwen.response.raise_for_status.assert_called_once_with()
        mock_qwen.write_bytes.assert_called_once_with(filepath, b'audio')

    def test_encode_clone_icl(self, mock_qwen, tmp_path):
        # Setup: a clone voice with a reference transcript (ICL mode).
        ref = tmp_path / 'ref.wav'
        ref.write_text('reference-audio')
        voice = QwenVoice(ref_audio=str(ref), ref_text='hello there')
        encoder = QwenEncoder()
        filepath = tmp_path / 'out.wav'

        # Run
        encoder.t2s('Clone me', voice, filepath)

        # Verify
        args, kwargs = mock_qwen.post.call_args
        assert args == (f'{DEFAULT_URL}/v1/audio/speech/upload',)
        assert kwargs['data'] == {
            'input': 'Clone me',
            'language': 'English',
            'response_format': 'wav',
            'ref_text': 'hello there',
        }
        assert 'voice_file' in kwargs['files']
        mock_qwen.write_bytes.assert_called_once_with(filepath, b'audio')

    def test_encode_clone_zero_shot(self, mock_qwen, tmp_path):
        # Setup: a clone voice with no transcript (zero-shot).
        ref = tmp_path / 'ref.wav'
        ref.write_text('reference-audio')
        voice = QwenVoice(ref_audio=str(ref))
        encoder = QwenEncoder()
        filepath = tmp_path / 'out.wav'

        # Run
        encoder.t2s('Clone me', voice, filepath)

        # Verify
        _, kwargs = mock_qwen.post.call_args
        assert kwargs['data'] == {
            'input': 'Clone me',
            'language': 'English',
            'response_format': 'wav',
            'x_vector_only': 'true',
        }
        assert 'voice_file' in kwargs['files']
        mock_qwen.write_bytes.assert_called_once_with(filepath, b'audio')

    def test_encode_preset_seed(self, mock_qwen, tmp_path):
        # A seeded preset voice sends the seed in the JSON payload.
        voice = QwenVoice(voice_id='Ryan', seed=42)

        QwenEncoder().t2s('Hello', voice, tmp_path / 'out.wav')

        mock_qwen.post.assert_called_once_with(
            f'{DEFAULT_URL}/v1/audio/speech',
            json={
                'input': 'Hello',
                'voice': 'Ryan',
                'language': 'English',
                'response_format': 'wav',
                'seed': 42,
            }
        )

    def test_encode_clone_seed(self, mock_qwen, tmp_path):
        # A seeded clone voice sends the seed as a (string) form field.
        ref = tmp_path / 'ref.wav'
        ref.write_text('reference-audio')
        voice = QwenVoice(ref_audio=str(ref), seed=42)

        QwenEncoder().t2s('Clone me', voice, tmp_path / 'out.wav')

        _, kwargs = mock_qwen.post.call_args
        assert kwargs['data'] == {
            'input': 'Clone me',
            'language': 'English',
            'response_format': 'wav',
            'x_vector_only': 'true',
            'seed': '42',
        }

    def test_encode_preset_temperature(self, mock_qwen, tmp_path):
        # A preset voice with a temperature sends it in the JSON payload.
        voice = QwenVoice(voice_id='Ryan', seed=42, temperature=0.6)

        QwenEncoder().t2s('Hello', voice, tmp_path / 'out.wav')

        mock_qwen.post.assert_called_once_with(
            f'{DEFAULT_URL}/v1/audio/speech',
            json={
                'input': 'Hello',
                'voice': 'Ryan',
                'language': 'English',
                'response_format': 'wav',
                'seed': 42,
                'temperature': 0.6,
            }
        )

    def test_encode_clone_temperature(self, mock_qwen, tmp_path):
        # A clone voice with a temperature sends it as a (string) form field.
        ref = tmp_path / 'ref.wav'
        ref.write_text('reference-audio')
        voice = QwenVoice(ref_audio=str(ref), temperature=0.6)

        QwenEncoder().t2s('Clone me', voice, tmp_path / 'out.wav')

        _, kwargs = mock_qwen.post.call_args
        assert kwargs['data'] == {
            'input': 'Clone me',
            'language': 'English',
            'response_format': 'wav',
            'x_vector_only': 'true',
            'temperature': '0.6',
        }

    def test_encode_design(self, mock_qwen, tmp_path):
        # A designed voice posts to the design endpoint with voice_description.
        voice = QwenVoice(
            description='a warm elderly woman', seed=7, temperature=0.6
        )

        QwenEncoder().t2s('Hello', voice, tmp_path / 'out.wav')

        mock_qwen.post.assert_called_once_with(
            f'{DEFAULT_URL}/v1/audio/speech/design',
            json={
                'input': 'Hello',
                'voice_description': 'a warm elderly woman',
                'language': 'English',
                'response_format': 'wav',
                'seed': 7,
                'temperature': 0.6,
            }
        )
        mock_qwen.write_bytes.assert_called_once_with(
            tmp_path / 'out.wav', b'audio'
        )

    def test_encode_retries(self, mock_qwen, tmp_path):
        # Setup: the server errors on every attempt.
        mock_qwen.response.raise_for_status.side_effect = Exception('boom')
        voice = QwenVoice(voice_id='Ryan')
        encoder = QwenEncoder()

        # Run
        with pytest.raises(Exception, match='boom'):
            encoder.t2s('Hello', voice, tmp_path / 'out.wav')

        # Verify: five attempts.
        assert mock_qwen.post.call_count == 5
        mock_qwen.write_bytes.assert_not_called()

    def test_audio_format(self):
        assert QwenEncoder().audio_format == 'wav'
        assert QwenEncoder(audio_format='mp3').audio_format == 'mp3'

    def test_file_extension(self):
        assert QwenEncoder().file_extension == 'wav'
        assert QwenEncoder(audio_format='mp3').file_extension == 'mp3'

    def test_file_extension_unsupported(self):
        with pytest.raises(ValueError, match='not supported'):
            QwenEncoder(audio_format='ogg').file_extension

    def test_t2s_not_a_qwen_voice(self, tmp_path):
        with pytest.raises(ValueError, match='Not a QwenVoice'):
            QwenEncoder().t2s('Hello', Voice(), tmp_path / 'out.wav')

    def test_qwen_voice_requires_a_source(self):
        with pytest.raises(ValidationError):
            QwenVoice()

    def test_qwen_voice_exactly_one_source(self):
        with pytest.raises(ValidationError):
            QwenVoice(voice_id='Ryan', ref_audio='ref.wav')
        with pytest.raises(ValidationError):
            QwenVoice(voice_id='Ryan', description='a narrator')

    def test_qwen_voice_is_clone(self):
        assert QwenVoice(voice_id='Ryan').is_clone is False
        assert QwenVoice(ref_audio='ref.wav').is_clone is True

    def test_qwen_voice_is_design(self):
        assert QwenVoice(description='a calm narrator').is_design is True
        assert QwenVoice(voice_id='Ryan').is_design is False
