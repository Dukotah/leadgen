"""
Networking reliability + concurrency helpers (stdlib + requests only).

These are small, dependency-light primitives the collect step can lean on:
  - retry():           exponential-backoff wrapper around any zero-arg callable.
  - RateLimiter:       thread-safe per-host pacing (inject a clock for tests).
  - parallel_collect(): run many record-returning thunks concurrently, isolate
                        failures, and preserve input order.

They mirror the existing retry/backoff style in sources._overpass_query (a small
fixed number of attempts, sleep between them) without changing it.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor


def retry(fn, tries: int = 3, backoff: float = 1.0, exc=(Exception,)):
    """Call fn() and retry on failure with exponential backoff.

    Retries up to `tries` total attempts. Between attempt n and n+1 it sleeps
    backoff * 2**n seconds (so backoff, 2*backoff, 4*backoff, …). Only exceptions
    matching `exc` are retried; anything else propagates immediately. After the
    last attempt the final error is re-raised.

    Returns fn()'s result on the first success.
    """
    if tries < 1:
        raise ValueError("tries must be >= 1")
    last: BaseException | None = None
    for attempt in range(tries):
        try:
            return fn()
        except exc as e:
            last = e
            if attempt == tries - 1:
                break
            time.sleep(backoff * (2 ** attempt))
    assert last is not None
    raise last


class RateLimiter:
    """Keep per-host calls spaced at least `min_interval_s` apart.

    Thread-safe: a single lock serializes the bookkeeping AND the sleep so two
    threads hitting the same host can't both decide it's their turn. The clock is
    injectable (`now`, a monotonic-style callable, plus `sleep`) so tests can
    drive it deterministically without real time.
    """

    def __init__(self, min_interval_s: float, *, now=time.monotonic, sleep=time.sleep):
        self.min_interval_s = float(min_interval_s)
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed: dict[str, float] = {}

    def wait(self, host: str) -> None:
        """Block until at least min_interval_s has elapsed since this host's last call."""
        with self._lock:
            now = self._now()
            allowed_at = self._next_allowed.get(host, now)
            if allowed_at > now:
                self._sleep(allowed_at - now)
                now = allowed_at
            self._next_allowed[host] = now + self.min_interval_s


def parallel_collect(thunks: list, workers: int = 6) -> list:
    """Run zero-arg callables concurrently and concatenate their (list) results.

    Each thunk must return a list of records. A thunk that raises contributes []
    instead of killing the batch. Results are concatenated in input order
    regardless of completion order. An empty `thunks` returns [].
    """
    thunks = list(thunks)
    if not thunks:
        return []
    results: list[list] = [[] for _ in thunks]

    def _call(thunk):
        try:
            out = thunk()
            return out if out is not None else []
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for i, out in enumerate(ex.map(_call, thunks)):
            results[i] = out

    flat: list = []
    for part in results:
        flat.extend(part)
    return flat
