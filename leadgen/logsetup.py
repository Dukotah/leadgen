"""
Logging helper for the leadgen CLI.

`make_logger` returns a callable suitable for passing as run_pipeline(log=...).
It honors --quiet / --verbose verbosity and can tee progress lines to a file.
"""
from __future__ import annotations

from typing import Callable


def make_logger(quiet: bool = False, verbose: bool = False,
                log_file: str | None = None) -> Callable[[str], None]:
    """Build a log callback.

    quiet:   suppress the per-step progress lines printed to stdout/stderr.
    verbose: print everything (default behavior is already verbose; this is
             accepted for explicitness and future-proofing).
    log_file: if set, also tee every line to this file (append mode, utf-8).

    The returned callable always writes to the log file (when given) even in
    quiet mode, so a quiet console run can still leave a full trace on disk.
    """
    fh = None
    if log_file:
        # Line-buffered append so the file stays useful if the run is killed.
        fh = open(log_file, "a", encoding="utf-8", errors="replace", buffering=1)

    def log(msg: str = "") -> None:
        line = str(msg)
        if fh is not None:
            try:
                fh.write(line + "\n")
            except Exception:
                pass
        if not quiet:
            print(line)

    # Expose the file handle so callers can close it if they want to.
    log.log_file_handle = fh  # type: ignore[attr-defined]
    return log
