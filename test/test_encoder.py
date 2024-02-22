from pathlib import Path
from unittest.mock import call

from google.cloud.texttospeech import SynthesisInput

from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.manifest import Manifest
from zaphodvox.text import parse_text


class TestEncoder():
    def test_encode(
        self, audio_encoding, google_voice, mock_audio, mock_builtins_open,
        mock_google, mock_progress_bar
    ):
        # Setup
        full_text = "Paragraph 1\n\nParagraph 2\nParagraph 3"
        basename = 'output'
        path = Path('/path/to')
        fragments = parse_text(full_text, voice=google_voice)
        manifest = Manifest.plan(
            fragments, basename, 'wav', silence_duration=100
        )
        mock_write = mock_builtins_open.return_value.write
        mock_audio_segment_cls, mock_audio_segment = mock_audio

        # Run
        GoogleEncoder().encode_manifest(manifest, path, silence_duration=100)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Google client synthesize_speech
        assert mock_google.client.synthesize_speech.call_count == 3
        # Fragment #0
        mock_google.client.synthesize_speech.assert_any_call(request={
            'input': SynthesisInput(ssml='<speak>Paragraph 1</speak>'),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(audio_encoding)
        })
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00000.wav'), 'wb'
        )
        assert mock_write.call_args_list[0] == call(mock_google.audio_content)
        # Fragment #1
        mock_audio_segment_cls.silent.assert_called_once_with(duration=100)
        mock_audio_segment.export.assert_called_once_with(
            str(path / f'{basename}-00001.wav'), format='wav'
        )
        # Fragment #2
        mock_google.client.synthesize_speech.assert_any_call(request={
            'input': SynthesisInput(ssml='<speak>Paragraph 2</speak>'),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(audio_encoding)
        })
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00002.wav'), 'wb'
        )
        assert mock_write.call_args_list[1] == call(mock_google.audio_content)
        # Fragment #3
        mock_google.client.synthesize_speech.assert_any_call(request={
            'input': SynthesisInput(ssml='<speak>Paragraph 3</speak>'),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(audio_encoding)
        })
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00003.wav'), 'wb'
        )
        assert mock_write.call_args_list[2] == call(mock_google.audio_content)
        # Progress bar
        mock_progress_bar.encoder.assert_called_once_with(
            'Encoding', total=sum(len(t) for t in full_text.split('\n'))
        )

    def test_encode_max_chars(
        self, audio_encoding, google_voice, mock_audio, mock_builtins_open,
        mock_google, mock_progress_bar
    ):
        # Setup
        full_text = "Paragraph 1\n\nParagraph 2\nParagraph 3"
        basename = 'output'
        path = Path('/path/to')
        fragments = parse_text(full_text, voice=google_voice, max_chars=30)
        manifest = Manifest.plan(
            fragments, basename, 'wav', silence_duration=100
        )
        mock_write = mock_builtins_open.return_value.write
        mock_audio_segment_cls, mock_audio_segment = mock_audio

        # Run
        GoogleEncoder().encode_manifest(manifest, path, silence_duration=100)

        # Verify
        # Google client
        mock_google.client_cls.assert_called_once_with()
        # Google client synthesize_speech
        assert mock_google.client.synthesize_speech.call_count == 2
        mock_audio_segment_cls.silent.assert_not_called()
        # Fragment #0
        mock_audio_segment.export.assert_not_called()
        mock_google.client.synthesize_speech.assert_any_call(request={
            'input': SynthesisInput(
                ssml='<speak>Paragraph 1\n <break time=\"0.100s\" /> '
                'Paragraph 2\n</speak>'
            ),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(audio_encoding)
        })
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00000.wav'), 'wb'
        )
        assert mock_write.call_args_list[0] == call(mock_google.audio_content)
        # Fragment #1
        mock_google.client.synthesize_speech.assert_any_call(request={
            'input': SynthesisInput(ssml='<speak>Paragraph 3</speak>'),
            'voice': google_voice.voice_selection_params,
            'audio_config': google_voice.get_audio_config(audio_encoding)
        })
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00001.wav'), 'wb'
        )
        assert mock_write.call_args_list[1] == call(mock_google.audio_content)
        # Progress bar
        mock_progress_bar.encoder.assert_called_once_with(
            'Encoding', total=(
                sum(len(t) for t in full_text.split('\n')) +
                len('\n <break time=\"0.100s\"/> ') + 2 # newlines
            )
        )
