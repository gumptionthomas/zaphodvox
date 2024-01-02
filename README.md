The `zaphodvox` python package provides a command-line interface for encoding a text file into synthetic speech audio using either the [Google Text-to-Speech API](https://cloud.google.com/text-to-speech/docs) or the [ElevenLabs Speech Synthesis API](https://elevenlabs.io/docs).

It can be run from the command-line or imported as a python package for programmatic integration.

# Installation

> "He was clearly a man of many qualities, even if they were mostly bad ones."

```bash
$ pip install zaphodvox
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

An example text file (`gone-bananas.txt`):

```text
This is the first line of text.
This is the next line. By default, each line of text is sent to the API individually.
This is the last line. And this is a sentence that is split
between lines. Ideally, these parts of the sentence would be on the same line.
```

```bash
$ zaphodvox --encoder=google --voice-id=A --encode gone-bananas.txt
```

Running the above command will encode the text file using the [Google Text-to-Speech API](https://cloud.google.com/text-to-speech/docs) with the `en-US-Wavenet-A` voice. This will result in the following audio files being created in the working directory (one file for each line of text):

```console
gone-bananas-00000.wav ["This is the first line..."]
gone-bananas-00001.wav ["This is the next line. By default..."]
gone-bananas-00002.wav ["This is the last line. And this is..."]
gone-bananas-00003.wav ["between lines. Ideally, these..."]
```

If you want the individual audio files combined into one, you can add the `--concat` argument:

```bash
$ zaphodvox --encoder=google --voice-id=A --encode --concat gone-bananas.txt
```

Now only a single file, `gone-bananas.wav`, will be created in the working directory.

Note that there isn't much silence between individual lines of a text file. To add a delay between lines, we simply need to add an extra newline between each line of text. The easiest way to do this is to use the `--clean` option:

```bash
$ zaphodvox --clean gone-bananas.txt
```

This command will convert the text file to plain text and attempt to add an extra newline between paragraphs as well as combine sentences that have been split between adjacent lines. It will output the newly "cleaned" text file as `gone-bananas-cleaned.txt`:

```text
This is the first line of text. It should probably be a paragraph.

This is the next line. By default, each line of text is sent to the API individually.

This is the last line. And this is a sentence that is split between lines. Ideally, these parts of the sentence would be on the same line.
```

We can now encode this new file:

```bash
$ zaphodvox --encoder=google --voice-id=A --encode --concat gone-bananas-cleaned.txt
```

Notice that there's 500ms of silence (the default) generated for each empty newline and that the last sentence is no longer split between lines.

We can skip a step and combine `--encode` and `--clean` into a single command:

```bash
$ zaphodvox --encoder=google --voice-id=A --clean --encode --concat gone-bananas.txt
```

The text file will be cleaned before being encoded and concatenated into `gone-bananas.wav`. The cleaned text file (i.e. `gone-bananas-cleaned.txt`) will still be created in the working directory so you can verify the actual text that was encoded.

# Voice Configurations

> "I'm so great even I get tongue-tied talking to myself."

Multiple voice configurations can be defined in a JSON file and loaded via the `--voices` argument.

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

If a `--voices` JSON file is used, inline `ZVOX: [name]` tags in the `textfile` can specify the voice(s) to be used.

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
$ zaphodvox --voices=voices.json --encoder=google --encode heart-of-gold.txt
```

The above command will result in the following audio files to be created in the working directory:

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
