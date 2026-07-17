import os
from typing import Optional, Union

CONNECT_TIMEOUT = 5.0
"""The seconds to wait for a server to accept a connection.

Short on purpose: every server `zaphodvox` talks to is local, and a local peer
either answers the SYN immediately or is not there.
"""

DEFAULT_READ_TIMEOUT = 600.0
"""The seconds to wait for a server's response, by default.

Generous on purpose. This is not sized for steady-state generation (a couple of
seconds), but for the slowest *legitimate* response: a server lazy-loads its
clone and design models on first use, and that includes a `torch.compile`
warmup. Time that out and the retry aborts real work and then fails the job --
which is worse than the hang this timeout exists to prevent.
"""

TIMEOUT_ENV = 'ZAPHODVOX_TIMEOUT'
"""The environment variable holding the default read timeout."""


def request_timeout(
    read: Optional[float]
) -> Optional[tuple[float, float]]:
    """The `timeout` to pass to a `requests` call.

    Every HTTP call needs one. Left off, `requests` defaults to `timeout=None` --
    block forever -- so a peer that vanishes without closing its connection (a
    box that loses its network stack sends no FIN and no RST, it just goes
    silent) wedges the job for good. Worse, the `tenacity` retry wrapped around
    every one of these calls cannot help: it retries on exceptions, and a hang
    raises nothing. A timeout is what turns the hang into a `ReadTimeout` the
    retry can actually catch.

    Args:
        read: The seconds to wait for a response. `None` uses
            `DEFAULT_READ_TIMEOUT`; `0` waits forever.

    Returns:
        A `(connect, read)` tuple, or `None` to wait forever.

    Raises:
        ValueError: If `read` is negative.
    """
    if read is None:
        read = DEFAULT_READ_TIMEOUT
    if read < 0:
        # `requests` would take this and complain only once the request is
        # under way -- from inside the retry, so a mistyped "-5" would be five
        # confusing failures partway through a book instead of one complaint.
        raise ValueError(
            f'A timeout cannot be negative (got {read:g}). Pass the seconds to '
            'wait for a response, or 0 to wait forever.'
        )
    if not read:
        return None
    return (CONNECT_TIMEOUT, read)


def default_timeout() -> Union[str, float]:
    """The default read timeout, from the environment.

    Returns:
        The read timeout in seconds (a string when it comes from the
            environment, for `argparse` to convert and complain about).
    """
    return os.environ.get(TIMEOUT_ENV, DEFAULT_READ_TIMEOUT)
