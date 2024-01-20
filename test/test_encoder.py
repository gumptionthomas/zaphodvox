from pathlib import Path
from unittest.mock import call, mock_open, patch

from zaphodvox.googlecloud.encoder import GoogleEncoder
from zaphodvox.manifest import Manifest
from zaphodvox.text import parse_text
from zaphodvox.googlecloud.voice import GoogleVoice


@patch('builtins.open', new_callable=mock_open)
@patch('zaphodvox.googlecloud.encoder.TextToSpeechClient')
class TestEncoder():
    @patch('shutil.copy')
    @patch('zaphodvox.audio.AudioSegment')
    @patch('zaphodvox.googlecloud.encoder.GoogleEncoder.t2s')
    @patch('zaphodvox.encoder.ProgressBar')
    def test_encode(
        self, mock_progress_bar, mock_t2s, *args
    ):
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

        GoogleEncoder().encode_manifest(manifest, path, silence_duration=100)

        expected_calls = [
            call(text, voice, path) for text, path in [
                ('Paragraph 1', path / f'{basename}-00000.wav'),
                # Skip {basename}-00001.wav because of silent text fragment
                ('Paragraph 2', path / f'{basename}-00002.wav'),
                ('Paragraph 3', path / f'{basename}-00003.wav')
            ]
        ]
        mock_t2s.assert_has_calls(expected_calls)
        mock_progress_bar.assert_called_once_with(
            'Encode', total=sum(len(t) for t in full_text.split('\n'))
        )
        mock_progress_bar.return_value.__enter__.assert_called_once()
        mock_progress_bar.return_value.__exit__.assert_called_once()
