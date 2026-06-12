"""
Pure (no-network) tests for the on-disk TTL cache: set/get round-trip, TTL
expiry via an injected clock, cached_get fetch-once-within-ttl behaviour, and
graceful handling of corrupt/missing cache files.
Run:  python leadgen/tests/test_cache.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.cache import DiskCache, cached_get, DEFAULT_TTL


class _Clock:
    """An injectable clock that starts at t and advances on demand."""

    def __init__(self, t: float = 1000.0):
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ── set / get round-trip ──────────────────────────────────────────────────────

def test_set_get_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        c = DiskCache(cache_dir=d, ttl=100, now=_Clock())
        c.set("http://x.test/a", "hello world")
        assert c.get("http://x.test/a") == "hello world"


def test_get_missing_returns_none():
    with tempfile.TemporaryDirectory() as d:
        c = DiskCache(cache_dir=d, ttl=100, now=_Clock())
        assert c.get("http://x.test/never") is None


# ── TTL expiry via injected clock ─────────────────────────────────────────────

def test_expiry_via_clock():
    with tempfile.TemporaryDirectory() as d:
        clk = _Clock(0.0)
        c = DiskCache(cache_dir=d, ttl=10, now=clk)
        c.set("k", "v")
        clk.advance(5)            # still fresh
        assert c.get("k") == "v"
        clk.advance(6)            # now 11s > ttl 10
        assert c.get("k") is None


def test_per_call_ttl_override():
    with tempfile.TemporaryDirectory() as d:
        clk = _Clock(0.0)
        c = DiskCache(cache_dir=d, ttl=DEFAULT_TTL, now=clk)
        c.set("k", "v")
        clk.advance(50)
        assert c.get("k", ttl=100) == "v"   # within override
        assert c.get("k", ttl=10) is None   # expired under override


# ── cached_get fetch-once semantics ───────────────────────────────────────────

def test_cached_get_fetches_once_within_ttl():
    with tempfile.TemporaryDirectory() as d:
        clk = _Clock(0.0)
        c = DiskCache(cache_dir=d, ttl=100, now=clk)
        calls = {"n": 0}

        def fetch(url):
            calls["n"] += 1
            return "body-" + url

        assert c.cached_get("http://x.test/p", fetch) == "body-http://x.test/p"
        assert c.cached_get("http://x.test/p", fetch) == "body-http://x.test/p"
        assert calls["n"] == 1                       # second call served from cache

        clk.advance(101)                             # expire it
        assert c.cached_get("http://x.test/p", fetch) == "body-http://x.test/p"
        assert calls["n"] == 2                        # re-fetched after expiry


def test_cached_get_does_not_cache_none():
    with tempfile.TemporaryDirectory() as d:
        c = DiskCache(cache_dir=d, ttl=100, now=_Clock())
        calls = {"n": 0}

        def fetch(url):
            calls["n"] += 1
            return None

        assert c.cached_get("http://x.test/q", fetch) is None
        assert c.cached_get("http://x.test/q", fetch) is None
        assert calls["n"] == 2          # None results are not cached, so we retry


def test_module_cached_get_with_clock():
    with tempfile.TemporaryDirectory() as d:
        clk = _Clock(0.0)
        calls = {"n": 0}

        def fetch(url):
            calls["n"] += 1
            return "X"

        a = cached_get("http://x.test/m", fetch, ttl=100, clock=clk, cache_dir=d)
        b = cached_get("http://x.test/m", fetch, ttl=100, clock=clk, cache_dir=d)
        assert a == "X" and b == "X"
        assert calls["n"] == 1


# ── corrupt / missing handled gracefully ──────────────────────────────────────

def test_corrupt_file_returns_none():
    with tempfile.TemporaryDirectory() as d:
        c = DiskCache(cache_dir=d, ttl=100, now=_Clock())
        c.set("k", "v")
        with open(c.path_for("k"), "w", encoding="utf-8") as f:
            f.write("{not valid json")
        assert c.get("k") is None       # corrupt entry -> miss, no exception


def test_clear_removes_entries():
    with tempfile.TemporaryDirectory() as d:
        c = DiskCache(cache_dir=d, ttl=100, now=_Clock())
        c.set("a", "1")
        c.set("b", "2")
        c.clear()
        assert c.get("a") is None and c.get("b") is None


def test_set_on_unwritable_dir_does_not_raise():
    # A path whose parent is a file, not a dir — makedirs fails, set() no-ops.
    with tempfile.TemporaryDirectory() as d:
        blocker = os.path.join(d, "afile")
        with open(blocker, "w", encoding="utf-8") as f:
            f.write("x")
        c = DiskCache(cache_dir=os.path.join(blocker, "sub"), ttl=100, now=_Clock())
        c.set("k", "v")                 # must not raise
        assert c.get("k") is None


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
