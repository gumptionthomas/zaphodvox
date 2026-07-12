# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`zaphodvox` is a CLI and Python library that encodes a text file (or a JSON manifest) into synthetic speech audio using a **locally-hosted TTS server**. Two backends, selected with `--encoder-name`:

- **`qwen`** (the default) — the [`eddie-tts`](https://github.com/gumptionthomas/eddie-tts) fork of [cornball-ai/qwen3-tts-api](https://github.com/cornball-ai/qwen3-tts-api), serving the open-weight [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) models. Presets, clones (zero-shot or ICL), and natural-language voice *design*.
- **`chatterbox`** (added 2.3.0) — presets and clones only, steered numerically rather than by `instruct`/`description`. Useful for auditioning voices; **not the one to narrate a book with** — see the artifact caveat under its encoder below.

Requires Python >=3.10. `ffmpeg` is needed only to concatenate to `mp3` (wav concat is pure stdlib).

Historically this project wrapped Google Cloud TTS, ElevenLabs, and AllTalk. 2.0.0 removed all three in favor of a single local Qwen backend (the pre-2.0 code is preserved on the `v1.3.0-multi-backend` tag); 2.3.0 made the backend layer plural again, this time over local servers.

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

# Run the CLI locally (talks to a local server at --qwen-url / --chatterbox-url)
python -m zaphodvox.main --help    # or, if installed: zaphodvox --help
```

`pytest` auto-adds `src` to `pythonpath` and writes coverage to `lcov.info` + terminal. Tests mock all network/API and filesystem calls (see `test/conftest.py`) — no real server, credentials, or `ffmpeg` are needed to run them.

**Caveat: the suite patches `builtins.open` globally.** That keeps tests hermetic but means most of them never touch a real file — which is exactly how a fleet of missing `encoding='utf-8'` arguments survived until someone ran the CLI on Windows (cp1252 → `UnicodeDecodeError` on any curly quote). If you touch file I/O, add a test that does *real* I/O in a `tmp_path` with the `open` mock disabled; `TestTextEncoding` (`test/test_main.py`) and the whole of `test/test_voice_library.py` are the pattern. Always pass `encoding='utf-8'` on text-mode `open()` (plus `newline='\n'` on writes), and never build a path for serialization by hand — go through `paths.py` (`rebase_ref()` to write one, `resolve_ref()` to read one back, `abspath()` to compare or print one). A path spelled with `str(Path(...))` picks up backslashes on Windows and stops resolving anywhere else.

`.github/workflows/ci.yml` runs the suite on ubuntu/windows/macos × Python 3.10 and 3.12 (3.13 is blocked by `pydub` importing `audioop`, removed in that version), plus a ruff + mypy lint job, on every push to `main` and every PR.

## Pipeline (the big picture)

`main.main()` (`src/zaphodvox/main.py`) orchestrates everything as an ordered set of optional stages driven by CLI flags. Reading `main()` top-to-bottom is the fastest way to understand control flow:

1. **read** — `read_text_manifest()` loads the input file and tries to parse it as a `Manifest` JSON; if that fails it's treated as plain text. So the *same* input arg is either a text file or a manifest.
2. **`--clean`** — `text.clean_text()` normalizes text (unidecode, paragraph breaks, optional `--max-chars` sentence-boundary splitting). Writes `<basename>-clean.txt`.
3. **`--plan` / `--encode`** — `plan()` builds a `Manifest` via `text.parse_text()` (one `Fragment` per line by default; lines combined up to `--max-chars`). `--plan` writes `<basename>-plan.json` without encoding.
4. **`--encode`** — `Encoder.encode_manifest()` synthesizes each fragment to an audio file and updates the manifest in place. Optionally writes `<basename>-manifest.json`.
5. **`--concat`** — `audio.concat_files()` stitches fragment audio into `<basename>.<ext>`.

There's also a standalone **`--audition SEEDS`** mode (`main.audition()`): given a preset `--voice-id` (or a `--voice-description`, or a clone `--voice-ref-audio` — exactly one) and a sample sentence, it synthesizes a candidate reference clip per seed — `SEEDS` is an `--indexes`-style spec parsed by `main.parse_seeds()` (`5`, `1-5`, `3,9,20`; closed ranges only) — so the best take can be adopted as a clone anchor. It reuses `encode_manifest()` by building a synthetic `Manifest` of `N` same-text fragments with per-seed `QwenVoice`s, writes a `*-audition.json` index, and prints a table. A **`--list-voices`** mode prints the server's built-in presets (`Encoder.list_voices()` → `GET /v1/voices` on qwen, `GET /get_predefined_voices` on chatterbox). `--voice-id` accepts a comma-separated list when auditioning, which sweeps several presets at once (a candidate per voice per seed) — the way to shop for a voice on Chatterbox, which cannot design one; `--adopt` then needs `--voice-id` too, since the seed alone no longer names one candidate. A standalone **`--add-voice NAME`** mode (`main.add_voice()`) registers a clip you already have (a human recording) straight into `--voices-file`, building the voice from the ordinary `--voice-*` args — no audition. A clip already inside the library is referenced in place; one from outside is copied in under the voice's name. It shares `main.write_named_voice()` with adopt. The companion **`--adopt SEED`** mode (`main.adopt()`) reads that index (the inputfile), builds a clone `QwenVoice` from the chosen candidate (carrying its `ref_text`/`seed`/`temperature`), **copies the clip into `--clips-dir` named for the voice** (`paths.clip_filename()` + `main.copy_clip()`, a no-op if it's already there; `--clips-dir` defaults to `$ZAPHODVOX_CLIPS_DIR` else beside the voices file, and a relative value is resolved against the *voices file's* directory because it describes the library's layout, not the CWD), and adds/updates it under `--voice-name` in `--voices-file`. The copy is what lets you audition into a scratch dir and delete it afterwards — the library ends up holding every clip it references. Nothing is ever deleted; the rejected candidates are left alone so a different seed can still be adopted later. Both are mutually exclusive with the other action flags. Auditioning a *clone* source re-clones it, so adopting a candidate re-anchors the voice to clean synthetic audio — that's the supported way to launder a noisy human recording into a usable reference, and it's a one-hop operation (each pass is a generation of copying, and artifacts compound).

A separate **`--proof`** mode (`main.proof()`) runs read-only checks over the manuscript and writes a `*-proof.json` report (of `ProofReport`/`ProofFinding`, in `proof.py`) plus a table; it never edits the text. Deterministic checks (`proof.py` + `dictionary.py`/`pyspellchecker` + a project wordlist): spelling, repeated/unusual characters, whitespace. When `--llm-url` (or `ZAPHODVOX_LLM_URL`) is set, `llm.py` adds a **local** LLM pass (`LLMClient` → OpenAI-compatible `/v1/chat/completions`, chunked, low temp, JSON-schema output) for contextual/structural issues (homophones, garbled sentences, chapter-header consistency), merged into the report as `source: "llm"`. Per project rule the LLM is **local only, never cloud** (see the memory constraint). The companion **`--add-word`** mode appends accepted spellings to the `--dict` wordlist.

If no action flag is given, the program prints a quip and exits 0 (`handle_version_and_ntd`). All exceptions bubble to `main()`'s top-level handler, which prints a red error and exits 1.

## Key architectural concepts

**Encoder registration is subclass-based.** `main.encoder_class()` finds the encoder by iterating `Encoder.__subclasses__()` and matching `cls.name`. This means **an encoder module must be imported somewhere before it can be discovered**. `arg_parser.py` imports `QwenEncoder` and `ChatterboxEncoder` explicitly to register them and to populate the `--encoder-name` choices; `voices.py` imports their `Voice` subclasses for the same reason. If you add another encoder, import it in both.

**Voices are polymorphic and self-describing** (as of 2.3.0). A serialized voice records its `encoder`, which is how it is read back as the right subclass (`voices.parse_voice()`) — so one voices file can be a library for both engines. `Voice` sets `extra='forbid'`, and that is **load-bearing, not tidiness**: without it a voice for one engine would quietly validate as a voice for the other, silently dropping every setting the other does not recognize. `QwenVoice.encoder` defaults to `'qwen'`, so a file written before the tag existed still reads back as what it was. What the engines share lives on the `Voice` base (`ref_audio` + its anchoring, `seed`, `temperature`, `label`); what they do not stays on the subclass.

**Encoder is an ABC** (`src/zaphodvox/encoder.py`). Subclasses implement `audio_format`, `file_extension`, `from_args()`, `list_voices()` (the server's presets, for `--list-voices`), `clone_voice()` (the `Voice` that `--adopt`/`--add-voice` write into the library, since only the backend knows which settings a clone of its own carries), and `t2s()`. `validate_voice()` is an optional hook (see below). The base `encode_manifest()` handles iteration, the progress bar, per-fragment silence, voice resolution, and converting runs of `\n\n+` into pauses via `break_tag`. **Qwen takes plain text, not SSML** — so `break_tag`'s default renders paragraph breaks as plain sentence stops (`' . '`, not SSML `<break>` tags), and `QwenEncoder.t2s()` sends the fragment text as-is (no `<speak>` wrapping). A future SSML-based encoder would override `break_tag`. The whole `qwen` backend lives in `src/zaphodvox/qwen/` (`encoder.py`, `voice.py`).

**ChatterboxEncoder is a thin HTTP client too** (`chatterbox/encoder.py`, added 2.3.0 for issue #36). It targets the server's **native `POST /tts`**, not the OpenAI-compatible `/v1/audio/speech` (which demands a meaningless `model` field and re-chunks text we have already fragmented — hence `split_text: false`). **Cloning is two requests, not one**: the clip is uploaded via `POST /upload_reference` and then referred to by name; `ChatterboxEncoder._reference()` caches the upload so a book of 3,000 fragments sends the clip once. Chatterbox has **no voice design and no ICL clone mode**, and steers delivery numerically (`exaggeration`/`cfg_weight`/`speed_factor`) rather than with `instruct` — `ChatterboxVoice.from_args()` raises on `--voice-description`/`--voice-instruct`/`--voice-ref-text` rather than silently ignoring them, which would mean discovering after a whole book that the setting never applied. Base URL from `--chatterbox-url` (default `http://127.0.0.1:8004`, env `ZAPHODVOX_CHATTERBOX_URL`). Both servers hold a model in VRAM, so in practice only one runs at a time.

**The two backends are not peers, and qwen is the one to narrate with.** Chatterbox routinely keeps generating audio *after* it has finished speaking the text, leaving a few hundred milliseconds of invented sound — a "robotic breath," distortion, a smeared syllable — at the end of a clip. This is endemic to the model, not a misconfiguration: Chatterbox ships a runtime detector for it (`AlignmentStreamAnalyzer`, whose `forcing EOS token, long_tail=True` warning fills the server log), and that detector can only fire *after* several frames of the artifact already exist, so it curbs the damage rather than preventing it. It fires on long fragments (alignment drifts off the end of the text) *and* on short ones (the text completes immediately, leaving the decoder runway to wander), so `--max-chars` reduces the rate without fixing the cause. Measured against qwen on the same text, qwen artifacts at near zero. Conclusions, so this is not rediscovered the hard way:
- **Don't switch the default, and don't "optimize" fragment sizing to fix this.** It has been tried; the failure is architectural (an autoregressive token model that can run past its text), not a parameter.
- **Chatterbox earns its keep for auditioning voices**, where a trailing breath on a candidate is irrelevant — `--adopt` re-clones the candidate anyway.
- If someone does want to narrate with it, the fix is downstream: trim each fragment's tail (energy-based, not a fixed chop). Safe here because zaphodvox supplies its own inter-fragment silence at concat, so the model's trailing frames are not load-bearing. Not implemented — deliberately.
- Its defaults are hot for long-form (server-side `exaggeration: 1.3`, `temperature: 0.8`, inherited whenever `--voice-*` omits them). `0.5`/`0.6` is steadier, but only reduces the rate.

**QwenEncoder is a thin HTTP client** (`qwen/encoder.py`). `t2s()` dispatches on the voice: a preset speaker POSTs JSON to `{url}/v1/audio/speech`; a clone POSTs multipart (the reference audio file) to `{url}/v1/audio/speech/upload`; a design POSTs JSON to `{url}/v1/audio/speech/design`. All write the raw response bytes to the fragment file and are wrapped in a `tenacity` retry. Server base URL comes from `--qwen-url` (default `http://127.0.0.1:4123`, env `ZAPHODVOX_QWEN_URL`).

**Voice model.** The `Voice` base (`voice.py`) carries what both engines share — `voice_id`, `ref_audio` (plus its anchoring, below), `seed`, `temperature`, `label` — and each backend subclasses it for what they do not. A `QwenVoice` (`qwen/voice.py`) is one of: a **preset** (`voice_id`, e.g. `"Ryan"`, with optional `instruct` emotion/style), a **clone** (`ref_audio`, optional `ref_text` transcript for ICL vs. zero-shot), or a **design** (`description`, a natural-language voice); a `model_validator` enforces exactly one, and `is_clone`/`is_design` distinguish them. A `ChatterboxVoice` has no design and no ICL — preset or clone only.

Designs are the least consistent for long content — the intended pattern is design → `--audition` → `--adopt` as a clone. `seed` pins the server's RNG so a voice stays consistent across chunks and re-encodes; `temperature` tunes run-to-run variability (lower is steadier), not expressiveness. Both are sent per request and serialized with the voice into the manifest. On qwen both require the `eddie-tts` fork; upstream `qwen3-tts-api` implements neither. `--voice-id` and `--voice-ref-audio` are the mutually-exclusive CLI entry points.

**Voice reference paths are anchored to the file that declares them** (`paths.py`, as of 2.2.0). A clone's `ref_audio` is meaningless without an anchor, and voices *travel between files* — `encode_manifest()` copies a resolved voice onto the fragment, so a path written in a voices file gets copied into the project's manifest. Two halves, both required:
- **Read:** `resolve_ref()` — absolute as-is, leading `~` expanded, relative resolved against the declaring file's directory. `Voice._base_dir` (a `PrivateAttr` on the *base*, never serialized, so both backends get this for free) holds that anchor; `main.anchor_voices()` sets it in `read_voices()` and `read_text_manifest()`. A voice from the CLI has no anchor and stays CWD-relative. `Voice.anchor()` no-ops when there is no `ref_audio` — otherwise two identical preset voices read from different files would compare unequal, since Pydantic includes private attrs in `__eq__`.
- **Write:** `rebase_ref()` — rewrites a path to stay valid from the file being written. Inside the target's tree it stays relative (so a voice library stays self-contained and movable); outside it becomes `~/`-anchored, else absolute (a `../../` escape would break as soon as the two directories moved independently, and can't cross Windows drives). Applied in `write_manifest()` and `adopt()`. `write_manifest()` rebases a `model_copy(deep=True)` — mutating the live manifest would corrupt a following `--concat`.

