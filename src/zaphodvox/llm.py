import json
from typing import Optional

import requests
from tenacity import Retrying, stop_after_attempt

from zaphodvox.progress import ProgressBar
from zaphodvox.proof import ProofFinding

DEFAULT_LLM_URL = 'http://127.0.0.1:1234'
"""The default base URL of a local OpenAI-compatible LLM server (LM Studio)."""

CHUNK_CHARS = 2000
"""The approximate size (in characters) of each proofreading chunk."""

PROOF_SYSTEM = (
    'You are a meticulous proofreader for an audiobook manuscript. Each input '
    "line is prefixed with its line number as 'N: '. Report ONLY genuine "
    'errors: misspellings in context, homophones (their/there), doubled '
    'words, garbled or OCR-broken sentences, obvious punctuation errors, and '
    'inconsistent or malformed chapter headers. Do NOT rewrite for style, '
    'tone, or dialect. Do NOT flag proper names, invented words, or '
    'intentional stylization. Do NOT report anything you are unsure about. '
    'Respond ONLY with JSON of the form '
    '{"findings": [{"line": <number>, "category": <short string>, '
    '"excerpt": <the problem text>, "message": <why it is wrong>, '
    '"suggestion": <a fix, or empty string>}]}. Use the printed line numbers. '
    'If there are no issues, return {"findings": []}.'
)
"""The system prompt for the proofreading request."""

PROOF_SCHEMA = {
    'name': 'proof_findings',
    'schema': {
        'type': 'object',
        'properties': {
            'findings': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'line': {'type': 'integer'},
                        'category': {'type': 'string'},
                        'excerpt': {'type': 'string'},
                        'message': {'type': 'string'},
                        'suggestion': {'type': 'string'},
                    },
                    'required': ['line', 'category', 'excerpt', 'message'],
                },
            },
        },
        'required': ['findings'],
    },
}
"""The JSON schema requested of the LLM (structured output)."""


class LLMClient:
    """A thin client for a local OpenAI-compatible chat-completions server."""

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> None:
        """Initializes the `LLMClient`.

        Args:
            url: The base URL of the local LLM server. Defaults to
                `DEFAULT_LLM_URL`.
            model: The model id (optional; the server may use its loaded
                model).
            temperature: The sampling temperature (low for consistency).
        """
        self._url = (url or DEFAULT_LLM_URL).rstrip('/')
        """The base URL of the local LLM server."""
        self._model = model
        """The model id."""
        self._temperature = temperature
        """The sampling temperature."""

    def complete_json(self, system: str, user: str, schema: dict) -> str:
        """Requests a JSON completion from the chat endpoint.

        Args:
            system: The system prompt.
            user: The user message.
            schema: The JSON schema for structured output.

        Returns:
            The message content (a JSON string).
        """
        payload: dict = {
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user},
            ],
            'temperature': self._temperature,
            'response_format': {'type': 'json_schema', 'json_schema': schema},
        }
        if self._model:
            payload['model'] = self._model
        for attempt in Retrying(reraise=True, stop=stop_after_attempt(3)):
            with attempt:
                with requests.post(
                    f'{self._url}/v1/chat/completions', json=payload
                ) as response:
                    response.raise_for_status()
                    data = response.json()
                    return data['choices'][0]['message']['content']
        raise RuntimeError('unreachable')


def _chunk_lines(
    lines: list[str], chunk_chars: int = CHUNK_CHARS
) -> list[tuple[int, list[str]]]:
    """Groups lines into chunks of roughly `chunk_chars`, tracking the
        (1-based) starting line number of each chunk.

    Args:
        lines: The text lines.
        chunk_chars: The approximate chunk size in characters.

    Returns:
        A list of `(start_line, chunk_lines)` tuples.
    """
    chunks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start = 1
    size = 0
    for number, line in enumerate(lines, start=1):
        if current and size + len(line) > chunk_chars:
            chunks.append((start, current))
            current = []
            start = number
            size = 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append((start, current))
    return chunks


def _parse_findings(content: str) -> list[ProofFinding]:
    """Parses the LLM's JSON response into `ProofFinding`s, defensively.

    Args:
        content: The JSON string returned by the LLM.

    Returns:
        The parsed findings (empty if the response is malformed).
    """
    findings: list[ProofFinding] = []
    try:
        items = json.loads(content).get('findings', [])
    except (ValueError, AttributeError):
        return findings
    for item in items:
        try:
            suggestion = item.get('suggestion') or ''
            findings.append(ProofFinding(
                line=int(item['line']),
                type='proofread',
                source='llm',
                severity='warning',
                text=item.get('excerpt', ''),
                message=f"{item.get('category', 'issue')}: {item['message']}",
                suggestions=[suggestion] if suggestion else [],
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return findings


def proofread(text: str, client: LLMClient) -> list[ProofFinding]:
    """Proofreads the text with the local LLM, chunk by chunk.

    Args:
        text: The manuscript text.
        client: The `LLMClient`.

    Returns:
        The LLM's findings (mapped to absolute line numbers).
    """
    chunks = _chunk_lines(text.split('\n'))
    findings: list[ProofFinding] = []
    with ProgressBar('Proofreading', total=len(chunks)) as bar:
        for start, chunk_lines in chunks:
            numbered = '\n'.join(
                f'{start + offset}: {line}'
                for offset, line in enumerate(chunk_lines)
            )
            content = client.complete_json(PROOF_SYSTEM, numbered, PROOF_SCHEMA)
            findings.extend(_parse_findings(content))
            bar.next()
    return findings
