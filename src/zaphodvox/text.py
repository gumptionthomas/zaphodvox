import re
from typing import Dict, List, Optional, Tuple

from unidecode import unidecode

from zaphodvox.voice import Voice


def match_voice(
    text: str,
    voices: Optional[Dict[str, Optional[Voice]]] = None,
) -> Tuple[bool, Optional[Voice]]:
    """Matches the given text with a named voice and returns the corresponding
    `NamedVoice` object.

    Args:
        text: The text to match with a named Voice.
        voices: A dictionary of named voices.

    Returns:
        A tuple containing a boolean indicating whether a match was found and
            the matched `Voice` object, if any.
    """
    match = re.match(r'ZVOX:\s*([^\s]+)', text)
    if match:
        voice_name = match.group(1).strip()
        named_voice = (voices or {}).get(voice_name, None)
        return True, named_voice
    return False, None


def parse_text(
    text: str,
    voice: Optional[Voice] = None,
    voices: Optional[Dict[str, Optional[Voice]]] = None,
    max_chars: Optional[int] = None
) -> list[Tuple[str, Voice]]:
        """Parse the text into blocks with associated voice.

        Args:
            text: The text to be parsed.
            voice: The default `Voice` to be used for blocks without a
                specified 'inline' `Voice`.
            voices: A dictionary of named voices.
            max_chars: The maximum number of characters per block.

        Returns:
            A list of tuples containing the parsed text blocks
                and their associated `Voice` objects.

        Raises:
            ValueError: If a `Voice` is not specified for a block.
        """
        lines = [p for p in text.split('\n')]
        blocks: List[Tuple[str, Voice]] = []
        line_voice = voice
        for line in lines:
            matched, matched_voice = match_voice(line, voices)
            if matched:
                if matched_voice:
                    line_voice = matched_voice
                continue
            if line_voice:
                if max_chars and blocks:
                    prev_text, prev_voice = blocks[-1]
                    if (
                        len(prev_text) + 1 + len(line) <= max_chars and
                        line_voice == prev_voice
                    ):
                        blocks[-1] = (prev_text + '\n' + line, prev_voice)
                        continue
                blocks.append((line, line_voice))
            else:
                raise ValueError('No voice specified for text block.')
        return blocks


def end_of_paragraph(text: str) -> bool:
    """Check if given text ends with a punctuation mark indicating the end of
    a sentence.

    Args:
        text: The text to check.

    Returns:
        `True` if the text ends with a punctuation mark indicating
            the end of a sentence, `False` otherwise.
    """
    for ending in ['.', '?', '!']:
        if (
            text.endswith(ending) or
            text.endswith(ending+'\'') or
            text.endswith(ending+'"')
        ):
            return True
    return False


def split_text(text: str, max_chars: int) -> str:
    """Recurively splits the given text into lines of
    at most `max_chars` length.

    Args:
        text: The text to be split.
        max_chars: The maximum number of characters per line.

    Returns:
        The split text.
    """
    if len(text) <= max_chars:
        return text
    else:
        i = max(
            text.rfind('.', 0, max_chars),
            text.rfind('?', 0, max_chars),
            text.rfind('!', 0, max_chars)
        )
        if i == -1:
            i = text.rfind(' ', 0, max_chars)
        else:
            i = text.find(' ', i, max_chars)
        if i == -1:
            i = max_chars
        return text[:i] + '\n\n' + split_text(text[i:].lstrip(), max_chars)


def clean_text(text: str, max_chars: Optional[int] = None) -> str:
    """Cleans the given text by replacing '\\r' with '\\n', removing
    leading/trailing whitespaces, and adding appropriate line breaks between
    lines.

    Args:
        text: The text to be cleaned.
        max_chars: The maximum number of characters per line.

    Returns:
        The cleaned text.
    """
    lines = [p for p in text.replace('\r', '\n').split('\n')]
    lines.append('\n')
    cleaned_text = ''
    for i in range(0, len(lines) - 1):
        if line := lines[i]:
            line = unidecode(line.strip())
            if max_chars:
                line = split_text(line, max_chars)
            if not lines[i + 1]:
                new_line = line + '\n'
            elif end_of_paragraph(line):
                new_line = line + '\n\n'
            else:
                new_line = line + ' '
        else:
            new_line = '\n'
        cleaned_text += new_line
    return cleaned_text
