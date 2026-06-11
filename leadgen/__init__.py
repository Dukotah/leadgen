"""
leadgen — a universal lead-generation engine.

One pipeline (collect → enrich → score → suppress → export) driven by swappable
*verticals*. A vertical defines WHAT you're prospecting for; the engine handles
HOW. See README.md and verticals/ for examples.

    from leadgen import run_pipeline, get_vertical
    leads = run_pipeline(get_vertical("web_design"), market="austin_tx")
"""
from .vertical import Vertical, register, get_vertical, all_verticals
from .pipeline import run_pipeline

# Importing the verticals package registers the built-in verticals as a side effect.
from . import verticals as _verticals  # noqa: F401

__all__ = [
    "Vertical", "register", "get_vertical", "all_verticals", "run_pipeline",
]
__version__ = "1.0.0"
