import json
from collections import namedtuple
from typing import Iterator
from unittest.mock import MagicMock, mock_open, patch

import pytest

from zaphodvox.elevenlabs.voice import ElevenLabsVoice
from zaphodvox.googlecloud.voice import GoogleVoice


@pytest.fixture
def text_to_encode() -> str:
    return "Don't panic!"


@pytest.fixture
def google_voice() -> GoogleVoice:
    return GoogleVoice(
        voice_id='A',
        language='en',
        region='US',
        type='Wavenet'
    )


@pytest.fixture
def elevenlabs_voice() -> ElevenLabsVoice:
    return ElevenLabsVoice(voice_id='Ford')


@pytest.fixture
def voices_data(google_voice, elevenlabs_voice) -> dict:
    return {
        'voices': {
            'voice_1': {
                'google': google_voice.model_dump(),
                'elevenlabs': elevenlabs_voice.model_dump()
            },
            'voice_2': {'elevenlabs': {'voice_id': 'Arthur'}}
        }
    }


@pytest.fixture
def voices_json_data(voices_data) -> str:
    return json.dumps(voices_data)


@pytest.fixture
def fragments_data() -> list[dict]:
    # Fragments #0 to #3 are regular text
    fragments: list[dict] = [
        {
            'text': f'Text {i}',
            'filename': f'test-{i:05}.wav',
            'voice': {
                'voice_id': 'A',
                'language': 'en',
                'region': 'US',
                'type': 'Wavenet'
            },
            'voice_name': 'voice_1',
            'encoder': 'google',
            'audio_format': 'linear16',
            'silence_duration': None
        } for i in range(5)
    ]
    # Fragment #4 is silence
    fragments[4]['text'] = ''
    fragments[4]['voice'] = None
    fragments[4]['voice_name'] = None
    fragments[4]['silence_duration'] = 500
    return fragments


@pytest.fixture
def manifest_json_data(voices_data, fragments_data) -> str:
    return json.dumps(
        {'fragments': fragments_data, 'voices': voices_data['voices']}
    )


@pytest.fixture
def no_voice_manifest_json_data() -> str:
    return json.dumps({
    'fragments': [{
            'text': 'Text 0',
            'filename': 'test-00000.wav',
            'encoder': 'google',
            'audio_format': 'linear16',
            'silence_duration': None
        }]
    })


@pytest.fixture
def incorrect_voice_manifest_json_data() -> str:
    return json.dumps({
        'fragments': [{
                'text': 'Text 0',
                'filename': 'test-00000.wav',
                'voice': {'voice_id': 'Ford'},
                'voice_name': 'voice_1',
                'encoder': 'google',
                'audio_format': 'linear16',
                'silence_duration': None
        }],
        'voices': {'voice_1': {'elevenlabs': {'voice_id': 'Ford'}}}
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


@pytest.fixture
def mock_copy() -> Iterator[MagicMock]:
    with (
        patch('zaphodvox.audio.shutil.copy') as copy,
        patch('zaphodvox.audio.Path.exists', return_value=True)
    ):
        yield copy


MockTempDir = namedtuple('MockTempDir', ['temp_dir_cls', 'path'])


@pytest.fixture
def mock_temp_dir(tmp_path) -> Iterator[MockTempDir]:
    with patch('zaphodvox.main.TemporaryDirectory') as temp_dir:
        temp_dir.return_value.__enter__.return_value = str(tmp_path)
        yield MockTempDir(temp_dir, tmp_path)


MockGoogle = namedtuple(
    'MockGoogle', ['client_cls', 'client', 'audio_content']
)


@pytest.fixture
def mock_google() -> Iterator[MockGoogle]:
    with patch(
        'zaphodvox.googlecloud.encoder.TextToSpeechClient'
    ) as client_cls:
        client = client_cls.return_value
        client_cls.from_service_account_file.return_value = client
        client.return_value.synthesize_speech.return_value.audio_content = \
            b'audio'
        mock_response = client.synthesize_speech.return_value
        yield MockGoogle(client_cls, client, mock_response.audio_content)


MockElevenlabs = namedtuple(
    'MockElevenlabs',
    ['history', 'save', 'generate', 'elvoice', 'from_voice_id']
)


@pytest.fixture
def mock_elevenlabs() -> Iterator[MockElevenlabs]:
    with (
        patch('zaphodvox.elevenlabs.encoder.History') as history,
        patch('zaphodvox.elevenlabs.encoder.save') as save,
        patch('zaphodvox.elevenlabs.encoder.generate') as generate,
        patch('zaphodvox.elevenlabs.encoder.ELVoice') as elvoice,
        patch(
            'zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id'
        ) as from_voice_id
    ):
        yield MockElevenlabs(history, save, generate, elvoice, from_voice_id)
