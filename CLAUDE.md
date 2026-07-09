# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`zaphodvox` is a CLI and Python library that encodes a text file (or a JSON manifest) into synthetic speech audio using a **locally-hosted Qwen3-TTS server** (e.g. [cornball-ai/qwen3-tts-api](https://github.com/cornball-ai/qwen3-tts-api), which wraps the open-weight [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) models). Requires Python >=3.10 and a working `ffmpeg` install (used via `pydub`).

Historically this project wrapped Google Cloud TTS, ElevenLabs, and AllTalk. As of 2.0.0 those backends were removed in favor of the single local Qwen backend; the pre-2.0 multi-backend code is preserved on the `v1.3.0-multi-backend` tag.

## Commands

Development uses [Hatch](https://hatch.pypa.io/) (see `pyproject.toml`); a flat `requirements.txt` is also provided. A local `.venv` (created with `uv venv`) also works — invoke it as `.venv/bin/python -m pytest`.

```bash
# Run the full test suite with coverage (config in pyproject.toml [tool.pytest])
hatch run test:test          # or simply: pytest   (or: .venv/bin/python -m pytest)

# Run a single test file / test / keyword
pytest test/test_text.py
pytest test/test_main.py::TestMain::test_main
pytest -k parse_indexes

# Lint / type-check (config in pyproject.toml)
ruff check src test          # line-length 80, target py311
mypy src

# Run the CLI locally (talks to a Qwen3-TTS server at --qwen-url)
python -m zaphodvox.main --help    # or, if installed: zaphodvox --help
```

`pytest` auto-adds `src` to `pythonpath` and writes coverage to `lcov.info` + terminal. Tests mock all network/API and filesystem calls (see `test/conftest.py`) — no real server, credentials, or `ffmpeg` are needed to run them.

## Pipeline (the big picture)

`main.main()` (`src/zaphodvox/main.py`) orchestrates everything as an ordered set of optional stages driven by CLI flags. Reading `main()` top-to-bottom is the fastest way to understand control flow:

1. **read** — `read_text_manifest()` loads the input file and tries to parse it as a `Manifest` JSON; if that fails it's treated as plain text. So the *same* input arg is either a text file or a manifest.
2. **`--clean`** — `text.clean_text()` normalizes text (unidecode, paragraph breaks, optional `--max-chars` sentence-boundary splitting). Writes `<basename>-clean.txt`.
3. **`--plan` / `--encode`** — `plan()` builds a `Manifest` via `text.parse_text()` (one `Fragment` per line by default; lines combined up to `--max-chars`). `--plan` writes `<basename>-plan.json` without encoding.
4. **`--encode`** — `Encoder.encode_manifest()` synthesizes each fragment to an audio file and updates the manifest in place. Optionally writes `<basename>-manifest.json`.
5. **`--concat`** — `audio.concat_files()` stitches fragment audio into `<basename>.<ext>` via `pydub`.

There's also a standalone **`--audition N`** mode (`main.audition()`): given a preset `--voice-id` and a sample sentence, it synthesizes `N` candidate reference clips across seeds `0..N-1` (candidate `k` uses seed `k`) so the best take can be adopted as a clone anchor. It reuses `encode_manifest()` by building a synthetic `Manifest` of `N` same-text fragments with per-seed `QwenVoice`s, writes a `*-audition.json` index, and prints a table. The companion **`--adopt SEED`** mode (`main.adopt()`) reads that index (the inputfile), builds a clone `QwenVoice` from the chosen candidate (carrying its `ref_text`/`seed`/`temperature`), and adds/updates it under `--voice-name` in `--voices-file`. Both are mutually exclusive with the other action flags.

A separate **`--proof`** mode (`main.proof()`) runs read-only checks over the manuscript and writes a `*-proof.json` report (of `ProofReport`/`ProofFinding`, in `proof.py`) plus a table; it never edits the text. Deterministic checks (`proof.py` + `dictionary.py`/`pyspellchecker` + a project wordlist): spelling, repeated/unusual characters, whitespace. When `--llm-url` (or `ZAPHODVOX_LLM_URL`) is set, `llm.py` adds a **local** LLM pass (`LLMClient` → OpenAI-compatible `/v1/chat/completions`, chunked, low temp, JSON-schema output) for contextual/structural issues (homophones, garbled sentences, chapter-header consistency), merged into the report as `source: "llm"`. Per project rule the LLM is **local only, never cloud** (see the memory constraint). The companion **`--add-word`** mode appends accepted spellings to the `--dict` wordlist.

If no action flag is given, the program prints a quip and exits 0 (`handle_version_and_ntd`). All exceptions bubble to `main()`'s top-level handler, which prints a red error and exits 1.

## Key architectural concepts

**Encoder registration is subclass-based.** `main.encoder_voice()` finds the encoder by iterating `Encoder.__subclasses__()` and matching `encoder_class.name`. This means **an encoder module must be imported somewhere before it can be discovered**. `arg_parser.py` imports `QwenEncoder` explicitly to register it and to populate the `--encoder-name` choices. There is currently only one backend, but the ABC seam is kept deliberately — it's the project's proven extension point (four backends have lived here over its life). If you add another encoder, import it there too.

**Encoder is an ABC** (`src/zaphodvox/encoder.py`). Subclasses implement `audio_format`, `file_extension`, `from_args()`, and `t2s()`. The base `encode_manifest()` handles iteration, the progress bar, per-fragment silence, voice resolution, and converting runs of `\n\n+` into pauses via `break_tag`. **Qwen takes plain text, not SSML** — so `break_tag`'s default renders paragraph breaks as plain sentence stops (`' . '`, not SSML `<break>` tags), and `QwenEncoder.t2s()` sends the fragment text as-is (no `<speak>` wrapping). A future SSML-based encoder would override `break_tag`. The whole `qwen` backend lives in `src/zaphodvox/qwen/` (`encoder.py`, `voice.py`).

**QwenEncoder is a thin HTTP client** (`qwen/encoder.py`). `t2s()` dispatches on the voice: a preset speaker POSTs JSON to `{url}/v1/audio/speech`; a clone POSTs multipart (the reference audio file) to `{url}/v1/audio/speech/upload`; a design POSTs JSON to `{url}/v1/audio/speech/design`. All write the raw response bytes to the fragment file and are wrapped in a `tenacity` retry. Server base URL comes from `--qwen-url` (default `http://127.0.0.1:4123`, env `ZAPHODVOX_QWEN_URL`).

**Voice model.** `Voice` (`voice.py`) is an empty Pydantic base; `QwenVoice` (`qwen/voice.py`) subclasses it. A voice is one of: a **preset** (`voice_id`, e.g. `"Ryan"`, with optional `instruct` emotion/style), a **clone** (`ref_audio` path, optional `ref_text` transcript for ICL vs. zero-shot), or a **design** (`description`, a natural-language voice). A `model_validator` enforces exactly one of `voice_id`/`ref_audio`/`description`; `is_clone`/`is_design` distinguish them. Designs are the least consistent for long content — the intended pattern is design → `--audition` → `--adopt` as a clone. An optional `seed` pins the server's RNG so a voice stays consistent across chunks and re-encodes; an optional `temperature` tunes run-to-run variability (lower is steadier), not expressiveness. Both are sent per request and serialized with the voice into the manifest. Both require the `eddie` server (a fork of `cornball-ai/qwen3-tts-api`); upstream implements neither. `--voice-id` and `--voice-ref-audio` are the mutually-exclusive CLI entry points.

**Named voices are flat.** `NamedVoices` (`named_voices.py`) is just `{name: QwenVoice}` — a `--voices-file` and inline `ZVOX: <name>` tags in the text select a named voice directly. (Pre-2.0 this nested per-engine configs under `google`/`elevenlabs`/`alltalk` keys; that grouping is gone now that there's one backend.)

**Manifest is the serializable source of truth** (`manifest.py`, Pydantic models `Manifest` + `Fragment`). It round-trips to JSON, can be hand-edited, and fed back in as input. `--manifest-indexes` (parsed by `main.parse_indexes()`, supports `1`, `1-3`, `2-`, `-4`, comma lists) re-encodes only selected fragments in place. Fragment `voice` fields serialize polymorphically via `SerializeAsAny`; the manifest's top-level `voices` dict is `{name: QwenVoice}` so a manifest is self-contained.

**Inline voice switching.** `text.match_voice()` recognizes `ZVOX: <name>` lines; that line is not synthesized and sets the "current" voice for following fragments. Empty lines become silent fragments (`silence_duration`, rendered by `audio.create_silence`).

**Output-path resolution.** `main.file_path()` centralizes where files land: an explicit `--*-out` file path wins, else `--out-dir` + generated filename, else CWD. Generated names derive from `--basename` (defaults to the input file's stem).

## Conventions

- Pydantic v2 throughout for models and JSON (de)serialization; prefer model methods over ad-hoc dict handling.
- `QwenEncoder.t2s()` wraps the HTTP call in `tenacity` `Retrying(stop_after_attempt(5))`.
- Docstrings are Google-style and thorough; match the existing density when adding code.
- `__version__` lives in `src/zaphodvox/__init__.py` and is the Hatch version source.
