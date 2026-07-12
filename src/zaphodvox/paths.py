import os
import re
from pathlib import Path
from typing import Optional


def abspath(path: Path) -> Path:
    """Makes a path absolute and collapses any `.`/`..` segments.

    `Path.absolute()` alone keeps the segments verbatim, so a path anchored to
    `../lib` stays spelled that way -- fine to open, but noise in a message and
    not comparable with `relative_to()`.

    Args:
        path: The `Path` to normalize.

    Returns:
        The absolute, normalized `Path`.
    """
    return Path(os.path.normpath(path.absolute()))


def expanded_path(value: str) -> Path:
    """Converts a command-line argument to a `Path`, expanding a leading `~`.

    The shell only expands a tilde in some of the spellings people actually use:
    `--out-dir ~/voices` is expanded before the program ever sees it, but
    `--out-dir=~/voices` is not, and neither is a quoted environment variable
    (`ZAPHODVOX_VOICES_FILE="~/voices/voices.json"`). Left alone, those arrive as
    a literal `~`, and the program would go looking for -- or worse, create -- a
    directory actually named `~`.

    Args:
        value: The path as given on the command line or in an environment
            variable.

    Returns:
        The `Path`, with a leading `~` expanded to the home directory.
    """
    return Path(value).expanduser()


def clip_filename(voice_name: str, suffix: str) -> str:
    """Builds the filename a voice's reference clip is stored under.

    An adopted clip keeps the name of the audition candidate it came from
    (`narrator-audition-05.wav`) unless it is renamed, which would make a voice
    used for years carry the name of a throwaway artifact. Naming it for the
    voice keeps a voices library readable.

    Args:
        voice_name: The name of the voice, which may contain anything a person
            might type.
        suffix: The file extension to use, including the dot (e.g. `.wav`).

    Returns:
        The filename for the voice's reference clip.
    """
    slug = re.sub(r'[^A-Za-z0-9._-]+', '-', voice_name).strip('-.')
    return f'{slug or "voice"}{suffix}'


def resolve_ref(raw: str, base_dir: Optional[Path] = None) -> Path:
    """Resolves a stored reference path against the directory of the file that
    declared it.

    An absolute path is used as-is and a leading `~` is expanded against the
    home directory, so either survives being copied between files. A relative
    path is resolved against `base_dir` (the directory of the voices file or
    manifest it was read from); with no `base_dir` it stays relative to the
    current working directory, which is what a path typed on the command line
    should do.

    Args:
        raw: The reference path as stored (or as typed).
        base_dir: The directory `Path` of the file that declared `raw`.
            Defaults to `None` (the current working directory).

    Returns:
        The resolved `Path`.
    """
    path = Path(raw).expanduser()
    if path.is_absolute() or not base_dir:
        return path
    return base_dir / path


def rebase_ref(
    raw: str, base_dir: Optional[Path], target_dir: Path
) -> str:
    """Rewrites a reference path so that it stays valid from a different file.

    Voices travel between files: a voice read from a voices file is copied into
    the manifest of whatever project encoded it. Its path must therefore be
    rewritten to be meaningful from the file it is being written into, or it
    would silently resolve against the wrong directory.

    A target inside `target_dir` is written relative to it, which keeps a voice
    library self-contained and movable. Anything outside is written home-
    anchored (`~/...`) when possible, else absolute: a relative path out of the
    tree (`../../voices/x.wav`) would break as soon as the two directories moved
    independently of each other, and cannot be expressed at all across Windows
    drives.

    Args:
        raw: The reference path as stored.
        base_dir: The directory `Path` of the file that declared `raw`.
        target_dir: The directory `Path` of the file being written.

    Returns:
        The rewritten reference path, in POSIX form.
    """
    resolved = abspath(resolve_ref(raw, base_dir))
    target = abspath(target_dir)
    try:
        return resolved.relative_to(target).as_posix()
    except ValueError:
        pass
    try:
        return (Path('~') / resolved.relative_to(Path.home())).as_posix()
    except ValueError:
        return resolved.as_posix()
