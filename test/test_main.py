from pathlib import Path
from unittest.mock import MagicMock, call, mock_open, patch

import pytest
from zaphodvox.googlecloud.voice import GoogleVoice
from zaphodvox.main import main
from zaphodvox.parser import parse_args

TEST_VOICES = """{
    "voices": {
        "voice_1": {
            "google": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "elevenlabs": {"voice_id": "Josh"}
        },
        "voice_2": {
            "elevenlabs": {
                "voice_id": "Adam",
                "model": "multilingual_v2"
            }
        }
    }
}"""

TEST_MANIFEST = """{
    "fragments": [
        {
            "text": "Text 0",
            "filename": "test-00000.wav",
            "voice": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "voice_name": "voice_1",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        },
        {
            "text": "Text 1",
            "filename": "test-00001.wav",
            "voice": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "voice_name": "voice_1",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        },
        {
            "text": "Text 2",
            "filename": "test-00002.wav",
            "voice": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "voice_name": "voice_1",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        },
        {
            "text": "Text 3",
            "filename": "test-00003.wav",
            "voice": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "voice_name": "voice_1",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        },
        {
            "text": "",
            "filename": "test-00004.wav",
            "voice": null,
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": 500
        }
    ],
    "voices": {
        "voice_1": {
            "google": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            },
            "elevenlabs": {"voice_id": "Josh"}
        },
        "voice_2": {
            "google": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Wavenet"
            }
        }
    }
}"""

TEST_NO_VOICE_MANIFEST = """{
    "fragments": [
        {
            "text": "Text 0",
            "filename": "test-00000.wav",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        }
    ]
}"""

TEST_INCORRECT_VOICE_MANIFEST = """{
    "fragments": [
        {
            "text": "Text 0",
            "filename": "test-00000.wav",
            "voice": {"voice_id": "Josh"},
            "voice_name": "voice_1",
            "encoder": "google",
            "audio_format": "linear16",
            "silence_duration": null
        }
    ],
    "voices": {
        "voice_1": {
            "elevenlabs": {"voice_id": "Josh"}
        }
    }
}"""


