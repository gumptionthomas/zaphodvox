import json
from pathlib import Path
from unittest.mock import call, mock_open

import pytest

from zaphodvox.arg_parser import parse_args
from zaphodvox.main import main
from zaphodvox.qwen.encoder import DEFAULT_URL


AUDITION_INDEX = json.dumps([
    {'seed': 0, 'filename': 'ryan-audition-00.wav', 'voice_id': 'Ryan',
     'instruct': 'calm', 'language': 'English', 'temperature': 0.6,
     'text': 'Sample reference line for the narrator voice.'},
    {'seed': 1, 'filename': 'ryan-audition-01.wav', 'voice_id': 'Ryan',
     'instruct': 'calm', 'language': 'English', 'temperature': 0.6,
     'text': 'Sample reference line for the narrator voice.'},
])


def speech_call(text, voice_id='Ryan', url=DEFAULT_URL, language='English',
                audio_format='wav'):
    return call(
        f'{url}/v1/audio/speech',
        json={
            'input': text,
            'voice': voice_id,
            'language': language,
            'response_format': audio_format,
        }
    )


class TestMain():
    def test_main(
        self, mock_audio, mock_builtins_open, mock_qwen, text_to_encode,
        tmp_path, voices_json_data
    ):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--voice-name=voice_1',
            '--voices-file=voices.json',
            '--encode',
            f'--out-dir={str(tmp_path)}',
            '--concat',
            '--concat-out=.',
            'test.txt'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=text_to_encode).return_value,
            mock_open(read_data=voices_json_data).return_value,
            mock_builtins_open.return_value,
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call('test.txt', 'r')
        # Voices file
        mock_builtins_open.assert_any_call('voices.json', 'r')
        # Synthesis
        mock_qwen.post.assert_called_once_with(*speech_call(text_to_encode).args,
                                               **speech_call(text_to_encode).kwargs)
        mock_qwen.write_bytes.assert_called_once_with(
            tmp_path / 'test-00000.wav', b'audio'
        )
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat file
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment_cls.from_file.assert_called_once_with(
            str(tmp_path / 'test-00000.wav'), format='wav'
        )
        mock_audio.segment.export.assert_called_once_with(
            'test.wav', format='wav'
        )
        # Manifest file
        mock_builtins_open.assert_any_call(
            str(tmp_path / 'test-manifest.json'), 'w'
        )
        assert mock_write.call_count == 1
        assert mock_builtins_open.call_count == 3

    def test_main_manifest(
        self, mock_audio, mock_builtins_open, mock_qwen, manifest_json_data
    ):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--basename=test',
            '--encode',
            '--concat',
            '--silence-duration=42',
            '--indexes=0, 2,4 ',
            'test-manifest.json'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=manifest_json_data).return_value,
            mock_builtins_open.return_value,
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call('test-manifest.json', 'r')
        # Two text fragments (#0 and #2) synthesized
        assert mock_qwen.post.call_count == 2
        # Fragment #0
        mock_qwen.post.assert_has_calls([speech_call('Text 0')])
        mock_qwen.write_bytes.assert_any_call(Path('test-00000.wav'), b'audio')
        # Fragment #2
        mock_qwen.post.assert_has_calls([speech_call('Text 2')])
        mock_qwen.write_bytes.assert_any_call(Path('test-00002.wav'), b'audio')
        assert mock_qwen.write_bytes.call_count == 2
        # Fragment #4 (silence)
        mock_audio.segment_cls.silent.assert_called_once_with(duration=42)
        mock_audio.segment.export.assert_any_call(
            'test-00004.wav', format='wav'
        )
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment.export.assert_any_call('test.wav', format='wav')
        assert mock_audio.segment.export.call_count == 2
        # Manifest file
        mock_builtins_open.assert_any_call('test-manifest.json', 'w')
        assert mock_write.call_count == 1

    def test_main_manifest_inline_voice(
        self, mock_audio, mock_builtins_open, mock_qwen,
        inline_voice_manifest_json_data, text_to_encode
    ):
        # A manifest carrying an inline voice (no voice_name, no voices map)
        # must re-encode without re-specifying a voice.
        sys_args = [
            '--encoder=qwen',
            '--basename=test',
            '--encode',
            'test-manifest.json'
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data=inline_voice_manifest_json_data).return_value,
            mock_builtins_open.return_value,
        )

        # Run
        main(sys_args)

        # Verify: synthesized using the manifest's own inline voice
        mock_qwen.post.assert_called_once_with(
            *speech_call(text_to_encode).args,
            **speech_call(text_to_encode).kwargs
        )
        mock_qwen.write_bytes.assert_called_once_with(
            Path('test-00000.wav'), b'audio'
        )

    def test_main_manifest_no_voice(
        self, capfd, mock_audio, mock_builtins_open, mock_qwen,
        no_voice_manifest_json_data
    ):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--basename=test',
            '--encode',
            '--concat',
            'test-manifest.json'
        ]
        mock_builtins_open.return_value = mock_open(
            read_data=no_voice_manifest_json_data
        ).return_value

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        mock_builtins_open.assert_called_once_with('test-manifest.json', 'r')
        mock_qwen.post.assert_not_called()
        mock_audio.segment_cls.silent.assert_not_called()
        mock_audio.segment_cls.empty.assert_not_called()
        mock_audio.segment.export.assert_not_called()
        assert mock_builtins_open.call_count == 1
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No voice specified' in out

    def test_main_manifest_incorrect_voice(
        self, capfd, incorrect_voice_manifest_json_data, mock_audio,
        mock_builtins_open, mock_qwen
    ):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--basename=test',
            '--encode',
            '--concat',
            'test-manifest.json'
        ]
        mock_builtins_open.return_value = mock_open(
            read_data=incorrect_voice_manifest_json_data
        ).return_value

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        mock_builtins_open.assert_called_once_with('test-manifest.json', 'r')
        mock_qwen.post.assert_not_called()
        mock_audio.segment_cls.silent.assert_not_called()
        mock_audio.segment_cls.empty.assert_not_called()
        mock_audio.segment.export.assert_not_called()
        assert mock_builtins_open.call_count == 1
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No voice specified' in out

    def test_main_encode_exception(
        self, capfd, mock_audio, mock_builtins_open, mock_qwen, text_to_encode
    ):
        # Setup
        error = 'encode exception'
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--encode',
            '--concat',
            'test.txt'
        ]
        mock_qwen.response.raise_for_status.side_effect = Exception(error)

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call('test.txt', 'r')
        mock_builtins_open().read.assert_called_once()
        # 5 tries
        assert mock_qwen.post.call_count == 5
        assert mock_qwen.post.call_args_list == [
            speech_call(text_to_encode)
        ] * 5
        mock_qwen.write_bytes.assert_not_called()
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
        self, capfd, mock_audio, mock_builtins_open, mock_qwen, text_to_encode
    ):
        # Setup
        error = 'export error'
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--encode',
            '--concat',
            'test.txt'
        ]
        mock_write = mock_builtins_open.return_value.write
        mock_audio.segment.export.side_effect = Exception(error)

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        # Input file
        mock_builtins_open.assert_any_call('test.txt', 'r')
        mock_builtins_open().read.assert_called_once()
        # Synthesis succeeded once
        mock_qwen.post.assert_called_once_with(
            *speech_call(text_to_encode).args,
            **speech_call(text_to_encode).kwargs
        )
        mock_qwen.write_bytes.assert_called_once_with(
            Path('test-00000.wav'), b'audio'
        )
        # No silence
        mock_audio.segment_cls.silent.assert_not_called()
        # Concat files
        mock_audio.segment_cls.empty.assert_called_once()
        mock_audio.segment.export.assert_called_once_with(
            'test.wav', format='wav'
        )
        # Manifest file written before concat
        mock_builtins_open.assert_any_call('test-manifest.json', 'w')
        assert mock_write.call_count == 1
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
        assert 'version 2.0.0' in out

    def test_nothing_to_do(self, capfd, mock_builtins_open):
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

    def test_no_inputfile(self, capfd, mock_builtins_open):
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

    def test_nonexistant_inputfile(self, capfd):
        # Setup
        sys_args = ['--encoder=qwen', '--encode', 'test.txt']
        args = parse_args(sys_args)

        # Run
        with pytest.raises(SystemExit) as se:
            main(preparsed_args=args)

        # Verify
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No such file' in out

    def test_no_encoder(self, capfd, mock_builtins_open):
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
        self, capfd, manifest_json_data, mock_builtins_open
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

    def test_invalid_encoder(self, capfd, mock_builtins_open):
        # Setup
        sys_args = ['--encoder=qwen', '--encode', 'test.txt']
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

    def test_clean(self, mock_builtins_open, text_to_encode):
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

    def test_clean_max_chars(self, mock_builtins_open, text_to_encode):
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

    def test_plan(self, mock_builtins_open):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--plan',
            'test.txt'
        ]

        # Run
        main(sys_args)

        # Verify
        expected_calls = [
            call(filename, mode) for filename, mode in [
                ('test.txt', 'r'),
                ('test-plan.json', 'w')
            ]
        ]
        assert mock_builtins_open.call_args_list == expected_calls

    def test_plan_no_voice(self, capfd, mock_builtins_open, voices_json_data):
        # Setup
        sys_args = [
            '--encoder=qwen',
            '--voices-file=voices.json',
            '--plan',
            'test.txt'
        ]
        text = 'ZVOX: voice_1\nThis is\nZVOX: voice_null\na test'
        mock_builtins_open.side_effect = (
            mock_open(read_data=text).return_value,
            mock_open(read_data=voices_json_data).return_value
        )

        # Run
        with pytest.raises(SystemExit) as se:
            main(sys_args)

        # Verify
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'No voice specified for name "voice_null"' in out


