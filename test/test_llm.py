import json
from unittest.mock import patch

from zaphodvox.llm import (
    LLMClient,
    _chunk_lines,
    _parse_findings,
    proofread,
)
from zaphodvox.text import end_of_sentence


def _completion(content: str) -> dict:
    return {'choices': [{'message': {'content': content}}]}


class TestLLM():
    def test_chunk_lines_breaks_on_sentence_end(self):
        lines = [f'Sentence number {i} is here.' for i in range(6)]
        chunks = _chunk_lines(lines, chunk_chars=50)
        # Every chunk ends on a sentence-ending line.
        assert all(end_of_sentence(cl[-1]) for _, cl in chunks)
        # Chunking is lossless.
        assert [line for _, cl in chunks for line in cl] == lines
        # Line numbers are contiguous.
        assert [start for start, _ in chunks] == [1, 3, 5]

    def test_chunk_lines_never_splits_mid_sentence(self):
        # Hard-wrapped: each sentence spans two physical lines; only the second
        # line of each ends the sentence.
        lines = [
            'The towel is the most', 'massively useful thing.',
            'A hitchhiker needs one', 'above all other things.',
        ]
        chunks = _chunk_lines(lines, chunk_chars=20)
        for _, chunk_lines in chunks:
            last = chunk_lines[-1].strip()
            assert not last or end_of_sentence(last)

    def test_chunk_lines_groups_small(self):
        chunks = _chunk_lines(['short.', 'lines.', 'here.'], chunk_chars=1000)
        assert len(chunks) == 1
        assert chunks[0] == (1, ['short.', 'lines.', 'here.'])

    def test_parse_findings(self):
        content = json.dumps({'findings': [
            {'line': 3, 'category': 'homophone', 'excerpt': 'Their were',
             'message': 'wrong', 'suggestion': 'There were'},
            {'line': 5, 'category': 'header', 'excerpt': 'chapter 2',
             'message': 'inconsistent'},
        ]})
        findings = _parse_findings(content)
        assert len(findings) == 2
        assert findings[0].line == 3
        assert findings[0].source == 'llm'
        assert findings[0].type == 'proofread'
        assert findings[0].suggestions == ['There were']
        assert findings[1].suggestions == []

    def test_parse_findings_malformed(self):
        assert _parse_findings('not json') == []
        assert _parse_findings(json.dumps({'findings': [{'line': 1}]})) == []

    def test_client_complete_json(self):
        with patch('zaphodvox.llm.requests') as mock_requests:
            response = mock_requests.post.return_value.__enter__.return_value
            response.json.return_value = _completion('{"findings": []}')

            client = LLMClient('http://host:1234/', model='qwen')
            out = client.complete_json('sys', 'usr', {'name': 's', 'schema': {}})

            assert out == '{"findings": []}'
            args, kwargs = mock_requests.post.call_args
            assert args[0] == 'http://host:1234/v1/chat/completions'
            body = kwargs['json']
            assert body['model'] == 'qwen'
            assert body['response_format']['type'] == 'json_schema'
            assert body['messages'][0]['role'] == 'system'

    def test_proofread(self):
        with patch('zaphodvox.llm.requests') as mock_requests:
            response = mock_requests.post.return_value.__enter__.return_value
            response.json.return_value = _completion(json.dumps({'findings': [
                {'line': 1, 'category': 'homophone', 'excerpt': 'x',
                 'message': 'y', 'suggestion': 'z'}]}))

            findings = proofread('one line', LLMClient('http://host:1234'))

            assert len(findings) == 1
            assert findings[0].line == 1
            assert findings[0].source == 'llm'
