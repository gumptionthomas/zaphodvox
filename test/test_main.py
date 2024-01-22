from pathlib import Path
from unittest.mock import MagicMock, call, mock_open

import pytest
from google.cloud.texttospeech import AudioEncoding, SynthesisInput

from zaphodvox.main import main
from zaphodvox.parser import parse_args


class TestMain():
    def test_main(
        self, text_to_encode, google_voice, mock_builtins_open,
        voices_json_data, mock_audio, mock_copy, mock_temp_dir,
        mock_google
    ):
        # Setup
        sys_args = [
            '--encoder=google',
            '--voice-name=voice_1',
            '--voices-file=voices.json',
            '--encode',
            '--concat',
            '--copy',
            'test.txt'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=text_to_encode).return_value,
            mock_open(read_data=voices_json_data).return_value,
            mock_builtins_open.return_value,
            mock_builtins_open.return_value
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_any_call('test.txt', 'r')
        # Voices file
        mock_builtins_open.assert_any_call('voices.json', 'r')
        # Google client synthesize_speech
        request = {
            'input': SynthesisInput(text=text_to_encode),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(
                AudioEncoding.LINEAR16
            )
        }
        mock_google.client.synthesize_speech.assert_called_once_with(
            request=request
        )
        # Fragment file
        mock_builtins_open.assert_any_call(
            str(mock_temp_dir.path / 'test-00000.wav'), 'wb'
        )
        mock_write.assert_any_call(mock_google.audio_content)
        mock_audio.segment_cls.silence.assert_not_called()
        # Concat file
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment_cls.from_file.assert_called_once_with(
            str(mock_temp_dir.path / 'test-00000.wav'), format='wav'
        )
        mock_audio.segment.export.assert_called_once_with(
            str(Path.cwd() / 'test.wav'), format='wav'
        )
        # Manifest file
        mock_builtins_open.assert_any_call(
            str(Path.cwd() / 'test-manifest.json'), 'w'
        )
        assert mock_write.call_count == 2
        # Copy
        mock_copy.assert_called_once_with(
            str(mock_temp_dir.path / 'test-00000.wav'), str(Path.cwd())
        )

    def test_main_manifest(
        self, google_voice, mock_builtins_open, manifest_json_data,
        mock_audio, mock_copy, mock_google, mock_temp_dir
    ):
        # Setup
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--concat-out=.',
            '--indexes=0, 2,4 ',
            '--copy',
            'test-manifest.json'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=manifest_json_data).return_value,
            mock_builtins_open.return_value,
            mock_builtins_open.return_value,
            mock_builtins_open.return_value
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_any_call('test-manifest.json', 'r')
        # Google client synthesize_speech
        mock_temp_dir.temp_dir_cls.assert_called_once_with()
        assert mock_google.client.synthesize_speech.call_count == 2
        # Fragment #0
        request = {
            'input': SynthesisInput(text='Text 0'),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(
                AudioEncoding.LINEAR16
            )
        }
        mock_google.client.synthesize_speech.assert_any_call(request=request)
        mock_builtins_open.assert_any_call('test-00000.wav', 'wb')
        assert mock_write.call_args_list[0] == call(mock_google.audio_content)
        # Fragment #2
        request['input'] = SynthesisInput(text='Text 2')
        mock_google.client.synthesize_speech.assert_any_call(request=request)
        mock_builtins_open.assert_any_call('test-00002.wav', 'wb')
        assert mock_write.call_args_list[1] == call(mock_google.audio_content)
        # No other google fragments
        assert mock_google.client.synthesize_speech.call_count == 2
        # Fragment #4 (silence)
        mock_audio.segment_cls.silent.assert_called_once()
        mock_audio.segment.export.assert_any_call(
            'test-00004.wav', format='wav'
        )
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment.export.assert_any_call('test.wav', format='wav')
        assert mock_audio.segment.export.call_count == 2
        # Manifest file
        mock_builtins_open.assert_any_call('test-manifest.json', 'w')
        assert mock_write.call_count == 3
        # Copy not called
        mock_copy.assert_not_called()

    def test_main_manifest_different_encoder(
        self, voices_json_data, manifest_json_data, elevenlabs_voice,
        mock_builtins_open, mock_elevenlabs, mock_audio, mock_copy
    ):
        # Setup
        sys_args = [
            '--encoder=elevenlabs',
            '--basename=test',
            '--voices-file=voices.json',
            '--encode',
            '--concat',
            '--indexes=0, 2, 4',
            '--copy',
            'test-manifest.json'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=manifest_json_data).return_value,
            mock_open(read_data=voices_json_data).return_value,
            mock_builtins_open.return_value
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call(
            str(Path('test-manifest.json')), 'r'
        )
        # Voices file
        mock_builtins_open.assert_any_call(
            str(Path('voices.json')), 'r'
        )
        # Fragment #0
        mock_elevenlabs.from_voice_id.assert_any_call(
            elevenlabs_voice.voice_id
        )
        mock_elevenlabs.elvoice.assert_any_call(
            voice_id=elevenlabs_voice.voice_id,
            settings=mock_elevenlabs.from_voice_id.return_value
        )
        mock_elevenlabs.generate.assert_any_call(
            text='Text 0',
            voice=mock_elevenlabs.elvoice.return_value,
            output_format='mp3_44100_128',
            model='eleven_multilingual_v2'
        )
        mock_elevenlabs.save.assert_any_call(
            mock_elevenlabs.generate.return_value,
            'test-00000.mp3',
        )
        # Fragment #2
        mock_elevenlabs.from_voice_id.assert_any_call(
            elevenlabs_voice.voice_id
        )
        mock_elevenlabs.elvoice.assert_any_call(
            voice_id=elevenlabs_voice.voice_id,
            settings=mock_elevenlabs.from_voice_id.return_value
        )
        mock_elevenlabs.generate.assert_any_call(
            text='Text 2',
            voice=mock_elevenlabs.elvoice.return_value,
            output_format='mp3_44100_128',
            model='eleven_multilingual_v2'
        )
        mock_elevenlabs.save.assert_any_call(
            mock_elevenlabs.generate.return_value,
            'test-00002.mp3',
        )
        # No other elevenlabs fragments
        assert mock_elevenlabs.from_voice_id.call_count == 2
        assert mock_elevenlabs.elvoice.call_count == 2
        assert mock_elevenlabs.generate.call_count == 2
        assert mock_elevenlabs.save.call_count == 2
        # Fragment #4 (silence)
        mock_audio.segment_cls.silent.assert_called_once()
        mock_audio.segment.export.assert_any_call(
            'test-00004.mp3', format='mp3'
        )
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment.export.assert_has_calls([
            call('test-00004.mp3', format='mp3'),
            call('test.mp3', format='mp3')
        ])
        # Manifest file
        mock_builtins_open.assert_any_call('test-manifest.json', 'w')
        assert mock_write.call_count == 1
        # Copy not called
        mock_copy.assert_not_called()

    def test_main_manifest_no_voice(
        self, mock_builtins_open, no_voice_manifest_json_data, mock_audio,
        mock_google, mock_copy, capfd
    ):
        # Setup
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--copy',
            'test-manifest.json'
        ]
        mock_builtins_open.return_value = mock_open(
            read_data=no_voice_manifest_json_data
        ).return_value

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_called_once_with(
            str(Path('test-manifest.json')), 'r'
        )
        # Google client synthesize_speech not called
        mock_google.client.synthesize_speech.assert_not_called()
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files not called
        mock_audio.segment_cls.empty.assert_not_called()
        mock_audio.segment.export.assert_not_called()
        # Manifest file not called
        assert mock_builtins_open.call_count == 1
        # Copy not called
        mock_copy.assert_not_called()
        # System exit
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No voice specified' in out

    def test_main_manifest_incorrect_voice(
        self, mock_builtins_open, incorrect_voice_manifest_json_data,
        mock_audio, mock_google, mock_copy, capfd
    ):
        # Setup
        sys_args = [
            '--encoder=google',
            '--basename=test',
            '--encode',
            '--concat',
            '--copy',
            'test-manifest.json'
        ]
        mock_builtins_open.return_value = mock_open(
            read_data=incorrect_voice_manifest_json_data
        ).return_value

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_called_once_with('test-manifest.json', 'r')
         # Google client synthesize_speech not called
        mock_google.client.synthesize_speech.assert_not_called()
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files not called
        mock_audio.segment_cls.empty.assert_not_called()
        mock_audio.segment.export.assert_not_called()
        # Manifest file not called
        assert mock_builtins_open.call_count == 1
        # Copy not called
        mock_copy.assert_not_called()
        # System exit
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No voice specified' in out

    def test_main_elevenlabs(
        self, text_to_encode, elevenlabs_voice, mock_builtins_open,
        mock_temp_dir, mock_elevenlabs, mock_copy, mock_audio
    ):
        # Setup
        voice_id = elevenlabs_voice.voice_id
        sys_args = [
            '--encoder=elevenlabs',
            f'--voice-id={voice_id}',
            '--encode',
            '--concat',
            '--copy',
            '--delete-history',
            'test.txt'
        ]
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        # Voice
        mock_elevenlabs.from_voice_id.assert_called_once_with(voice_id)
        mock_elevenlabs.elvoice.assert_called_once_with(
            voice_id=voice_id,
            settings=mock_elevenlabs.from_voice_id.return_value
        )
        # Fragment #0
        mock_elevenlabs.generate.assert_called_once_with(
            text=text_to_encode,
            voice=mock_elevenlabs.elvoice.return_value,
            output_format='mp3_44100_128',
            model='eleven_multilingual_v2'
        )
        mock_elevenlabs.save.assert_called_once_with(
            mock_elevenlabs.generate.return_value,
            str(mock_temp_dir.path / 'test-00000.mp3')
        )
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment_cls.from_file.assert_called_once_with(
            str(mock_temp_dir.path / 'test-00000.mp3'), format='mp3'
        )
        mock_audio.segment.export.assert_called_once_with(
            str(Path.cwd() / 'test.mp3'), format='mp3'
        )
        # Manifest file
        mock_builtins_open.assert_any_call(
            str(Path.cwd() / 'test-manifest.json'), 'w'
        )
        assert mock_write.call_count == 1
        # Copy files
        mock_copy.assert_called_once_with(
            str(mock_temp_dir.path / 'test-00000.mp3'), str(Path.cwd())
        )
        # Delete history
        mock_elevenlabs.history.from_api.assert_called_once_with()

    def test_main_encode_exception(
        self, text_to_encode, google_voice, mock_builtins_open, mock_audio,
        mock_google, mock_temp_dir, capfd
    ):
        error = 'encode exception'
        # Setup
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            'test.txt'
        ]
        mock_google.client.synthesize_speech.side_effect = Exception(error)

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_builtins_open().read.assert_called_once()
        # Google client synthesize_speech
        mock_temp_dir.temp_dir_cls.assert_called_once_with()
        request = {
            'input': SynthesisInput(text=text_to_encode),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(
                AudioEncoding.LINEAR16
            )
        }
        mock_google.client.synthesize_speech.assert_any_call(request=request)
        assert mock_google.client.synthesize_speech.call_count == 5
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files not called
        mock_audio.segment_cls.empty.assert_not_called()
        mock_audio.segment.export.assert_not_called()
        # Manifest file not called
        mock_builtins_open().write.assert_not_called()
        # System exit
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert error in out

    def test_main_concat_exception(
        self, text_to_encode, google_voice, mock_builtins_open,
        mock_google, mock_audio, mock_copy, mock_temp_dir, capfd
    ):
        # Setup
        error  = 'from_file error'
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--encode',
            '--concat',
            '--copy',
            'test.txt'
        ]
        mock_write = mock_builtins_open.return_value.write
        mock_audio.segment_cls.from_file.side_effect = Exception(error)

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Input file
        mock_builtins_open.assert_any_call(str(Path('test.txt')), 'r')
        mock_builtins_open().read.assert_called_once()
        # Google client synthesize_speech
        request = {
            'input': SynthesisInput(text=text_to_encode),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(
                AudioEncoding.LINEAR16
            )
        }
        mock_google.client.synthesize_speech.assert_called_once_with(
            request=request
        )
        # Fragment file
        mock_builtins_open.assert_any_call(
            str(mock_temp_dir.path / 'test-00000.wav'), 'wb'
        )
        mock_write.assert_any_call(mock_google.audio_content)
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment.export.assert_not_called()
        # Manifest file
        mock_builtins_open.assert_any_call(
            str(Path.cwd() / 'test-manifest.json'), 'w'
        )
        assert mock_write.call_count == 2
        # Copy
        mock_copy.assert_called_once_with(
            str(mock_temp_dir.path / 'test-00000.wav'), str(Path.cwd())
        )
        # System exit
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert error in out

    def test_version(self, capfd):
        # Setup
        sys_args = ['--version']

        # Run
        with pytest.raises(SystemExit) as se:
            main(raw_args=sys_args)

        # Verify
        assert se.value.code == 0
        out, _ = capfd.readouterr()
        assert 'version 1.2.0' in out

    def test_nothing_to_do(self, mock_builtins_open, capfd):
        # Setup
        sys_args = ['test.txt']

        # Run
        with pytest.raises(SystemExit) as se:
            main(raw_args=sys_args)

        # Verify
        mock_builtins_open.assert_not_called()
        assert se.value.code == 0
        out, _ = capfd.readouterr()
        assert 'Nothing to do' in out

    def test_no_inputfile(self, mock_builtins_open, capfd):
        # Setup
        sys_args = ['--encode']
        args = parse_args(sys_args)

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        mock_builtins_open.assert_not_called()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No input file specified.' in out

    def test_nonexistant_inputfile(self, mock_google, capfd):
        # Setup
        sys_args = ['--encoder=google', '--encode', 'test.txt']
        args = parse_args(sys_args)

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        mock_google.client_cls.assert_called_once_with()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No such file' in out

    def test_no_encoder(self, mock_builtins_open, capfd):
        # Setup
        sys_args = ['--encode', 'test.txt']
        args = parse_args(sys_args)

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        mock_builtins_open.assert_not_called()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No encoder specified' in out

    def test_manifest_no_encoder(
        self, mock_builtins_open, manifest_json_data, capfd
    ):
        # Setup
        mock_builtins_open.read_data = manifest_json_data
        sys_args = ['--encode', 'test-manifest.json']
        args = parse_args(sys_args)

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        mock_builtins_open.assert_not_called()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No encoder specified' in out

    def test_invalid_encoder(self, mock_builtins_open, capfd):
        # Setup
        sys_args = ['--encoder=google', '--encode', 'test.txt']
        args = parse_args(sys_args)
        args.encoder_name = 'NotARealEncoder'

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        mock_builtins_open.assert_not_called()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'Encoder "NotARealEncoder" not found' in out

    def test_clean(self, text_to_encode, mock_builtins_open):
        # Setup
        sys_args = ['--clean', 'test.txt']

        # Run
        main(sys_args)

        # Verify
        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        mock_builtins_open().write.assert_called_once_with(
            f'{text_to_encode}\n\n'
        )

    def test_clean_max_chars(self, text_to_encode, mock_builtins_open):
        # Setup
        sys_args = ['--clean', '--max-chars=7', 'test.txt']

        # Run
        main(sys_args)

        # Verify
        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-clean.txt', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls
        words = text_to_encode.split()
        mock_builtins_open().write.assert_called_once_with(
            f'{words[0]}\n\n{words[1]}\n\n'
        )

    def test_plan(self, mock_builtins_open, mock_google):
        # Setup
        sys_args = [
            '--encoder=google',
            '--voice-id=A',
            '--plan',
            'test.txt'
        ]

        # Run
        main(sys_args)

        # Verify
        mock_google.client_cls.assert_called_once_with()
        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-plan.json', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls

    def test_delete_history(self, mock_elevenlabs):
        # Setup
        sys_args = [
            '--encoder=elevenlabs',
            '--delete-history'
        ]
        mock_history_item = MagicMock()
        mock_elevenlabs.history.from_api.return_value = [mock_history_item]

        # Run
        main(sys_args)

        # Verify
        mock_elevenlabs.history.from_api.assert_called_once()
        mock_history_item.delete.assert_called_once()

    def test_google_delete_history(self, mock_google, capfd):
        # Setup
        sys_args = [
            '--encoder=google',
            '--delete-history'
        ]

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        mock_google.client_cls.assert_not_called()
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert (
            'The "elevenlabs" encoder must be specified to delete history' in
            out
        )
