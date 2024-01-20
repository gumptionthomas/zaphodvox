The `zaphodvox` python package provides a command-line interface for encoding a text file into synthetic speech audio using either the [Google Text-to-Speech API](https://cloud.google.com/text-to-speech/docs) or the [ElevenLabs Speech Synthesis API](https://elevenlabs.io/docs).

# Installation

> "He was clearly a man of many qualities, even if they were mostly bad ones."

```console
$ pip install zaphodvox
...
Successfully installed zaphodvox...

$ zaphodvox --help
usage: zaphodvox --blah --blah --blah --beware --blah whatever
...
$ zaphodvox test.txt
Nothing to do... I'd give you advice, but you wouldn't listen. No one ever does.

$ pip uninstall zaphodvox
...
Successfully uninstalled zaphodvox...
```

# Authorization

> "He didn't know why he had become President of the Galaxy, except that it seemed a fun thing to be."

Authorization credentials are required for both the Google Text-To-Speech APIs and the ElevenLabs Speech Synthesis APIs. These can be specified either by defining environment variables or using CLI arguments.

## Google

The Google encoder requires that you set up an account, project, and service account JSON key as described in the ["Before You Begin"](https://cloud.google.com/text-to-speech/docs/before-you-begin) documentation.

You can set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the downloaded service account file path or you can pass the file path directly to the CLI with the `--service-account` argument.

## ElevenLabs

The ElevenLabs encoder requires that you set up an account and generate an API key as described in the ["Authentication"](https://elevenlabs.io/docs/api-reference/text-to-speech#authentication) section of the [API Reference documentation](https://elevenlabs.io/docs/api-reference/text-to-speech).

You can set the `ELEVEN_API_KEY` environment variable to the API key copied from your profile page or you can pass the key directly to the CLI with the `--api-key` argument.

# Usage

> "I refuse to answer that question on the grounds that I don't know the answer."

Detailed usage information can be printed by running:

```bash
$ zaphodvox --help
```

Some examples using this text file (`gone-bananas.txt`):

```text
This is the first line of text.
This is the next line. By default, each line of text is sent to the API individually.
This is the last line. And this is a sentence that is split
between lines. Ideally, these parts of the sentence would be on the same line.
```

```bash
$ zaphodvox --encoder=google --voice-id=A --encode gone-bananas.txt
```

Running the above command will encode the text file using the [Google Text-to-Speech API](https://cloud.google.com/text-to-speech/docs) with the `en-US-Wavenet-A` voice. This will result in the following fragment audio files being created in the working directory (one file for each line of text):

```console
gone-bananas-00000.wav ["This is the first line..."]
gone-bananas-00001.wav ["This is the next line. By default..."]
gone-bananas-00002.wav ["This is the last line. And this is..."]
gone-bananas-00003.wav ["between lines. Ideally, these..."]
```

In addition to the audio files, a manifest JSON file (`gone-bananas-manifest.json`) will also be written to the working directory. This file contains information about the fragment audio files encoded, including the text, the relative file name, and the voice used. This manifest file can also be used as input to the command rather than a text file. See the [manifest documentation](#manifest) for more information.

## Concatenation

To combine the individual fragment audio files into one, add the `--concat` argument:

```bash
$ zaphodvox --encoder=google --voice-id=A --encode --concat gone-bananas.txt
```

Now only a single audio file, `gone-bananas.wav`, will be created in the working directory.

## Cleaning

Note that there isn't much silence between individual lines of the text file. To add a delay between lines, simply add an extra newline between each line of text. The easiest way to do this is to use the `--clean` option:

```bash
$ zaphodvox --clean gone-bananas.txt
```

This command will convert the text file to plain text and attempt to add an extra newline between paragraphs as well as combine sentences that have been split between adjacent lines. It will output the newly "cleaned" text file as `gone-bananas-cleaned.txt`:

```text
This is the first line of text. It should probably be a paragraph.

This is the next line. By default, each line of text is sent to the API individually.

This is the last line. And this is a sentence that is split between lines. Ideally, these parts of the sentence would be on the same line.
```

Encode this new file:

```bash
$ zaphodvox --encoder=google --voice-id=A --encode --concat gone-bananas-cleaned.txt
```

Notice that there's 500ms of silence (the default) generated for each empty newline and that the last sentence is no longer split between lines.

The `--clean` and `--encode` arguments can be combined in a single call:

```bash
$ zaphodvox --encoder=google --voice-id=A --clean --encode --concat gone-bananas.txt
```

If the `--max-chars` argument is provided, the cleaning process will guarantee that every line is less than `max-chars` characters by splitting long lines at sentence boundaries.

The text file will be cleaned before being encoded and concatenated into `gone-bananas.wav`. The cleaned text file (i.e. `gone-bananas-cleaned.txt`) will still be created in the working directory.

# Voice Configurations

> "I'm so great even I get tongue-tied talking to myself."

Multiple voice configurations can be defined in a JSON file and loaded via the `--voices-file` argument.

An example voice configuration file (`voices.json`):

```json
{
    "voices": {
        "Marvin": {
            "google": {
                "voice_id": "A",
                "language": "en",
                "region": "US",
                "type": "Neural2"
            },
            "elevenlabs": {
                "voice_id": "EXAVITQu4vr4xnSDxMaL"
            }
        },
        "Ford": {
            "google": {
                "voice_id": "D",
                "language": "en",
                "region": "GB",
                "type": "Wavenet"
            },
            "elevenlabs": {
                "voice_id": "TxGEqnHWrfWFTfGW9XjX"
            }
        },
        "Trillian": {
            "google": {
                "voice_id": "C",
                "language": "en",
                "region": "GB",
                "type": "Wavenet"
            },
            "elevenlabs": {
                "voice_id": "EeMfvkfxDAepqPVNPE8M"
            }
        }
    }
}
```

If a `--voices-file` JSON file is used, inline `ZVOX: [name]` tags in a text `inputfile` can specify the voice(s) to be used.

A example multi-voice text file (`heart-of-gold.txt`):

```text
ZVOX: Marvin
This text will be spoken by the Marvin voice defined in the voices JSON file. That is, it will use either the
specified Google voice (i.e. "en-US-F-Wavenet") or ElevenLabs voice (i.e. voice ID "EXAVITQu4vr4xnSDxMaL")
depending on which encoder is used.

ZVOX: Ford
This will line be spoken by the Ford voice. That is, it will use either the specified Google voice
(i.e. "en-US-D-Wavenet") or ElevenLabs voice (i.e. voice ID "TxGEqnHWrfWFTfGW9XjX") depending on which
encoder is used.

This paragraph will also be spoken by the Ford voice as it is still the "current" voice.

ZVOX: Trillian // This is a UK female voice
Finally, this will be read by the Trillian voice. Note that text following a space after the voice name will be ignored.
If a line contains the "ZVOX" tag, it will not be synthesized to speech.
```

```bash
$ zaphodvox --voices-file=voices.json --encoder=google --encode heart-of-gold.txt
```

The above command will result in the following fragment audio files to be created in the working directory:

```console
heart-of-gold-00000.wav ["This text will be spoken by the..." using "Marvin" google voice]
heart-of-gold-00001.wav [500ms silence]
heart-of-gold-00002.wav ["This line will be spoken by the..." using "Ford" google voice]
heart-of-gold-00003.wav [500ms silence]
heart-of-gold-00004.wav ["This paragraph will also..." using "Ford" google voice]
heart-of-gold-00005.wav [500ms silence]
heart-of-gold-00006.wav ["Finally, this will be read by the..." using "Trillian" google voice]
heart-of-gold-00007.wav ["If a line contains the..." using "Trillian" google voice]
```

## Voice Configurations

> "He preferred people to be puzzled rather than contemptuous."

The JSON voice configurations for both Google and ElevenLabs follow the CLI "voice" arguments fairly closely. One difference is that CLI defaults don't necessarily apply in all cases.

### Google

See the Google documentation for [Supported Voices](https://cloud.google.com/text-to-speech/docs/voices), [Voice Selection Params](https://cloud.google.com/python/docs/reference/texttospeech/latest/google.cloud.texttospeech_v1.types.VoiceSelectionParams), and [Audio Config](https://cloud.google.com/python/docs/reference/texttospeech/latest/google.cloud.texttospeech_v1.types.AudioConfig) for more detailed information on the individual settings.

The required settings are `voice_id`, `language`, `region`, and `type`. All other settings will default to their underlying Google defaults.

Example:

```json
{
    "voice_id": "D",
    "language": "en",
    "region": "GB",
    "type": "Wavenet",
    "speaking_rate": null,
    "pitch": null,
    "volume_gain_db": null,
    "sample_rate_hertz": null,
    "effects_profile_id": null
}
```

### ElevenLabs

See the ElevenLabs documentation for [Voice Lab](https://elevenlabs.io/docs/voicelab/overview), [Models](https://elevenlabs.io/docs/speech-synthesis/models), and [Voice Settings](https://elevenlabs.io/docs/speech-synthesis/voice-settings) for more detailed information on the individual settings.

The only required setting is `voice_id`. All other settings will default to the underlying ElevenLabs defaults for the selected voice.

Example:

```json
{
    "voice_id": "EXAVITQu4vr4xnSDxMaL",
    "model": null,
    "stability": null,
    "similarity_boost": null,
    "style": null,
    "use_speaker_boost": null
}
```

# Manifest

> “If I ever meet myself, I'll hit myself so hard I won't know what's hit me.”

A manifest JSON file is created during the encoding process and can be used as the inputfile instead of a text file. If a manifest file is used, the fragment audio files to be re-encoded can be specified with the `--manifest-indexes` argument.

For example, consider this simple text file (`towel.txt`):

```text
Don't forget your towel.
And always know where it is.
```

The file is encoded with this command:

```bash
$ zaphodvox --encoder=google --voice-id=A --encode --copy towel.txt
```

Three files will be created in the current working directory: the two fragment audio files (`towel-00000.wav` and `towel-00001.wav`) and the manifest file (`towel-manifest.json`).

Here are the contents of `towel-manifest.json`:

```json
"fragments":
[
    {
        "text": "Don't forget your towel.",
        "filename": "towel-00000.wav",
        "voice":
        {
            "voice_id": "A",
            "language": "en",
            "region": "US",
            "type": "Wavenet"
        },
        "silence_duration": null,
        "encoder": "google",
        "audio_format": "linear16"
    },
    {
        "text": "And always know where it is.",
        "filename": "towel-00001.wav",
        "voice":
        {
            "voice_id": "A",
            "language": "en",
            "region": "US",
            "type": "Wavenet"
        },
        "silence_duration": null,
        "encoder": "google",
        "audio_format": "linear16"
    }
]
```

Note that the fragment `filename`s are relative to the manifest file's location.

Changes can be made to fragment `text`, `filename`, or `voice` items and the modified manifest file can be used to re-encode only the changes by specifying which fragment indexes to encode.

For example, if the second fragment's `text` field is modified to remove the initial "And", this command will re-encode only the second fragment audio file in place (i.e. `towel-00001.wav`):

```bash
$ zaphodvox --encoder=google --encode --manifest-indexes=1 towel-manifest.json
```

The `--concat` argument can also be added when using a manifest file as input. In this case, an attempt will be made to concatenate both the unmodified and newly encoded fragment audio files into one. If any of the files specified in the manifest is missing, the concatenation will fail.

A manifest plan can be created from a text file using the `--plan` argument:

```bash
$ zaphodvox --encoder=google --voice-id=A --plan gone-bananas.txt
```

The above command will write the manifest plan to `gone-bananas-plan.json` without doing any encoding. It can be reviewed and edited before being used as input to the command with the `--encode` argument.

By default, each line of the text file is encoded into its own audio fragment. If the `--max-chars` argument is provided when generating a plan manifest or encoding a text file, the planning process will attempt to combine multiple lines of text per audio fragment, up to `max-chars` characters. Larger fragments often encode with better results.