Path arguments from the CLI and the environment go through `paths.expanded_path()`, which expands a leading `~`. The shell only does that for *some* of the spellings people use — `--out-dir ~/voices` is expanded before the program sees it, but `--out-dir=~/voices` and a quoted `ZAPHODVOX_VOICES_FILE="~/lib/voices.json"` are not, and Windows shells never are. Left alone, those arrive as a literal `~` and the program would go looking for — or create — a directory named `~`.

`Encoder.validate_voice()` is a hook (no-op on the ABC; both backends check the reference file exists) called in a pre-pass at the top of `encode_manifest()`, so a bad path fails on the command line instead of 200 fragments into a book. Its error names the raw path, where it resolved to, and the directory it was anchored against.

**Concatenation copies samples through; it does not decode them** (`audio.py`, as of 2.3.0). The old `pydub` loop (`segments += AudioSegment.from_file(...)`) was **O(n²)** — every `+=` copied the whole accumulated book again — and held the entire audiobook in memory. A 600-fragment book took ~9.5s to stitch; it now takes ~0.09s (**~105x**), in constant memory.
- **`wav`** — `_concat_wav()` streams frames straight from each fragment into the output with the stdlib `wave` module. No `pydub`, no `ffmpeg`, no subprocess, nothing decoded.
- **`mp3`** — `_concat_encoded()` hands every fragment to a *single* `ffmpeg` concat-demuxer pass, so the audio is decoded and re-encoded once, in one process, rather than spawning `ffmpeg` per fragment (~18x). Don't "optimize" this to `-c copy`: each mp3 carries its own encoder padding, which adds an audible gap at every fragment boundary (measured: 200 fragments gained 9.5s of silence).

