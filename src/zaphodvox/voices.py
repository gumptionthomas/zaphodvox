from typing import Any

from pydantic import ValidationError

from zaphodvox.qwen.voice import QwenVoice  # noqa: F401
from zaphodvox.voice import Voice


def parse_voice(data: Any) -> Voice:
    """Deserializes a raw voice mapping into the right `Voice` subclass.

    A manifest or voices file records the encoder each voice belongs to, and that
    tag decides the subclass. A file written before the tag existed has none, and
    is read as a `QwenVoice` -- which is what it was, since Qwen was the only
    backend at the time.

    The subclasses have to be imported to be found (the same rule as encoders --
    see `main.encoder_voice()`), which is why this module imports every one of
    them.

    Args:
        data: The raw voice mapping, or a `Voice` (passed through unchanged).

    Returns:
        The `Voice` subclass instance.

    Raises:
        ValueError: If the mapping is not a valid voice for any encoder.
    """
    if isinstance(data, Voice) or not isinstance(data, dict):
        return data
    errors = []
    for voice_class in Voice.__subclasses__():
        try:
            return voice_class.model_validate(data)
        except ValidationError as e:
            errors.append(f'{voice_class.__name__}: {e.error_count()} error(s)')
    raise ValueError(
        f'Not a valid voice for any encoder ({"; ".join(errors)}): {data}'
    )
