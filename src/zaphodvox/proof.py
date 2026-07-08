import re
import unicodedata
from typing import Optional

from pydantic import BaseModel
from spellchecker import SpellChecker

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")
"""Matches word tokens (letters, with internal apostrophes)."""

REPEAT_RE = re.compile(r'([*_#~=+\-])\1{2,}')
"""Matches runs of 3+ of the same markup/punctuation character."""

ZERO_WIDTH = {'\u200b', '\u200c', '\u200d', '\ufeff', '\u00a0'}
"""Zero-width and non-breaking characters that are usually unwanted."""

MAX_REPORTED_LINES = 20
"""The maximum number of line numbers to list for a grouped finding."""


class ProofFinding(BaseModel):
    """A single issue found while proofing a manuscript."""

    line: int
    """The (1-based) line number of the issue (its first occurrence)."""
    type: str
    """The kind of issue (e.g. `spelling`, `repeated-char`)."""
    source: str
    """What found it (e.g. `dictionary`, `regex`)."""
    severity: str
    """`info` or `warning`."""
    text: str
    """The offending snippet (e.g. the unknown word or the character run)."""
    message: str
    """A human-readable description of the issue."""
    suggestions: list[str] = []
    """Suggested corrections, if any."""
    count: Optional[int] = None
    """The number of occurrences, for grouped findings."""
    lines: Optional[list[int]] = None
    """The line numbers of occurrences, for grouped findings."""


class ProofReport(BaseModel):
    """The result of proofing a manuscript."""

    source_file: Optional[str] = None
    """The proofed input file."""
    summary: dict[str, int] = {}
    """A count of findings by type."""
    findings: list[ProofFinding] = []
    """The individual findings."""


def check_spelling(
    lines: list[str], speller: SpellChecker
) -> list[ProofFinding]:
    """Flags words absent from the dictionary, grouped by unique word.

    Args:
        lines: The text lines.
        speller: The `SpellChecker` (seeded with any custom words).

    Returns:
        One finding per unique unknown word.
    """
    occurrences: dict[str, dict] = {}
    for number, line in enumerate(lines, start=1):
        for match in WORD_RE.finditer(line):
            token = match.group(0)
            base = token[:-2] if token.lower().endswith("'s") else token
            base = base.strip("'")
            key = base.lower()
            if len(key) < 2:
                continue
            entry = occurrences.setdefault(key, {'text': base, 'lines': []})
            entry['lines'].append(number)
    findings: list[ProofFinding] = []
    for key in sorted(speller.unknown(list(occurrences.keys()))):
        entry = occurrences[key]
        candidates = (speller.candidates(key) or set()) - {key}
        suggestions = sorted(
            candidates, key=lambda word: speller.word_frequency[word],
            reverse=True
        )[:5]
        findings.append(ProofFinding(
            line=entry['lines'][0], type='spelling', source='dictionary',
            severity='warning', text=entry['text'], message='Unknown word',
            suggestions=suggestions, count=len(entry['lines']),
            lines=entry['lines'][:MAX_REPORTED_LINES],
        ))
    return findings


def check_repeated_chars(lines: list[str]) -> list[ProofFinding]:
    """Flags runs of 3+ repeated markup/punctuation characters.

    Args:
        lines: The text lines.

    Returns:
        One finding per run.
    """
    findings: list[ProofFinding] = []
    for number, line in enumerate(lines, start=1):
        for match in REPEAT_RE.finditer(line):
            run = match.group(0)
            findings.append(ProofFinding(
                line=number, type='repeated-char', source='regex',
                severity='info', text=run,
                message=(
                    f"Run of {len(run)} '{match.group(1)}' "
                    '(stray markup or artifact?)'
                ),
            ))
    return findings


def _is_unusual(char: str) -> bool:
    """Whether a character is a control, format, or otherwise unexpected one
        (excluding tabs, which the whitespace check handles).

    Args:
        char: The character to test.

    Returns:
        `True` if the character is unusual.
    """
    if char == '\t':
        return False
    if char in ZERO_WIDTH or char == '\ufffd':
        return True
    return unicodedata.category(char) in ('Cc', 'Cf', 'Co', 'Cn')


def check_unusual_chars(lines: list[str]) -> list[ProofFinding]:
    """Flags control/format/unexpected characters, grouped by character.

    Args:
        lines: The text lines.

    Returns:
        One finding per unusual character.
    """
    occurrences: dict[str, list[int]] = {}
    for number, line in enumerate(lines, start=1):
        for char in line:
            if _is_unusual(char):
                occurrences.setdefault(char, []).append(number)
    findings: list[ProofFinding] = []
    for char, numbers in occurrences.items():
        name = unicodedata.name(char, 'UNKNOWN')
        findings.append(ProofFinding(
            line=numbers[0], type='unusual-char', source='regex',
            severity='warning', text=f'U+{ord(char):04X}',
            message=f'Unusual character: {name}', count=len(numbers),
            lines=numbers[:MAX_REPORTED_LINES],
        ))
    return findings


def check_whitespace(lines: list[str]) -> list[ProofFinding]:
    """Flags trailing whitespace, tabs, and runs of 3+ blank lines.

    Args:
        lines: The text lines.

    Returns:
        Grouped whitespace findings.
    """
    findings: list[ProofFinding] = []
    trailing = [
        number for number, line in enumerate(lines, start=1)
        if line.strip() and line != line.rstrip()
    ]
    if trailing:
        findings.append(ProofFinding(
            line=trailing[0], type='whitespace', source='regex',
            severity='info', text='trailing whitespace',
            message='Lines with trailing whitespace', count=len(trailing),
            lines=trailing[:MAX_REPORTED_LINES],
        ))
    tabs = [
        number for number, line in enumerate(lines, start=1) if '\t' in line
    ]
    if tabs:
        findings.append(ProofFinding(
            line=tabs[0], type='whitespace', source='regex', severity='info',
            text='tab', message='Lines containing tab characters',
            count=len(tabs), lines=tabs[:MAX_REPORTED_LINES],
        ))
    run = 0
    start = 0
    for number, line in enumerate(lines, start=1):
        if line.strip():
            if run > 2:
                findings.append(ProofFinding(
                    line=start, type='whitespace', source='regex',
                    severity='info', text=f'{run} blank lines',
                    message=f'{run} consecutive blank lines',
                ))
            run = 0
        else:
            start = number if run == 0 else start
            run += 1
    return findings


def proof_text(text: str, speller: SpellChecker) -> ProofReport:
    """Runs all deterministic checks over the text.

    Args:
        text: The manuscript text.
        speller: The `SpellChecker` (seeded with any custom words).

    Returns:
        The `ProofReport`.
    """
    lines = text.split('\n')
    findings = (
        check_spelling(lines, speller)
        + check_repeated_chars(lines)
        + check_unusual_chars(lines)
        + check_whitespace(lines)
    )
    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.type] = summary.get(finding.type, 0) + 1
    return ProofReport(summary=summary, findings=findings)
