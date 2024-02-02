from unittest.mock import patch

from zaphodvox.progress import ProgressBar


class TestProgressBar():
    @patch('zaphodvox.progress.Live')
    @patch('zaphodvox.progress.Panel')
    @patch('zaphodvox.progress.Progress')
    def test_progress_bar(self, mock_progress, mock_panel, mock_live):
        # Setup
        mock_progress().add_task.return_value = 1234

        # Run
        with ProgressBar('Test', total=10) as bar:
            bar.next()

        # Verify
        mock_progress().add_task.assert_called_once()
        mock_progress().advance.assert_called_once()
        mock_panel.assert_not_called()
        mock_live.assert_called_once()
