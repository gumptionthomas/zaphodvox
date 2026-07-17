from zaphodvox.http import (
    CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    request_timeout,
)


class TestRequestTimeout():
    def test_none_is_the_default_read_timeout(self):
        assert request_timeout(None) == (CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT)

    def test_a_read_timeout_is_paired_with_the_connect_timeout(self):
        # Connecting to a local server either happens at once or does not
        # happen; only the response is worth waiting on.
        assert request_timeout(30.0) == (CONNECT_TIMEOUT, 30.0)

    def test_zero_disables_the_timeout(self):
        # `requests` reads `None` as "block forever", which is the escape hatch
        # for a server so slow that any number would be a guess.
        assert request_timeout(0) is None

    def test_the_default_read_timeout_outlasts_a_lazy_model_load(self):
        # The trap this whole thing has to avoid: a first request to a clone or
        # design model loads it and runs a torch.compile warmup, which takes far
        # longer than the ~2s of steady-state generation. Time it out and the
        # retry aborts legitimate work five times over and then fails the job.
        assert DEFAULT_READ_TIMEOUT >= 300.0
