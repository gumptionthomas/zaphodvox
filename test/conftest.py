import json
from collections import namedtuple
from typing import Iterator
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zaphodvox.qwen.voice import QwenVoice


@pytest.fixture
def text_to_encode() -> str:
    return "Don't panic!"


@pytest.fixture
def qwen_voice() -> QwenVoice:
    return QwenVoice(voice_id='Ryan')


@pytest.fixture
def qwen_voice_2() -> QwenVoice:
    return QwenVoice(voice_id='Serena')


@pytest.fixture
def qwen_clone_voice() -> QwenVoice:
    return QwenVoice(ref_audio='ref.wav', ref_text='hello')


@pytest.fixture
def voices_data(qwen_voice, qwen_voice_2) -> dict:
    return {
        'voices': {
            'voice_1': qwen_voice.model_dump(),
            'voice_2': qwen_voice_2.model_dump(),
        }
    }


@pytest.fixture
def voices_json_data(voices_data) -> str:
    return json.dumps(voices_data)


@pytest.fixture
def fragments_data() -> list[dict]:
    # Fragments #0 to #3 are regular text, #4 is silence.
    fragments: list[dict] = [
        {
            'text': f'Text {i}',
            'filename': f'test-{i:05}.wav',
            'voice_name': 'voice_1',
            'encoder': 'qwen',
            'audio_format': 'wav',
            'silence_duration': None,
        } for i in range(5)
    ]
    fragments[4]['text'] = ''
    fragments[4]['voice_name'] = None
    fragments[4]['silence_duration'] = 500
    return fragments


@pytest.fixture
def manifest_json_data(voices_data, fragments_data) -> str:
    return json.dumps(
        {'fragments': fragments_data, 'voices': voices_data['voices']}
    )


@pytest.fixture
def no_voice_manifest_json_data(text_to_encode) -> str:
    return json.dumps({
        'fragments': [{
            'text': text_to_encode,
            'filename': 'test-00000.wav',
            'encoder': 'qwen',
            'audio_format': 'wav',
            'silence_duration': None,
        }]
    })


@pytest.fixture
def inline_voice_manifest_json_data(qwen_voice, text_to_encode) -> str:
    # The fragment carries an inline voice (no voice_name, no voices map), so
    # it must be re-encodable without re-specifying a voice.
    return json.dumps({
        'fragments': [{
            'text': text_to_encode,
            'filename': 'test-00000.wav',
            'voice': qwen_voice.model_dump(),
            'encoder': 'qwen',
            'audio_format': 'wav',
            'silence_duration': None,
        }]
    })


@pytest.fixture
def incorrect_voice_manifest_json_data(qwen_voice, text_to_encode) -> str:
    # The fragment references a voice name ("voice_2") that is not present in
    # the manifest voices, so it cannot be resolved.
    return json.dumps({
        'fragments': [{
            'text': text_to_encode,
            'filename': 'test-00000.wav',
            'voice_name': 'voice_2',
            'encoder': 'qwen',
            'audio_format': 'wav',
            'silence_duration': None,
        }],
        'voices': {'voice_1': qwen_voice.model_dump()},
    })


@pytest.fixture
def mock_builtins_open(text_to_encode) -> Iterator[MagicMock]:
    with patch('builtins.open', new_callable=mock_open) as mbo:
        mbo.return_value = mock_open(read_data=text_to_encode).return_value
        yield mbo


MockAudio = namedtuple('MockAudio', ['segment_cls', 'segment'])


@pytest.fixture
def mock_audio() -> Iterator[tuple[MagicMock, MagicMock]]:
    with patch('zaphodvox.audio.AudioSegment') as segment_cls:
        segment = segment_cls.return_value
        segment.__add__.return_value = segment
        segment.__iadd__.return_value = segment
        segment_cls.empty.return_value = segment
        segment_cls.from_file.return_value = segment
        segment_cls.silent.return_value = segment
        yield MockAudio(segment_cls, segment)


MockQwen = namedtuple(
    'MockQwen', ['requests', 'post', 'response', 'content', 'write_bytes']
)


@pytest.fixture
def mock_qwen() -> Iterator[MockQwen]:
    with (
        patch('zaphodvox.qwen.encoder.requests') as mock_requests,
        patch('pathlib.Path.write_bytes', autospec=True) as mock_write_bytes,
    ):
        response = MagicMock()
        response.content = b'audio'
        mock_requests.post.return_value.__enter__.return_value = response
        yield MockQwen(
            mock_requests,
            mock_requests.post,
            response,
            response.content,
            mock_write_bytes,
        )


MockProgressBar = namedtuple('MockProgressBar', ['audio', 'encoder'])


@pytest.fixture
def mock_progress_bar() -> Iterator[MockProgressBar]:
    with (
        patch('zaphodvox.audio.ProgressBar') as apb,
        patch('zaphodvox.encoder.ProgressBar') as epb
    ):
        yield MockProgressBar(apb, epb)
