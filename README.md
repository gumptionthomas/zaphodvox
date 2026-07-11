# zaphodvox

The `zaphodvox` python package provides a command-line interface for encoding a text file into synthetic speech audio using a locally-hosted [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) server (the [`eddie-tts`](https://github.com/gumptionthomas/eddie-tts) fork of [qwen3-tts-api](https://github.com/cornball-ai/qwen3-tts-api), which wraps the open-weight Qwen3-TTS models).

## Installation

> "He was clearly a man of many qualities, even if they were mostly bad ones."

Install the latest release from PyPI:

```console
$ pip install zaphodvox
...
Successfully installed zaphodvox-2.2.0...

$ zaphodvox test.txt
Nothing to do... I'd give you advice, but you wouldn't listen. No one ever does.
```

For the latest unreleased code, install from GitHub instead:

```console
$ pip install git+https://github.com/gumptionthomas/zaphodvox.git
```

Or clone it and install in editable mode to hack on it:

```console
$ git clone https://github.com/gumptionthomas/zaphodvox.git
$ cd zaphodvox
$ pip install -e .
```

`zaphodvox` needs **Python 3.10–3.12** (its pinned dependencies don't yet ship wheels for 3.13+, so a newer interpreter will try — and fail — to build them from source; [pyenv](https://github.com/pyenv/pyenv) makes pinning one easy) and a current installation of [ffmpeg](https://ffmpeg.org/). To actually synthesize anything, it also needs a running [Qwen3-TTS server](#qwen3-tts-server).

## Qwen3-TTS Server

> "He didn't know why he had become President of the Galaxy, except that it seemed a fun thing to be."

`zaphodvox` does no synthesis itself. It talks to a locally-hosted [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) server that exposes an OpenAI-style speech API, so you must have one running before encoding.

The server needs to expose three endpoints:

- `POST /v1/audio/speech` for built-in preset speakers.
- `POST /v1/audio/speech/upload` for zero-shot voice cloning.
- `POST /v1/audio/speech/design` for voices generated from a description.

The reference implementation is [**`eddie-tts`**](https://github.com/gumptionthomas/eddie-tts) — a Windows-friendly fork of [`cornball-ai/qwen3-tts-api`](https://github.com/cornball-ai/qwen3-tts-api), which in turn serves the open-weight [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) models. Follow Eddie's README to install and run it. **The `--voice-seed` and `--voice-temperature` options require Eddie** — upstream `qwen3-tts-api` implements neither `seed` nor `temperature`, so on that server those flags are silently ignored. The models want an NVIDIA GPU, so a CUDA-capable card is effectively a prerequisite for the server (not for `zaphodvox`). No API keys or authentication are involved, as the server is expected to be local and trusted.

By default `zaphodvox` talks to the server at `http://127.0.0.1:4123`. Override the base URL with the `--qwen-url` argument or the `ZAPHODVOX_QWEN_URL` environment variable.

## Usage

> "I refuse to answer that question on the grounds that I don't know the answer."

Detailed usage information can be printed by running:

```bash
zaphodvox --help
```

Some examples using the following text file (`gone-bananas.txt`):

```text
This is the first line of text.
This is the next line. By default, each line of text is sent to the server individually.
This is the last line. And this is a sentence that is split
between lines. Ideally, these parts of the sentence would be on the same line.
```

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --encode gone-bananas.txt
```

Running the above command will encode the text file with the locally-hosted [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) server using the `Ryan` preset speaker. This will result in the following fragment audio files being created in the current directory (one file for each line of text):

```console
gone-bananas-00000.wav ["This is the first line..."]
gone-bananas-00001.wav ["This is the next line. By default..."]
gone-bananas-00002.wav ["This is the last line. And this is..."]
gone-bananas-00003.wav ["between lines. Ideally, these..."]
```

In addition to the audio files, a manifest JSON file (`gone-bananas-manifest.json`) will also be written to the current directory. This file contains information about the fragment audio files encoded, including the text, the relative file name, and the voice used. This manifest file can also be used as input to the command rather than a text file. See the [manifest documentation](#manifest) for more information.

### Voices: Presets, Clones, and Designs

A Qwen voice is one of: a built-in **preset speaker**, a zero-shot **clone** of a reference audio file, or a **design** generated from a text description. `--voice-id` (preset), `--voice-ref-audio` (clone), and `--voice-description` (design) are mutually exclusive.

To use a **preset speaker**, pass its name to `--voice-id`. The available speakers are `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric`, `Ryan`, `Aiden`, `Ono_Anna`, and `Sohee`. You can optionally steer the delivery with `--voice-instruct` and set the language with `--voice-language`:

```bash
zaphodvox --encoder=qwen --voice-id=Eric --voice-instruct="depressed, morose" --encode gone-bananas.txt
```

The default language is `English`. Other supported values are `Chinese`, `Japanese`, `Korean`, `German`, `French`, `Russian`, `Portuguese`, `Spanish`, and `Italian`:

```bash
zaphodvox --encoder=qwen --voice-id=Dylan --voice-language=French --encode gone-bananas.txt
```

To **clone a voice**, pass a reference audio file to `--voice-ref-audio` instead of a `--voice-id`:

```bash
zaphodvox --encoder=qwen --voice-ref-audio=trillian-sample.wav --encode gone-bananas.txt
```

Without a transcript, this performs a true zero-shot clone. If you also provide the transcript of the reference audio via `--voice-ref-text`, the server uses the higher-quality in-context (ICL) clone mode:

```bash
zaphodvox --encoder=qwen --voice-ref-audio=trillian-sample.wav --voice-ref-text="Well, hello there." --encode gone-bananas.txt
```

To **design a voice** from a natural-language description, pass it to `--voice-description`:

```bash
zaphodvox --encoder=qwen --voice-description="a warm elderly woman, gentle and unhurried" --encode gone-bananas.txt
```

Note that a designed voice is the least consistent choice for a whole book — the model re-derives the voice from the description on each call. For steady narration, design a voice, audition it, and **adopt the best take as a clone** (see [Auditioning a reference voice](#auditioning-a-reference-voice) below); the clone then anchors every chunk.

The audio output format is `wav` by default. Use `--qwen-audio-format` to select `wav` or `mp3`:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --qwen-audio-format=mp3 --encode gone-bananas.txt
```

By default each fragment is synthesized non-deterministically, so a voice can drift in timbre and pacing from chunk to chunk. Pin a fixed RNG seed with `--voice-seed` to keep a voice consistent across every fragment (and across re-encodes). Combining it with a larger `--max-chars` gives the steadiest results:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --voice-seed=42 --max-chars=500 --encode gone-bananas.txt
```

The seed is stored with the voice in the manifest, so re-encoding a fragment reproduces the same audio.

A seed makes a given fragment *reproducible*, but the model still reads different lines with different energy — that variation is driven by the text itself. `--voice-temperature` tunes how much the delivery **varies from run to run**, not how flat or dramatic it is: lower is steadier and more repeatable, higher is more varied. It is *not* an expressiveness dial — on the same sentence, `0.3` and `1.0` are barely distinguishable by ear. For actual style control, reach for `--voice-instruct` (preset voices) or `--voice-description` (designed voices), which move the voice far more than temperature does.

### Auditioning a reference voice

> "The ships hung in the sky in much the same way that bricks don't."

For the most consistent narration, clone every chunk from a single fixed reference clip rather than relying on a preset or a design. The `--audition` argument helps you find a good reference: it synthesizes a candidate clip of a preset (`--voice-id`) or designed (`--voice-description`) voice for each seed you specify — using the same syntax as `--indexes` (`5`, `1-5`, `3,9,20`) — from a sample sentence you provide:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan \
  --voice-instruct="calm narrator, neutral American accent" --voice-temperature=0.6 \
  --audition=1-5 --audition-text="It is a mistake to think you can solve any major problems just with potatoes." \
  --out-dir=refs
```

This writes `ryan-audition-01.wav` … `ryan-audition-05.wav` (the basename defaults to the voice name; files are named by seed), plus a `ryan-audition.json` index, and prints a table of the candidates. `--voice-instruct` and `--voice-temperature` apply to every candidate (only the seed varies), so audition at the same temperature you plan to encode with. Aim for ~10–15 seconds of speech in `--audition-text` so the clip works well as a reference; a short sample gets a warning. If `--audition-text` is omitted, the first line of the `inputfile` is used. (Auditioning seeds `1-5` rather than `0-4` is a fine habit — nothing is special about seed `0`, but starting at `1` avoids always judging the same seed-`0` take first.)

Listen to the candidates and adopt the one you like with `--adopt`, giving it a name and a voices file to write to (the audition index is the inputfile):

```bash
zaphodvox --adopt=2 --voice-name=Narrator --voices-file=voices.json refs/ryan-audition.json
```

This adds (or updates) a `Narrator` clone voice in `voices.json` that references the chosen candidate clip, carrying over its `ref_text`, `seed`, and `temperature` from the audition. From then on, `ZVOX: Narrator` (or `--voice-name=Narrator`) reads with that voice. `--voice-seed`/`--voice-temperature` override the carried-over values if given. Auditioning and adopting are each their own mode and can't be combined with `--encode`/`--plan`/`--concat`.

### Concatenation

To combine the individual fragment audio files into one, add the `--concat` argument:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --encode --concat gone-bananas.txt
```

An additional audio file, `gone-bananas.wav`, will be saved in the current directory.

### Cleaning

Note that there isn't much silence between individual lines of the text file. To add a delay between lines, simply add an extra newline between each line of text. The easiest way to do this is to use the `--clean` option:

```bash
zaphodvox --clean gone-bananas.txt
```

This command will convert the text file to plain text and attempt to add an extra newline between paragraphs as well as combine sentences that have been split between adjacent lines. It will output the newly "cleaned" text file as `gone-bananas-cleaned.txt`:

```text
This is the first line of text. It should probably be a paragraph.

This is the next line. By default, each line of text is sent to the server individually.

This is the last line. And this is a sentence that is split between lines. Ideally, these parts of the sentence would be on the same line.
```

Encode this new file:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --encode --concat gone-bananas-cleaned.txt
```

Notice that a pause is generated for each empty newline and that the last sentence is no longer split between lines.

The `--clean` and `--encode` arguments can be combined in a single call:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --clean --encode --concat gone-bananas.txt
```

If the `--max-chars` argument is provided, the cleaning process will guarantee that every line is less than `max-chars` characters by splitting long lines at sentence boundaries.

The text file will be cleaned before being encoded and concatenated into `gone-bananas.wav`. The cleaned text file (i.e. `gone-bananas-cleaned.txt`) will still be created in the current directory.

### Proofing

> "The Guide is definitive. Reality is frequently inaccurate."

Before encoding, `--proof` scans the manuscript for issues and writes a report. It is **read-only** — it never edits your text; you fix things by hand from the report (the findings carry line numbers). The deterministic checks are:

- **Spelling** — words absent from the dictionary and your project wordlist, grouped by unique word (so 500 occurrences of a character's name are one entry, not 500), with suggestions.
- **Repeated characters** — runs like `****` or `___` (stray markup or OCR artifacts).
- **Unusual characters** — control characters, replacement characters (`U+FFFD`), zero-width and non-breaking spaces, and other gremlins.
- **Whitespace** — trailing whitespace, tabs, and runs of blank lines.

```bash
zaphodvox --proof --dict gone-bananas.dict gone-bananas.txt
```

This writes `gone-bananas-proof.json` (and prints a table). The **project wordlist** (`--dict`, defaulting to `[basename].dict`) is a plain, version-controllable file of accepted spellings — one word per line, `#` comments allowed. When the proofer flags a real name or coined word, add it once and it stops being flagged:

```bash
zaphodvox --add-word Zaphod Beeblebrox Magrathea --dict gone-bananas.dict
```

The dictionary language defaults to `en` (override with `--dict-language`).

#### LLM-assisted proofreading

The deterministic checks above catch mechanical issues, but not contextual ones. Point `--llm-url` at a local [OpenAI-compatible](https://platform.openai.com/docs/api-reference/chat) LLM server (e.g. [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/)) to add a proofreading pass that also flags homophones (their/there), doubled words, garbled sentences, and inconsistent chapter headers:

```bash
zaphodvox --proof --llm-url=http://127.0.0.1:1234 --llm-model=qwen2.5-7b-instruct book.txt
```

These findings are merged into the same report with `source: "llm"`. Only a **local** LLM is ever contacted — no cloud service is used. The pass is skipped unless `--llm-url` (or the `ZAPHODVOX_LLM_URL` environment variable) is set; `--llm-model` defaults to the `ZAPHODVOX_LLM_MODEL` environment variable when not given. Like the deterministic checks, it is advisory: nothing is changed automatically.

## Voice Configurations

> "I'm so great even I get tongue-tied talking to myself."

Multiple voice configurations can be defined in a JSON file and loaded via the `--voices-file` argument (which defaults to the `ZAPHODVOX_VOICES_FILE` environment variable).

This is an example voice configuration file (`voices.json`):

```json
{
    "voices": {
        "Marvin": {
            "voice_id": "Eric",
            "language": "English",
            "instruct": "depressed, morose, flat and weary",
            "seed": 7
        },
        "Ford": {
            "voice_id": "Dylan",
            "language": "English",
            "instruct": "wry, casual, neutral American accent",
            "seed": 42
        },
        "Trillian": {
            "ref_audio": "trillian-sample.wav",
            "ref_text": "Well, hello there.",
            "seed": 101
        }
    }
}
```

Each named voice maps directly to the [Qwen voice](#qwen-voice-configuration) fields, so the voices file is the natural home for per-voice tuning: give each voice its own `instruct` (to pin its delivery and accent) and its own `seed` (so a character sounds like themselves across every chunk, and re-encodes reproduce). Tune a voice on the CLI until it sits right, then park that exact `instruct`/`seed` here and forget it. Note that `instruct` steers preset voices only — for a cloned voice (like `Trillian` above), the reference clip's own delivery sets the tone.

If a `--voices-file` is used, inline `ZVOX: [name]` tags in a text `inputfile` can specify the voice(s) to be used.

A example multi-voice text file (`heart-of-gold.txt`):

```text
ZVOX: Marvin
This text will be spoken by the Marvin voice defined in the voices JSON file. That is, it will use the
"Eric" preset speaker with a "depressed, morose" instruction and seed 7.

ZVOX: Ford
This line will be spoken by the Ford voice. That is, it will use the "Dylan" preset speaker with its own
instruction and seed.

This paragraph will also be spoken by the Ford voice as it is still the "current" voice.

ZVOX: Trillian // This is a cloned voice
Finally, this will be read by the Trillian voice, cloned from "trillian-sample.wav". Note that text following a space after the voice name will be ignored.
If a line contains the "ZVOX" tag, it will not be synthesized to speech.
```

```bash
zaphodvox --voices-file=voices.json --encoder=qwen --encode heart-of-gold.txt
```

The above command will result in the following fragment audio files to be created in the current directory:

```console
heart-of-gold-00000.wav ["This text will be spoken by the..." using "Marvin" voice]
heart-of-gold-00001.wav [silence]
heart-of-gold-00002.wav ["This line will be spoken by the..." using "Ford" voice]
heart-of-gold-00003.wav [silence]
heart-of-gold-00004.wav ["This paragraph will also..." using "Ford" voice]
heart-of-gold-00005.wav [silence]
heart-of-gold-00006.wav ["Finally, this will be read by the..." using "Trillian" voice]
heart-of-gold-00007.wav ["If a line contains the..." using "Trillian" voice]
```

### Qwen Voice Configuration

> "He preferred people to be puzzled rather than contemptuous."

The JSON voice configuration follows the CLI "voice" arguments fairly closely. One difference is that CLI defaults don't necessarily apply in all cases.

A voice is either a **preset** (a built-in speaker named by `voice_id`) or a **clone** (a zero-shot clone of the reference audio at `ref_audio`). Exactly one of `voice_id` or `ref_audio` is required.

The fields are:

- `voice_id`: The built-in preset speaker name (one of `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric`, `Ryan`, `Aiden`, `Ono_Anna`, `Sohee`). Mutually exclusive with `ref_audio`/`description`.
- `language`: The language of the text (defaults to `English`).
- `instruct`: An optional style/emotion direction for a preset voice (e.g. `calm, wry`). Ignored for cloned/designed voices.
- `ref_audio`: The path to a reference audio file to clone. Mutually exclusive with `voice_id`/`description`. A relative path is resolved against the directory of the file it is written in (see [A shared voice library](#a-shared-voice-library)), an absolute path or a `~/`-prefixed one is used as-is.
- `ref_text`: The transcript of `ref_audio`. If set, the higher-quality in-context (ICL) clone mode is used; otherwise a true zero-shot clone is used.
- `description`: A natural-language description of a voice to design (e.g. `a warm elderly woman`). Mutually exclusive with `voice_id`/`ref_audio`.
- `seed`: An optional fixed RNG seed. When set, every fragment using this voice is synthesized from the same seed, keeping the voice consistent across chunks and across re-encodes. Defaults to non-deterministic.
- `temperature`: An optional sampling temperature — how much the delivery varies from run to run (lower is steadier and more repeatable, higher is more varied), *not* an expressiveness control. Eddie defaults to `0.65` (narration-tuned), lower than Qwen's ~`0.9`, so moving from upstream `qwen3-tts-api` to Eddie changes the default output.

A preset example:

```json
{
    "voice_id": "Eric",
    "language": "English",
    "instruct": "depressed, morose",
    "seed": 42
}
```

A clone example:

```json
{
    "ref_audio": "trillian-sample.wav",
    "ref_text": "Well, hello there."
}
```

A design example:

```json
{
    "description": "a warm elderly woman, gentle and unhurried",
    "seed": 7,
    "temperature": 0.6
}
```

### A shared voice library

> "The ships hung in the sky in much the same way that bricks don't."

A clone's `ref_audio` is resolved **relative to the file that declares it**, not to the directory you happen to run from. That means a voices file and its reference clips can live together in one place and be used from any project:

```console
~/voices/
    library.json        ["Narrator" -> "narrator.wav", "Trillian" -> "trillian.wav"]
    narrator.wav
    trillian.wav
```

```console
$ cd ~/books/hitchhiker
$ zaphodvox --voices-file=~/voices/library.json --encoder=qwen --encode --voice-name=Narrator book.txt
```

`narrator.wav` is found next to `library.json`, wherever you run from. Point `ZAPHODVOX_VOICES_FILE` at the library once and you can drop the `--voices-file` argument entirely.

Because the library sits outside the project, the voice written into the project's manifest is rewritten to remain valid from *there* (as `~/voices/narrator.wav`), so the manifest can still re-encode itself later on its own. Within a directory the paths stay relative — `--adopt` writes a clip that sits beside the voices file as a bare `narrator.wav` — so the library as a whole stays self-contained and can be moved or committed as a unit.

A missing reference clip is reported before encoding begins, rather than partway through a long book.

## Manifest

> “If I ever meet myself, I'll hit myself so hard I won't know what's hit me.”

A manifest JSON file is created during the encoding process and can be used as the inputfile instead of a text file. If a manifest file is used, the fragment audio files to be re-encoded can be specified with the `--indexes` argument.

For example, consider this simple text file (`towel.txt`):

```text
Don't forget your towel.
And always know where it is.
```

The file is encoded with this command:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --encode towel.txt
```

Three files will be created in the current directory: the two fragment audio files (`towel-00000.wav` and `towel-00001.wav`) and the manifest file (`towel-manifest.json`).

Here are the contents of `towel-manifest.json`:

```json
"fragments":
[
    {
        "text": "Don't forget your towel.",
        "filename": "towel-00000.wav",
        "voice":
        {
            "voice_id": "Ryan",
            "language": "English"
        },
        "silence_duration": null,
        "encoder": "qwen",
        "audio_format": "wav"
    },
    {
        "text": "And always know where it is.",
        "filename": "towel-00001.wav",
        "voice":
        {
            "voice_id": "Ryan",
            "language": "English"
        },
        "silence_duration": null,
        "encoder": "qwen",
        "audio_format": "wav"
    }
]
```

Note that the fragment `filename`s are relative to the manifest file's location.

Changes can be made to fragment `text`, `filename`, or `voice` items and the modified manifest file can be used to re-encode only the changes by specifying which fragment indexes to encode.

For example, if the second fragment's `text` field is modified to remove the initial "And", this command will re-encode only the second fragment audio file in place (i.e. `towel-00001.wav`):

```bash
zaphodvox --encoder=qwen --encode --indexes=1 towel-manifest.json
```

The `--concat` argument can also be added when using a manifest file as input. In this case, an attempt will be made to concatenate both the unmodified and newly encoded fragment audio files into one. If any of the files specified in the manifest is missing, the concatenation will fail.

A manifest plan can be created from a text file using the `--plan` argument:

```bash
zaphodvox --encoder=qwen --voice-id=Ryan --plan gone-bananas.txt
```

The above command will write the manifest plan to `gone-bananas-plan.json` without doing any encoding. It can be reviewed and edited before being used as input to the command with the `--encode` argument.

By default, each line of the text file is encoded into its own audio fragment. If the `--max-chars` argument is provided when generating a plan manifest or encoding a text file, the planning process will attempt to combine multiple lines of text per audio fragment, up to `max-chars` characters. Larger fragments often encode with better results.