**This only works because every fragment shares one sample format**, which is why `create_silence()` takes `AudioParams` and `Encoder.encode_manifest()` defers silent fragments until after the speech exists (`Encoder.silence_params()` reads the format off a fragment the server actually returned — only the server knows what it emits). Silence used to be written at pydub's default 11025 Hz next to 24 kHz speech, and `pydub` quietly resampled it on concat. **`ffmpeg`'s concat demuxer cannot be trusted to fix a mismatch** — given mixed rates it silently dropped audio from a wav (2.9s of a 4.0s book), even with `-ar` forced. `_concat_wav()` therefore converts any fragment whose format disagrees, one at a time, which is what keeps already-encoded books working.

**Named voices are flat.** `NamedVoices` (`named_voices.py`) is just `{name: Voice}` — a `--voices-file` and inline `ZVOX: <name>` tags in the text select a named voice directly. Flat *across* backends, too: each voice carries its own `encoder` tag, so one library file can hold qwen and chatterbox voices side by side. (Pre-2.0 this nested per-engine configs under `google`/`elevenlabs`/`alltalk` keys; the tag replaces that grouping.)

**Manifest is the serializable source of truth** (`manifest.py`, Pydantic models `Manifest` + `Fragment`). It round-trips to JSON, can be hand-edited, and fed back in as input. `--indexes` (parsed by `main.parse_indexes()`, supports `1`, `1-3`, `2-`, `-4`, comma lists) re-encodes only selected fragments in place. Fragment `voice` fields serialize polymorphically via `SerializeAsAny`; the manifest's top-level `voices` dict is `{name: Voice}` (also `SerializeAsAny`) so a manifest is self-contained and reads back as the right subclass.

**Inline voice switching.** `text.match_voice()` recognizes `ZVOX: <name>` lines; that line is not synthesized and sets the "current" voice for following fragments. Empty lines become silent fragments (`silence_duration`, rendered by `audio.create_silence`).

**Output-path resolution.** `main.file_path()` centralizes where files land: an explicit `--*-out` file path wins, else `--out-dir` + generated filename, else CWD. Generated names derive from `--basename` (defaults to the input file's stem).

## Conventions

- Pydantic v2 throughout for models and JSON (de)serialization; prefer model methods over ad-hoc dict handling.
- Both encoders wrap their HTTP calls in `tenacity` `Retrying(stop_after_attempt(5))`.
- Docstrings are Google-style and thorough; match the existing density when adding code.
- `__version__` lives in `src/zaphodvox/__init__.py` and is the Hatch version source.
