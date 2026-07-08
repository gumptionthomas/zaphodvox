import json
from unittest.mock import patch

from zaphodvox.llm import (
    LLMClient,
    _chunk_lines,
    _parse_findings,
    proofread,
)


def _completion(content: str) -> dict:
    return {'choices': [{'message': {'content': content}}]}


class TestLLM():
    def test_chunk_lines_splits_by_size(self):
        lines = ['a' * 50, 'b' * 50, 'c' * 50]
        chunks = _chunk_lines(lines, chunk_chars=60)
        assert [start for start, _ in chunks] == [1, 2, 3]

    def test_chunk_lines_groups_small(self):
        chunks = _chunk_lines(['short', 'lines', 'here'], chunk_chars=1000)
        assert len(chunks) == 1
        assert chunks[0] == (1, ['short', 'lines', 'here'])

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
