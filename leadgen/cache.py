"""
On-disk TTL cache for HTTP GET responses — used during development so we don't
re-fetch the same URL on every run. Cache I/O never raises: any failure degrades
to a cache miss (or a silent no-op write), so the caller always falls back to a
real fetch.

The clock is injectable (`now` callable) so tests advance time without sleeping.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from typing import Callable, Optional

# Default time-to-live for a cached entry: 24 hours.
DEFAULT_TTL = 24 * 60 * 60


def default_dir() -> str:
    """The default cache directory: 'leadgen_cache' under the system temp dir."""
    return os.path.join(tempfile.gettempdir(), "leadgen_cache")


def _hash_key(key: str) -> str:
    return hashlib.sha256((key or "").encode("utf-8", "replace")).hexdigest()


class DiskCache:
    """A tiny JSON-on-disk TTL cache keyed by a hash of the key string.

    Each entry is one file containing {"value": str, "ts": float}. Reads of a
    missing/corrupt/expired file return None; all I/O errors are swallowed.
    """

    def __init__(self, cache_dir: Optional[str] = None,
                 ttl: float = DEFAULT_TTL,
                 now: Callable[[], float] = time.time):
        self.cache_dir = cache_dir or default_dir()
        self.ttl = ttl
        self.now = now

    # ── paths ────────────────────────────────────────────────────────────────
    def path(self) -> str:
        """The cache directory path."""
        return self.cache_dir

    def path_for(self, key: str) -> str:
        """Absolute path of the file that backs `key`."""
        return os.path.join(self.cache_dir, _hash_key(key) + ".json")

    def _ensure_dir(self) -> bool:
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            return True
        except Exception:
            return False

    # ── core ─────────────────────────────────────────────────────────────────
    def get(self, key: str, ttl: Optional[float] = None) -> Optional[str]:
        """Return the cached value for `key`, or None if missing/expired/corrupt."""
        ttl = self.ttl if ttl is None else ttl
        try:
            with open(self.path_for(key), "r", encoding="utf-8") as f:
                entry = json.load(f)
            ts = float(entry["ts"])
            value = entry["value"]
        except Exception:
            return None
        if not isinstance(value, str):
            return None
        if ttl is not None and ttl >= 0 and (self.now() - ts) > ttl:
            return None
        return value

    def set(self, key: str, value: str) -> None:
        """Store `value` under `key`. Silently no-ops on any I/O error."""
        if not self._ensure_dir():
            return
        target = self.path_for(key)
        entry = {"value": value, "ts": self.now()}
        try:
            # Write to a temp file in the same dir, then atomically replace.
            fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(entry, f)
                os.replace(tmp, target)
            except Exception:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass
        except Exception:
            return

    def cached_get(self, url: str, fetch_fn: Callable[[str], Optional[str]],
                   ttl: Optional[float] = None) -> Optional[str]:
        """Return cached text for `url`, else call `fetch_fn(url)`, cache, return it.

        Only non-None fetch results are cached. The clock used for freshness is
        this cache's `now`.
        """
        hit = self.get(url, ttl=ttl)
        if hit is not None:
            return hit
        value = fetch_fn(url)
        if value is not None:
            self.set(url, value)
        return value

    # ── maintenance ──────────────────────────────────────────────────────────
    def clear(self) -> None:
        """Delete every entry in the cache dir. Never raises."""
        try:
            names = os.listdir(self.cache_dir)
        except Exception:
            return
        for name in names:
            if not name.endswith(".json"):
                continue
            try:
                os.unlink(os.path.join(self.cache_dir, name))
            except Exception:
                pass


# ── module-level convenience (mirrors DiskCache methods) ──────────────────────

def cached_get(url: str, fetch_fn: Callable[[str], Optional[str]],
               ttl: float = DEFAULT_TTL,
               clock: Callable[[], float] = time.time,
               cache_dir: Optional[str] = None) -> Optional[str]:
    """One-shot convenience wrapper around DiskCache.cached_get."""
    cache = DiskCache(cache_dir=cache_dir, ttl=ttl, now=clock)
    return cache.cached_get(url, fetch_fn, ttl=ttl)
