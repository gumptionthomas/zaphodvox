from pathlib import Path

from zaphodvox.dictionary import add_words, build_speller, load_words


class TestDictionary():
    def test_load_words_missing(self):
        assert load_words(Path('does-not-exist.dict')) == set()
        assert load_words(None) == set()

    def test_load_ignores_comments_and_blanks(self, tmp_path):
        path = tmp_path / 'c.dict'
        path.write_text('Zaphod  # a name\n\n# a comment\nFord\n')
        assert load_words(path) == {'zaphod', 'ford'}

    def test_add_words_creates_dedups_sorts(self, tmp_path):
        path = tmp_path / 'book.dict'
        assert add_words(path, ['Zaphod', 'Trillian']) == ['Zaphod', 'Trillian']
        # "zaphod" already present (case-insensitively); only "Ford" is new.
        assert add_words(path, ['zaphod', 'Ford']) == ['Ford']
        assert path.read_text().splitlines() == ['Ford', 'Trillian', 'Zaphod']
        assert load_words(path) == {'ford', 'trillian', 'zaphod'}

    def test_build_speller_accepts_custom_words(self):
        speller = build_speller('en', {'zaphod'})
        assert not speller.unknown(['zaphod'])
        assert speller.unknown(['beeblebrox'])
