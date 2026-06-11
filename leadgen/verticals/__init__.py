"""
Built-in verticals. Importing this package registers them all.
Add a new use case by dropping a module here that calls leadgen.register(...).
"""
from . import web_design     # noqa: F401  (registers "web_design")
from . import seo_audit      # noqa: F401  (registers "seo_audit")
from . import social_only    # noqa: F401  (registers "social_only")