class TestMain():
    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.Path.exists')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        mock_temp_dir, mock_path_exists, *args
    ):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--voices-file=voices.json',
            '--encode',
            '--concat',
            '--copy',
            'test.txt'
        ]
        voice = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/foo'
        mock_path_exists.return_value = True
        mock_open_write = mock_builtins_open().write
        mock_builtins_open.side_effect = (
            mock_open(read_data=TEST_VOICES).return_value,
            mock_builtins_open.return_value,
            mock_builtins_open.return_value
        )

        main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_builtins_open.assert_any_call(str(Path('voices.json')), 'r')
        mock_t2s.assert_called_once_with(
            'Hello, world!', voice, Path('/tmp/foo/test-00000.wav')
        )
        mock_segment.export.assert_called_once_with(
            str(Path.cwd().joinpath('test.wav')), format='wav'
        )
        mock_builtins_open.assert_any_call(
            str(Path.cwd().joinpath('test-manifest.json')), 'w'
        )
        mock_open_write.assert_called_once()
        mock_copy.assert_called_once_with(
            '/tmp/foo/test-00000.wav', str(Path.cwd())
        )

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data=TEST_MANIFEST)
    def test_main_manifest(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, *args
    ):
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--manifest-indexes=0, 2,4 ',
            '--copy',
            'test-manifest.json'
        ]
        voice = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment

        main(sys_args)

        mock_builtins_open.assert_any_call(
            str(Path('test-manifest.json')), 'r'
        )
        mock_t2s.assert_has_calls([
            call('Text 0', voice, Path('test-00000.wav')),
            call('Text 2', voice, Path('test-00002.wav'))
        ])
        mock_audio_segment.silent.assert_called_once()

        mock_segment.export.assert_has_calls([
            call('test-00004.wav', format='wav'),
            call('test.wav', format='wav')
        ])

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.elevenlabs.encoder.ELVoice')
    @patch('zaphodvox.elevenlabs.encoder.save')
    @patch('zaphodvox.elevenlabs.encoder.generate')
    @patch('zaphodvox.elevenlabs.encoder.History')
    @patch('zaphodvox.main.Path.exists')
    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data=TEST_MANIFEST)
    def test_main_manifest_different_encoder(
        self, mock_builtins_open, mock_audio_segment, mock_copy,
        mock_voice_settings_from_voice_id, mock_path_exists, *args
    ):
        sys_args = [
            '--encoder=elevenlabs',
            '--basename=test',
            '--voices-file=voices.json',
            '--encode',
            '--concat',
            '--manifest-indexes=0, 2, 4',
            '--copy',
            'test-manifest.json'
        ]
        mock_voice_settings_from_voice_id.return_value = MagicMock()
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment
        mock_path_exists.return_value = True
        mock_builtins_open.side_effect = (
            mock_open(read_data=TEST_VOICES).return_value,
            mock_builtins_open.return_value,
            mock_builtins_open.return_value
        )

        main(sys_args)

        mock_builtins_open.assert_any_call(
            str(Path('test-manifest.json')), 'r'
        )
        mock_builtins_open.assert_any_call(
            str(Path('voices.json')), 'r'
        )
        mock_audio_segment.silent.assert_called_once()
        mock_segment.export.assert_has_calls([
            call('test-00004.mp3', format='mp3'),
            call('test.mp3', format='mp3')
        ])

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch(
        'builtins.open',
        new_callable=mock_open,
        read_data=TEST_NO_VOICE_MANIFEST
    )
    def test_main_manifest_no_voice(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, *args
    ):
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--copy',
            'test-manifest.json'
        ]
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment

        with pytest.raises(SystemExit):
            main(sys_args)

        mock_builtins_open.assert_any_call(
            str(Path('test-manifest.json')), 'r'
        )
        mock_t2s.assert_not_called()
        mock_audio_segment.silent.assert_not_called()
        mock_segment.export.assert_not_called()


    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.audio.AudioSegment')
    @patch(
        'builtins.open',
        new_callable=mock_open,
        read_data=TEST_INCORRECT_VOICE_MANIFEST
    )
    def test_main_manifest_incorrect_voice(
        self, mock_builtins_open, mock_audio_segment, *args
    ):
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--copy',
            'test-manifest.json'
        ]
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_audio_segment.silent.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment

        with pytest.raises(SystemExit):
            main(sys_args)

        mock_builtins_open.assert_any_call(
            str(Path('test-manifest.json')), 'r'
        )
        mock_audio_segment.silent.assert_not_called()
        mock_segment.export.assert_not_called()


    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.elevenlabs.encoder.ELVoice')
    @patch('zaphodvox.elevenlabs.encoder.save')
    @patch('zaphodvox.elevenlabs.encoder.generate')
    @patch('zaphodvox.elevenlabs.encoder.History')
    @patch('zaphodvox.main.Path.exists')
    @patch('zaphodvox.elevenlabs.voice.VoiceSettings.from_voice_id')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.elevenlabs.encoder.ElevenLabsEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main_elevenlabs(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        mock_voice_settings_from_voice_id, mock_path_exists, *args
    ):
        sys_args = [
            '--encoder=elevenlabs',
            '--voice-id=TxGEqnHWrfWFTfGW9XjX',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        mock_voice_settings_from_voice_id.return_value = MagicMock()
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_audio_segment.from_file.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_segment.__iadd__.return_value = mock_segment
        mock_path_exists.return_value = True

        main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_t2s.assert_called_once()
        mock_segment.export.assert_called_once()
        mock_copy.assert_called_once()

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main_encode_exception(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        mock_temp_dir, mock_client, mock_progress, capfd, *args
    ):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        voice = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/foo'
        mock_t2s.side_effect = Exception('encode exception')

        with pytest.raises(SystemExit) as se:
            main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_builtins_open().read.assert_called_once()
        mock_t2s.assert_called_once_with(
            'Hello, world!', voice, Path('/tmp/foo/test-00000.wav')
        )
        mock_segment.export.assert_not_called()
        mock_builtins_open().write.assert_not_called()
        mock_copy.assert_not_called()

        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'encode exception' in out

    @patch('zaphodvox.progress.ProgressBar')
    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('zaphodvox.main.Path.exists')
    @patch('zaphodvox.main.TemporaryDirectory')
    @patch('zaphodvox.audio.shutil.copy')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_main_concat_exception(
        self, mock_builtins_open, mock_audio_segment, mock_t2s, mock_copy,
        mock_temp_dir, mock_path_exists, mock_client, mock_progress, capfd,
        *args
    ):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        voice = GoogleVoice(
            voice_id='A', language='en', region='US', type='Wavenet'
        )
        mock_segment = mock_audio_segment()
        mock_audio_segment.empty.return_value = mock_segment
        mock_segment.__add__.return_value = mock_segment
        mock_temp_dir.return_value.__enter__.return_value = '/tmp/foo'
        mock_audio_segment.from_file.side_effect = Exception('from_file error')
        mock_path_exists.return_value = True

        with pytest.raises(SystemExit) as se:
            main(sys_args)

        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_builtins_open().read.assert_called_once()
        mock_t2s.assert_called_once_with(
            'Hello, world!', voice, Path('/tmp/foo/test-00000.wav')
        )
        mock_segment.export.assert_not_called()
        mock_builtins_open.assert_any_call(
            str(Path.cwd().joinpath('test-manifest.json')), 'w'
        )
        mock_builtins_open().write.assert_called_once()
        mock_copy.assert_called_once_with(
            '/tmp/foo/test-00000.wav', str(Path.cwd())
        )

        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'from_file error' in out


    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_nothing_to_do(self, mock_open, capfd, *args):
        sys_args = ['test.txt']

        with pytest.raises(SystemExit) as se:
            main(raw_args=sys_args)

        assert se.value.code == 0
        out, _ = capfd.readouterr()
        assert 'Nothing to do' in out

    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_no_encoder(self, mock_open, capfd, *args):
        sys_args = ['--encode', 'test.txt']
        args = parse_args(sys_args)

        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No encoder specified' in out

    @patch('builtins.open', new_callable=mock_open, read_data=TEST_MANIFEST)
    def test_manifest_no_encoder(self, mock_open, capfd, *args):
        sys_args = ['--encode', 'test-manifest.json']
        args = parse_args(sys_args)

        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No encoder specified' in out

    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_invalid_encoder(self, mock_open, capfd, *args):
        sys_args = ['--encoder=google', '--encode', 'test.txt']
        args = parse_args(sys_args)
        args.encoder = 'NotARealEncoder'

        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'Encoder "NotARealEncoder" not found' in out

    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_clean(self, mock_builtins_open, *args):
        sys_args = ['--clean', 'test.txt']

        main(sys_args)

        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        mock_builtins_open().write.assert_called_once_with('Hello, world!\n\n')

    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_clean_max_chars(self, mock_builtins_open, *args):
        sys_args = ['--clean', '--max-chars=7', 'test.txt']

        main(sys_args)

        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        mock_builtins_open().write.assert_called_once_with(
            'Hello,\n\nworld!\n\n'
        )

    @patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
    @patch('builtins.open', new_callable=mock_open, read_data='Hello, world!')
    def test_plan(self, mock_builtins_open, *args):
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--plan',
            'test.txt'
        ]

        main(sys_args)

        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-plan.json', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
