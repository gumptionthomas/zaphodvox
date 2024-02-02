from pathlib import Path
from unittest.mock import call, patch

from google.cloud.texttospeech import AudioEncoding, SynthesisInput

from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.manifest import Manifest
from zaphodvox.text import parse_text
from zaphodvox.googlecloud.voice import GoogleVoice


class TestEncoder():
    @patch('zaphodvox.encoder.ProgressBar')
    def test_encode(
        self, mock_progress_bar, mock_builtins_open, mock_google,
        mock_audio
    ):
        # Setup
        full_text = "Paragraph 1\n\nParagraph 2\nParagraph 3"
        basename = 'output'
        path = Path('/path/to')
        voice = GoogleVoice(
            voice_id='A', language='en', region='UK', type='Wavenet'
        )
        fragments = parse_text(full_text, voice=voice)
        manifest = Manifest.plan(
            fragments, basename, 'wav',
            silence_duration=100
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
        request = {
            'input': SynthesisInput(text='Paragraph 1'),
            'voice': voice.voice_selection_params,
            'audio_config': voice.get_audio_config(AudioEncoding.LINEAR16)
        }
        mock_google.client.synthesize_speech.assert_any_call(request=request)
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
        request = {
            'input': SynthesisInput(text='Paragraph 2'),
            'voice': voice.voice_selection_params,
            'audio_config': voice.get_audio_config(AudioEncoding.LINEAR16)
        }
        mock_google.client.synthesize_speech.assert_any_call(request=request)
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00002.wav'), 'wb'
        )
        assert mock_write.call_args_list[1] == call(mock_google.audio_content)
        # Fragment #3
        request = {
            'input': SynthesisInput(text='Paragraph 3'),
            'voice': voice.voice_selection_params,
            'audio_config': voice.get_audio_config(AudioEncoding.LINEAR16)
        }
        mock_google.client.synthesize_speech.assert_any_call(request=request)
        mock_builtins_open.assert_any_call(
            str(path / f'{basename}-00003.wav'), 'wb'
        )
        assert mock_write.call_args_list[2] == call(mock_google.audio_content)
        # No other synthesize_speech calls
        assert mock_google.client.synthesize_speech.call_count == 3
        # Progress bar
        mock_progress_bar.assert_called_once_with(
            'Encode', total=sum(len(t) for t in full_text.split('\n'))
        )
