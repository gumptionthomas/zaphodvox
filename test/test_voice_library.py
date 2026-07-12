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

    def test_missing_reference_audio_names_the_anchor_directory(
        self, library, project, monkeypatch, mock_qwen, mock_progress_bar,
        capfd
    ):
        # Setup: run from the library, naming the voices file bare, so its
        # directory is `.` -- an anchor that tells the reader nothing.
        (library / 'narrator.wav').unlink()
        monkeypatch.chdir(library)

        # Run
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder-name', 'qwen', '--encode',
                '-f', 'library.json', '-n', 'narrator',
                str(project / 'book.txt'),
            ])

        # Verify: the anchor is the directory itself, not `.`. Compare with
        # whitespace stripped, since the console wraps long paths.
        assert se.value.code == 1
        out, _ = capfd.readouterr()
        printed = ''.join(out.split())
        assert 'resolvedagainst"."' not in printed
        assert ''.join(str(library).split()) in printed


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
        # committed as a unit -- and the clip is named for the voice, not for
        # the audition it came out of.
        voices = json.loads(
            (audition / 'library.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['narrator']['ref_audio'] == 'narrator.wav'
        assert (audition / 'narrator.wav').read_bytes() == b'RIFFfake'

    def test_adopt_copies_the_clip_out_of_a_scratch_directory(
        self, tmp_path, monkeypatch, capfd
    ):
        # Setup: the intended workflow -- audition into a scratch directory, so
        # the library never fills up with candidates. The library holds only a
        # voices file, so the chosen clip has to be brought in.
        library = tmp_path / 'voices'
        refs = library / 'refs'
        refs.mkdir(parents=True)
        (refs / 'narrator-audition-05.wav').write_bytes(b'RIFFchosen')
        (refs / 'narrator-audition-01.wav').write_bytes(b'RIFFrejected')
        (refs / 'narrator-audition.json').write_text(
            json.dumps([
                {'seed': 5, 'filename': 'narrator-audition-05.wav',
                 'text': 'A sample sentence.', 'language': 'English'},
                {'seed': 1, 'filename': 'narrator-audition-01.wav',
                 'text': 'A sample sentence.', 'language': 'English'},
            ]),
            encoding='utf-8'
        )
        monkeypatch.chdir(library)

        # Run
        main([
            '--adopt', '5', '-n', 'Narrator',
            '-f', 'library.json',
            'refs/narrator-audition.json',
        ])

        # Verify: the winner is copied in under the voice's name, and the entry
        # points at the library's own copy -- not into the scratch directory,
        # which can now be deleted wholesale.
        assert (library / 'Narrator.wav').read_bytes() == b'RIFFchosen'
        voices = json.loads(
            (library / 'library.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator']['ref_audio'] == 'Narrator.wav'
        # Nothing is deleted: adopting a different seed later still works.
        assert (refs / 'narrator-audition-01.wav').exists()
        assert (refs / 'narrator-audition-05.wav').exists()

    def test_adopt_into_a_clips_subdirectory(
        self, tmp_path, monkeypatch, capfd
    ):
        # Setup: a library that keeps its clips in their own subdirectory.
        #   [library]/voices.json
        #   [library]/clips/*.wav
        library = tmp_path / 'library'
        refs = library / 'ref'
        refs.mkdir(parents=True)
        (refs / 'narrator-audition-05.wav').write_bytes(b'RIFFchosen')
        (refs / 'narrator-audition.json').write_text(
            json.dumps([{
                'seed': 5, 'filename': 'narrator-audition-05.wav',
                'text': 'A sample sentence.', 'language': 'English',
            }]),
            encoding='utf-8'
        )
        monkeypatch.chdir(library)

        # Run: --clips-dir is relative to the voices file, and does not exist
        # yet.
        main([
            '--adopt', '5', '-n', 'Narrator',
            '-f', 'voices.json', '--clips-dir', 'clips',
            'ref/narrator-audition.json',
        ])

        # Verify: the clip lands in clips/, and the reference stays relative to
        # the voices file -- so the library is still movable as a unit.
        assert (library / 'clips' / 'Narrator.wav').read_bytes() == b'RIFFchosen'
        voices = json.loads(
            (library / 'voices.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator']['ref_audio'] == 'clips/Narrator.wav'

    def test_clips_dir_env_var_is_the_default(
        self, tmp_path, monkeypatch, capfd
    ):
        # Setup: set the layout once, for every project.
        library = tmp_path / 'library'
        library.mkdir()
        (library / 'narrator-audition-05.wav').write_bytes(b'RIFFchosen')
        (library / 'audition.json').write_text(
            json.dumps([{
                'seed': 5, 'filename': 'narrator-audition-05.wav',
                'text': 'A sample sentence.', 'language': 'English',
            }]),
            encoding='utf-8'
        )
        monkeypatch.chdir(library)
        monkeypatch.setenv('ZAPHODVOX_CLIPS_DIR', 'clips')

        # Run: no --clips-dir.
        main([
            '--adopt', '5', '-n', 'Narrator',
            '-f', 'voices.json', 'audition.json',
        ])

        # Verify
        assert (library / 'clips' / 'Narrator.wav').is_file()
        voices = json.loads(
            (library / 'voices.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator']['ref_audio'] == 'clips/Narrator.wav'

    def test_adopting_a_clip_already_in_place_does_not_copy_it(
        self, tmp_path, monkeypatch, capfd
    ):
        # Setup: the candidate is already the file the voice would be copied to
        # -- so copying would mean opening it for writing while reading it.
        library = tmp_path / 'voices'
        library.mkdir()
        (library / 'Narrator.wav').write_bytes(b'RIFFfake')
        (library / 'audition.json').write_text(
            json.dumps([{
                'seed': 3, 'filename': 'Narrator.wav',
                'text': 'A sample sentence.', 'language': 'English',
            }]),
            encoding='utf-8'
        )
        monkeypatch.chdir(library)

        # Run
        main([
            '--adopt', '3', '-n', 'Narrator',
            '-f', 'library.json', 'audition.json',
        ])

        # Verify: the clip survives intact and is still referenced.
        assert (library / 'Narrator.wav').read_bytes() == b'RIFFfake'
        voices = json.loads(
            (library / 'library.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator']['ref_audio'] == 'Narrator.wav'

    def test_adopting_twice_replaces_the_clip(self, audition, capfd):
        # Re-adopting a voice refreshes its clip rather than failing.
        adopt_args = [
            '--adopt', '3', '-n', 'narrator',
            '-f', str(audition / 'library.json'),
            str(audition / 'book-audition.json'),
        ]

        # Run
        main(adopt_args)
        main(adopt_args)

        # Verify
        assert (audition / 'narrator.wav').read_bytes() == b'RIFFfake'


class TestAddVoice():
    """`--add-voice` registers a clip you already have, with no audition."""

    @pytest.fixture
    def library(self, tmp_path, monkeypatch) -> Path:
        library = tmp_path / 'library'
        (library / 'clips').mkdir(parents=True)
        (library / 'clips' / 'narrator.wav').write_bytes(b'RIFFhuman')
        monkeypatch.chdir(library)
        return library

    def test_a_clip_already_in_the_library_is_referenced_in_place(
        self, library, capfd
    ):
        # Run
        main([
            '--encoder-name', 'chatterbox', '--add-voice', 'Narrator',
            '-f', 'voices.json', '--clips-dir', 'clips',
            '--voice-ref-audio', 'clips/narrator.wav',
            '--voice-exaggeration', '0.6', '--voice-seed', '42',
        ])

        # Verify: referenced where it lies -- copying it to `clips/Narrator.wav`
        # would duplicate audio that is already in the library.
        voices = json.loads(
            (library / 'voices.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator'] == {
            'encoder': 'chatterbox',
            'ref_audio': 'clips/narrator.wav',
            'exaggeration': 0.6,
            'seed': 42,
        }
        # Compare the directory's actual entries: `Path.exists()` answers for
        # `narrator.wav` on a case-insensitive filesystem (macOS, Windows), and
        # would report a copy that never happened.
        assert [p.name for p in (library / 'clips').iterdir()] == [
            'narrator.wav'
        ]

    def test_a_clip_from_outside_is_copied_in(
        self, library, tmp_path, capfd
    ):
        # Setup: a recording sitting somewhere else entirely.
        outside = tmp_path / 'downloads'
        outside.mkdir()
        (outside / 'recording.wav').write_bytes(b'RIFFhuman')

        # Run
        main([
            '--encoder-name', 'chatterbox', '--add-voice', 'Narrator',
            '-f', 'voices.json', '--clips-dir', 'clips',
            '--voice-ref-audio', str(outside / 'recording.wav'),
        ])

        # Verify: brought into the library, so it holds every clip it refers to.
        assert (library / 'clips' / 'Narrator.wav').read_bytes() == b'RIFFhuman'
        voices = json.loads(
            (library / 'voices.json').read_text(encoding='utf-8')
        )
        assert voices['voices']['Narrator']['ref_audio'] == 'clips/Narrator.wav'

    def test_voices_for_both_encoders_in_one_file(self, library, capfd):
        # Run: the A/B setup -- the same library, two engines.
        main([
            '--encoder-name', 'chatterbox', '--add-voice', 'NarratorCB',
            '-f', 'voices.json', '--voice-ref-audio', 'clips/narrator.wav',
        ])
        main([
            '--encoder-name', 'qwen', '--add-voice', 'Narrator',
            '-f', 'voices.json', '--voice-ref-audio', 'clips/narrator.wav',
            '--voice-ref-text', 'Well, hello there.',
        ])

        # Verify
        voices = json.loads(
            (library / 'voices.json').read_text(encoding='utf-8')
        )['voices']
        assert voices['NarratorCB']['encoder'] == 'chatterbox'
        assert voices['Narrator']['encoder'] == 'qwen'
        assert voices['Narrator']['ref_text'] == 'Well, hello there.'

    def test_a_missing_clip_is_reported(self, library, capfd):
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder-name', 'chatterbox', '--add-voice', 'Narrator',
                '-f', 'voices.json',
                '--voice-ref-audio', 'clips/nope.wav',
            ])

        assert se.value.code == 1
        assert 'not found' in capfd.readouterr()[0]

    def test_requires_a_voice(self, library, capfd):
        with pytest.raises(SystemExit) as se:
            main([
                '--encoder-name', 'chatterbox', '--add-voice', 'Narrator',
                '-f', 'voices.json',
            ])

        assert se.value.code == 1
        assert 'requires a voice' in capfd.readouterr()[0]
