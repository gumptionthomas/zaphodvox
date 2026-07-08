from pathlib import Path
from typing import Optional

from spellchecker import SpellChecker


def _read_words(path: Optional[Path]) -> list[str]:
    """Reads the words from a wordlist file (one word per line, `#` comments).

    Args:
        path: The `Path` to the wordlist file.

    Returns:
        The list of words (original case, in file order), empty if the file
            is absent.
    """
    words: list[str] = []
    if not path:
        return words
    try:
        with open(str(path), 'r') as file:
            for line in file:
                word = line.split('#', 1)[0].strip()
                if word:
                    words.append(word)
    except FileNotFoundError:
        pass
    return words


def load_words(path: Optional[Path]) -> set[str]:
    """Loads a custom wordlist as a set of lowercased words for matching.

    Args:
        path: The `Path` to the wordlist file.

    Returns:
        The set of lowercased words (empty if the file is absent).
    """
    return {word.lower() for word in _read_words(path)}


def add_words(path: Path, new_words: list[str]) -> list[str]:
    """Adds words to a wordlist file, de-duplicated (case-insensitively) and
        sorted. Creates the file if it does not exist.

    Args:
        path: The `Path` to the wordlist file.
        new_words: The words to add.

    Returns:
        The words that were actually added (not already present).
    """
    words = _read_words(path)
    seen = {word.lower() for word in words}
    added: list[str] = []
    for word in new_words:
        if word.lower() not in seen:
            words.append(word)
            seen.add(word.lower())
            added.append(word)
    words = sorted(set(words), key=str.lower)
    with open(str(path), 'w') as file:
        file.write('\n'.join(words) + '\n')
    return added


def build_speller(
    language: str = 'en', custom_words: Optional[set[str]] = None
) -> SpellChecker:
    """Builds a `SpellChecker` for the given language, seeded with custom words.

    Args:
        language: The dictionary language (e.g. `en`).
        custom_words: Extra known words to accept (e.g. a project wordlist).

    Returns:
        The configured `SpellChecker`.
    """
    speller = SpellChecker(language=language)
    if custom_words:
        speller.word_frequency.load_words(custom_words)
    return speller
