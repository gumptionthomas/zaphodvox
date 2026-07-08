from zaphodvox.dictionary import build_speller
from zaphodvox.proof import (
    check_repeated_chars,
    check_spelling,
    check_unusual_chars,
    check_whitespace,
    proof_text,
)


class TestProof():
    def test_spelling_groups_by_word(self):
        speller = build_speller('en')
        lines = ['The fox jumpd over teh dog.', 'teh cat.']
        findings = {f.text.lower(): f for f in check_spelling(lines, speller)}

        assert 'jumpd' in findings
        teh = findings['teh']
        assert teh.count == 2
        assert teh.lines == [1, 2]
        assert 'the' in teh.suggestions

    def test_spelling_accepts_custom_words(self):
        speller = build_speller('en', {'zaphod'})
        assert check_spelling(['Zaphod waved a hand.'], speller) == []

    def test_repeated_chars(self):
        findings = check_repeated_chars(['a scene break ****', 'fine --'])
        assert len(findings) == 1
        assert findings[0].text == '****'
        assert findings[0].line == 1

    def test_unusual_chars(self):
        findings = check_unusual_chars(
            ['normal line', 'a \ufffd here', 'nbsp\u00a0x', 'has\ttab']
        )
        texts = {f.text for f in findings}
        assert 'U+FFFD' in texts
        assert 'U+00A0' in texts
        # Tabs are left to the whitespace check, not flagged as unusual.
        assert 'U+0009' not in texts

    def test_whitespace(self):
        lines = ['trailing  ', 'ok', '', '', '', 'end', 'has\ttab']
        texts = [f.text for f in check_whitespace(lines)]
        assert 'trailing whitespace' in texts
        assert 'tab' in texts
        assert any('blank lines' in text for text in texts)

    def test_proof_text_summary(self):
        speller = build_speller('en')
        report = proof_text('teh dog ****\n', speller)
        assert report.summary.get('spelling') == 1
        assert report.summary.get('repeated-char') == 1