class TestAudition():
    def test_audition(self, mock_qwen, mock_builtins_open):
        # Setup: three candidates of a preset voice, no input file.
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--audition=3',
            '--audition-text=A sufficiently long sample sentence for the '
            'narrator so the reference clip is a usable length for cloning.',
        ]

        # Run
        main(sys_args)

        # Verify: one request per seed 0..2, each carrying its seed.
        assert mock_qwen.post.call_count == 3
        seeds = [c.kwargs['json']['seed'] for c in mock_qwen.post.call_args_list]
        assert seeds == [0, 1, 2]
        # Candidate files are named by seed (basename defaults to the voice id).
        for seed in range(3):
            mock_qwen.write_bytes.assert_any_call(
                Path(f'ryan-audition-0{seed}.wav'), b'audio'
            )
        assert mock_qwen.write_bytes.call_count == 3
        # The index file is written.
        mock_builtins_open.assert_any_call('ryan-audition.json', 'w')

    def test_audition_applies_temperature(self, mock_qwen, mock_builtins_open):
        # --voice-temperature is fixed across all candidates (seed varies).
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--voice-temperature=0.6',
            '--audition=2',
            '--audition-text=A sufficiently long sample sentence for the '
            'narrator so the reference clip is a usable length for cloning.',
        ]

        # Run
        main(sys_args)

        # Verify: every candidate carries the same temperature.
        temps = [
            c.kwargs['json']['temperature']
            for c in mock_qwen.post.call_args_list
        ]
        assert temps == [0.6, 0.6]

    def test_audition_design(self, mock_qwen, mock_builtins_open):
        # Auditioning a designed voice posts to the design endpoint.
        sys_args = [
            '--encoder=qwen',
            '--voice-description=a warm elderly woman',
            '--audition=2',
            '--audition-text=A sufficiently long sample sentence for the '
            'narrator so the reference clip is a usable length for cloning.',
        ]

        # Run
        main(sys_args)

        # Verify: each candidate is a design request, seeds vary.
        assert mock_qwen.post.call_count == 2
        for c in mock_qwen.post.call_args_list:
            assert c.args[0].endswith('/v1/audio/speech/design')
            assert c.kwargs['json']['voice_description'] == (
                'a warm elderly woman'
            )
        seeds = [c.kwargs['json']['seed'] for c in mock_qwen.post.call_args_list]
        assert seeds == [0, 1]
        # basename defaults to 'design' when there is no input file or voice id.
        mock_builtins_open.assert_any_call('design-audition.json', 'w')
        mock_qwen.write_bytes.assert_any_call(
            Path('design-audition-00.wav'), b'audio'
        )

    def test_audition_uses_inputfile_text(self, mock_qwen, mock_builtins_open):
        # Setup: no --audition-text, so the input file's first line is used.
        sys_args = [
            '--encoder=qwen',
            '--voice-id=Ryan',
            '--audition=1',
            'sample.txt',
        ]
        mock_builtins_open.side_effect = (
            mock_open(read_data='First line is the sample.\nSecond.').return_value,
            mock_builtins_open.return_value,
        )

        # Run
        main(sys_args)

        # Verify: synthesized the first line; basename comes from the inputfile.
        assert mock_qwen.post.call_args.kwargs['json']['input'] == (
            'First line is the sample.'
        )
        mock_qwen.write_bytes.assert_called_once_with(
            Path('sample-audition-00.wav'), b'audio'
        )

    def test_audition_requires_voice_id(self, capfd, mock_qwen):
        with pytest.raises(SystemExit) as se:
            main(['--encoder=qwen', '--audition=2', '--audition-text=hello'])
        assert se.value.code == 1
        assert 'requires a preset' in capfd.readouterr()[0]

    def test_audition_rejects_clone(self, capfd, mock_qwen):
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder=qwen', '--voice-id=Ryan', '--voice-ref-audio=ref.wav',
                '--audition=2', '--audition-text=hello'
            ])
        assert se.value.code == 1
        assert 'do not supply' in capfd.readouterr()[0]

    def test_audition_rejects_other_actions(self, capfd, mock_qwen):
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder=qwen', '--voice-id=Ryan', '--audition=2',
                '--audition-text=hello', '--encode', 'test.txt'
            ])
        assert se.value.code == 1
        assert 'cannot be combined' in capfd.readouterr()[0]

    def test_audition_no_text(self, capfd, mock_qwen):
        with pytest.raises(SystemExit) as se:
            main(['--encoder=qwen', '--voice-id=Ryan', '--audition=2'])
        assert se.value.code == 1
        assert 'No audition text specified' in capfd.readouterr()[0]


