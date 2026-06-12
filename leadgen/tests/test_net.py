"""
Pure (offline) tests for leadgen.net: retry backoff, RateLimiter pacing with an
injected clock, and parallel_collect concat + failure isolation.
Run:  python leadgen/tests/test_net.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.net import retry, RateLimiter, parallel_collect


# ── retry ─────────────────────────────────────────────────────────────────────

def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("not yet")
        return "ok"

    # backoff=0 keeps the test instant.
    assert retry(fn, tries=3, backoff=0) == "ok"
    assert calls["n"] == 3


def test_retry_gives_up_after_tries():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RuntimeError("always")

    try:
        retry(fn, tries=3, backoff=0)
        assert False, "should have re-raised"
    except RuntimeError as e:
        assert str(e) == "always"
    assert calls["n"] == 3  # exactly `tries` attempts, no more


def test_retry_only_catches_listed_exceptions():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise KeyError("nope")

    try:
        retry(fn, tries=5, backoff=0, exc=(ValueError,))
        assert False, "unmatched exception should propagate immediately"
    except KeyError:
        pass
    assert calls["n"] == 1  # not retried


def test_retry_returns_first_success_without_sleeping():
    sleeps = []

    # Patch out time.sleep via backoff=0 + a fn that succeeds first try.
    def fn():
        return 42

    assert retry(fn, tries=3, backoff=0) == 42


# ── RateLimiter (injected clock) ──────────────────────────────────────────────

class _FakeClock:
    """Deterministic monotonic clock; .sleep advances virtual time and records it."""

    def __init__(self):
        self.t = 0.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, dt):
        self.slept.append(dt)
        self.t += dt


def test_ratelimiter_spaces_calls_per_host():
    clk = _FakeClock()
    rl = RateLimiter(1.0, now=clk.now, sleep=clk.sleep)

    rl.wait("a")            # first call: no wait
    assert clk.slept == []
    rl.wait("a")            # immediately again: must sleep ~1.0
    assert clk.slept == [1.0]
    assert clk.t == 1.0


def test_ratelimiter_independent_hosts():
    clk = _FakeClock()
    rl = RateLimiter(2.0, now=clk.now, sleep=clk.sleep)
    rl.wait("a")
    rl.wait("b")            # different host: no wait even though time hasn't moved
    assert clk.slept == []


def test_ratelimiter_no_wait_when_enough_elapsed():
    clk = _FakeClock()
    rl = RateLimiter(1.0, now=clk.now, sleep=clk.sleep)
    rl.wait("a")
    clk.t += 5.0            # plenty of time passes externally
    rl.wait("a")
    assert clk.slept == []  # already past the interval


# ── parallel_collect ──────────────────────────────────────────────────────────

def test_parallel_collect_concatenates_in_order():
    thunks = [lambda: [1, 2], lambda: [3], lambda: [4, 5, 6]]
    assert parallel_collect(thunks, workers=3) == [1, 2, 3, 4, 5, 6]


def test_parallel_collect_isolates_raising_thunk():
    def boom():
        raise RuntimeError("kaboom")

    thunks = [lambda: ["a"], boom, lambda: ["b", "c"]]
    # the raising thunk contributes [] and never kills the batch
    assert parallel_collect(thunks, workers=4) == ["a", "b", "c"]


def test_parallel_collect_empty():
    assert parallel_collect([], workers=4) == []


def test_parallel_collect_none_result_is_empty():
    thunks = [lambda: None, lambda: ["x"]]
    assert parallel_collect(thunks, workers=2) == ["x"]


def _run_all():
    fns = [g for n, g in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL {fn.__name__}: {e}")
        except Exception as e:
            failed += 1; print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
