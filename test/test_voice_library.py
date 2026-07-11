import json
from pathlib import Path

import pytest

from zaphodvox.main import main


class TestVoiceLibrary():
    """Drives the CLI against a voice library that lives outside the project.

    Deliberately unmocked file I/O: the rest of the suite patches
    `builtins.open`, which is exactly what hid the fact that a reference audio
    path was only ever resolved against the working directory. These tests read
    a real voices file and open a real reference clip, so they fail if a path is
    anchored to the wrong directory.
    """

    @pytest.fixture
    def library(self, tmp_path) -> Path:
        """A shared voice library: a voices file and its clip, together."""
        library = tmp_path / 'voices'
        library.mkdir()
        (library / 'narrator.wav').write_bytes(b'RIFFfake')
        (library / 'library.json').write_text(
            json.dumps({
                'voices': {
                    'narrator': {
                        'ref_audio': 'narrator.wav',
                        'ref_text': 'A sample sentence.',
                        'seed': 42,
                    }
                }
            }),
            encoding='utf-8'
        )
        return library

    @pytest.fixture
    def project(self, tmp_path, monkeypatch) -> Path:
        """A project directory elsewhere, which is where commands are run."""
        project = tmp_path / 'books' / 'hitchhiker'
        project.mkdir(parents=True)
        (project / 'book.txt').write_text('Hello there.\n', encoding='utf-8')
        monkeypatch.chdir(project)
        return project

    def _opened_ref(self, mock_qwen) -> Path:
        """The reference clip the encoder actually opened and uploaded."""
        files = mock_qwen.post.call_args.kwargs['files']
        return Path(files['voice_file'].name)

    def test_encode_opens_clip_beside_its_voices_file(
        self, library, project, mock_qwen, mock_progress_bar
    ):
        # Run: from the project, using the library in another directory.
        main([
            '--encoder-name', 'qwen', '--encode',
            '-f', str(library / 'library.json'), '-n', 'narrator',
            'book.txt',
        ])

        # Verify: `narrator.wav` resolved against the library, not the project.
        assert self._opened_ref(mock_qwen) == library / 'narrator.wav'

    def test_manifest_reencodes_on_its_own(
        self, library, project, mock_qwen, mock_progress_bar
    ):
        # Setup: encode once, which writes a manifest carrying the voice.
        main([
            '--encoder-name', 'qwen', '--encode',
            '-f', str(library / 'library.json'), '-n', 'narrator',
            'book.txt',
        ])
        mock_qwen.post.reset_mock()

        # Run: re-encode from the manifest alone, with no --voices-file. The
        # voice's path was written relative to the library, so it has to have
        # been rewritten on the way into the manifest to still mean anything
        # from here.
        main([
            '--encoder-name', 'qwen', '--encode', '-i', '0',
            'book-manifest.json',
        ])

        # Verify: it still finds the same clip.
        assert self._opened_ref(mock_qwen) == library / 'narrator.wav'

    def test_manifest_does_not_inherit_the_bare_library_filename(
        self, library, project, mock_qwen, mock_progress_bar
    ):
        # Run
        main([
            '--encoder-name', 'qwen', '--encode',
            '-f', str(library / 'library.json'), '-n', 'narrator',
            'book.txt',
        ])

        # Verify: copying `narrator.wav` verbatim into the project's manifest
        # would silently repoint it at a file that does not exist here.
        manifest = json.loads(
            (project / 'book-manifest.json').read_text(encoding='utf-8')
        )
        # Whether it was rewritten absolute or `~`-anchored depends on where the
        # temp directory falls relative to the home directory (on Windows it is
        # inside it), so assert the invariant rather than the spelling: it is no
        # longer the bare library filename, and it still points at the clip.
        ref_audio = manifest['fragments'][0]['voice']['ref_audio']
        assert ref_audio != 'narrator.wav'
        assert Path(ref_audio).expanduser() == library / 'narrator.wav'

    def test_zvox_tagged_manifest_reencodes_on_its_own(
        self, library, project, mock_qwen, mock_progress_bar
    ):
        # Setup: selecting the voice inline, which is how a library with several
        # voices gets used. This records a `voice_name`, so the voice is written
        # into the manifest's own `voices` block rather than onto the fragment.
        (project / 'book.txt').write_text(
            'ZVOX: narrator\nHello there.\n', encoding='utf-8'
        )
        main([
            '--encoder-name', 'qwen', '--encode',
            '-f', str(library / 'library.json'), 'book.txt',
        ])
        manifest = json.loads(
            (project / 'book-manifest.json').read_text(encoding='utf-8')
        )
        assert manifest['voices']['narrator']['ref_audio'] != 'narrator.wav'
        mock_qwen.post.reset_mock()

        # Run: re-encode from the manifest alone.
        main([
            '--encoder-name', 'qwen', '--encode', '-i', '0',
            'book-manifest.json',
        ])

        # Verify
        assert self._opened_ref(mock_qwen) == library / 'narrator.wav'

    def test_voices_file_env_var_is_the_default(
        self, library, project, mock_qwen, mock_progress_bar, monkeypatch
    ):
        # Setup: point at the library once, for every project.
        monkeypatch.setenv(
            'ZAPHODVOX_VOICES_FILE', str(library / 'library.json')
        )

        # Run: no -f.
        main([
            '--encoder-name', 'qwen', '--encode', '-n', 'narrator', 'book.txt',
        ])

        # Verify
        assert self._opened_ref(mock_qwen) == library / 'narrator.wav'

    def test_missing_reference_audio_fails_before_encoding(
        self, library, project, mock_qwen, mock_progress_bar, capfd
    ):
        # Setup
        (library / 'narrator.wav').unlink()

        # Run
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder-name', 'qwen', '--encode',
                '-f', str(library / 'library.json'), '-n', 'narrator',
                'book.txt',
            ])

        # Verify: it names the path it looked at, and nothing was synthesized.
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        assert 'narrator.wav' in out
        assert not mock_qwen.post.called


class TestAdoptPaths():
    """`--adopt` writes a clone voice into a voices file."""

    @pytest.fixture
    def audition(self, tmp_path, monkeypatch) -> Path:
        """An audition index and its candidate clip, in a library directory."""
        library = tmp_path / 'voices'
        library.mkdir()
        (library / 'book-audition-3.wav').write_bytes(b'RIFFfake')
        (library / 'book-audition.json').write_text(
            json.dumps([{
                'seed': 3,
                'filename': 'book-audition-3.wav',
                'text': 'A sample sentence.',
                'language': 'English',
            }]),
            encoding='utf-8'
        )
        monkeypatch.chdir(tmp_path)
        return library

    def test_adopt_keeps_a_bare_filename_beside_the_voices_file(
        self, audition, capfd
    ):
        # Run: from the parent directory, so the clip is reached as
        # `voices/book-audition-3.wav` -- a path that is only valid from here.
        main([
            '--adopt', '3', '-n', 'narrator',
            '-f', str(audition / 'library.json'),
            str(audition / 'book-audition.json'),
        ])

        # Verify: the library stays self-contained, so it can be moved or
        # committed as a unit.
        voices = json.loads(
            (audition / 'library.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['narrator']['ref_audio'] == (
            'book-audition-3.wav'
        )