class TestAdopt():
    def test_adopt_creates_voices_file(self, mock_builtins_open):
        # Setup: adopt candidate seed 1; the voices file does not exist yet.
        mock_builtins_open.side_effect = (
            mock_open(read_data=AUDITION_INDEX).return_value,  # index read
            FileNotFoundError(),                               # voices missing
            mock_builtins_open.return_value,                   # voices write
        )
        mock_write = mock_builtins_open.return_value.write
        sys_args = [
            '--adopt=1',
            '--voice-name=Narrator',
            '--voices-file=voices.json',
            'refs/ryan-audition.json',
        ]

        # Run
        main(sys_args)

        # Verify: a clone entry is written, resolving the clip beside the index.
        mock_builtins_open.assert_any_call('voices.json', 'w')
        written = json.loads(mock_write.call_args[0][0])
        assert written == {
            'voices': {
                'Narrator': {
                    'language': 'English',
                    'ref_audio': 'refs/ryan-audition-01.wav',
                    'ref_text': 'Sample reference line for the narrator voice.',
                    'seed': 1,
                    'temperature': 0.6,
                }
            }
        }

    def test_adopt_merges_into_existing(self, mock_builtins_open):
        # Setup: an existing voices file with another voice.
        existing = json.dumps(
            {'voices': {'Ford': {'voice_id': 'Dylan', 'language': 'English'}}}
        )
        mock_builtins_open.side_effect = (
            mock_open(read_data=AUDITION_INDEX).return_value,
            mock_open(read_data=existing).return_value,
            mock_builtins_open.return_value,
        )
        mock_write = mock_builtins_open.return_value.write

        # Run
        main([
            '--adopt=0', '--voice-name=Narrator',
            '--voices-file=voices.json', 'ryan-audition.json'
        ])

        # Verify: both the old and new voices are present.
        written = json.loads(mock_write.call_args[0][0])
        assert set(written['voices']) == {'Ford', 'Narrator'}
        assert written['voices']['Narrator']['ref_audio'] == (
            'ryan-audition-00.wav'
        )

    def test_adopt_seed_not_found(self, capfd, mock_builtins_open):
        mock_builtins_open.return_value = mock_open(
            read_data=AUDITION_INDEX
        ).return_value
        with pytest.raises(SystemExit) as se:
            main([
                '--adopt=9', '--voice-name=Narrator',
                '--voices-file=voices.json', 'ryan-audition.json'
            ])
        assert se.value.code == 1
        assert 'No audition candidate for seed 9' in capfd.readouterr()[0]

    def test_adopt_requires_voice_name(self, capfd, mock_builtins_open):
        with pytest.raises(SystemExit) as se:
            main(['--adopt=1', '--voices-file=voices.json', 'idx.json'])
        assert se.value.code == 1
        assert '--adopt requires --voice-name' in capfd.readouterr()[0]

    def test_adopt_requires_voices_file(self, capfd, mock_builtins_open):
        with pytest.raises(SystemExit) as se:
            main(['--adopt=1', '--voice-name=Narrator', 'idx.json'])
        assert se.value.code == 1
        assert '--adopt requires --voices-file' in capfd.readouterr()[0]
