from pathlib import Path

import pytest

from zaphodvox.paths import rebase_ref, resolve_ref


@pytest.fixture
def fake_home(tmp_path, monkeypatch) -> Path:
    """Points the home directory at a temp directory.

    Set through the environment rather than by patching `Path.home`, because
    `Path.expanduser` reads the environment directly; patching the method would
    leave the two disagreeing. `USERPROFILE` is what Windows consults.
    """
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    return home


class TestResolveRef():
    def test_relative_resolves_against_base_dir(self):
        resolved = resolve_ref('narrator.wav', Path('voices'))

        assert resolved == Path('voices/narrator.wav')

    def test_relative_without_base_dir_stays_relative_to_cwd(self):
        resolved = resolve_ref('narrator.wav', None)

        assert resolved == Path('narrator.wav')

    def test_absolute_ignores_base_dir(self, tmp_path):
        absolute = tmp_path / 'clips' / 'narrator.wav'

        resolved = resolve_ref(absolute.as_posix(), Path('voices'))

        assert resolved == absolute

    def test_home_anchored_ignores_base_dir(self, fake_home):
        resolved = resolve_ref('~/voices/narrator.wav', Path('voices'))

        assert resolved == fake_home / 'voices' / 'narrator.wav'


class TestRebaseRef():
    def test_target_inside_tree_stays_relative(self, tmp_path):
        # A clip beside the file being written keeps a bare filename, which is
        # what keeps a voice library self-contained and movable.
        rebased = rebase_ref('narrator.wav', tmp_path, tmp_path)

        assert rebased == 'narrator.wav'

    def test_target_in_subdirectory_stays_relative(self, tmp_path):
        rebased = rebase_ref('clips/narrator.wav', tmp_path, tmp_path)

        assert rebased == 'clips/narrator.wav'

    def test_target_outside_tree_is_home_anchored(self, fake_home):
        # The library is outside the project, so a relative path would break the
        # moment the two moved independently. Anchor it to the home directory.
        library = fake_home / 'voices'
        project = fake_home / 'books' / 'hitchhiker'

        rebased = rebase_ref('narrator.wav', library, project)

        assert rebased == '~/voices/narrator.wav'

    def test_target_outside_home_is_absolute(self, tmp_path, fake_home):
        library = tmp_path / 'elsewhere' / 'voices'
        project = tmp_path / 'books'

        rebased = rebase_ref('narrator.wav', library, project)

        assert rebased == (library / 'narrator.wav').as_posix()

    def test_rebase_is_idempotent(self, fake_home):
        # Rewriting a path that is already correct must not change it: `adopt`
        # rewrites every voice in the file each time it touches one.
        library = fake_home / 'voices'

        once = rebase_ref('narrator.wav', library, library)
        twice = rebase_ref(once, library, library)

        assert once == twice == 'narrator.wav'
