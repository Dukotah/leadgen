"""
Built-in verticals. Importing this package registers them all.
Add a new use case by dropping a module here that calls leadgen.register(...).
"""
from . import web_design       # noqa: F401  (registers "web_design")
from . import seo_audit        # noqa: F401  (registers "seo_audit")
from . import social_only      # noqa: F401  (registers "social_only")
from . import restaurants      # noqa: F401  (registers "restaurants")
from . import home_services    # noqa: F401  (registers "home_services")
from . import no_ssl           # noqa: F401  (registers "no_ssl")
from . import healthcare_web   # noqa: F401  (registers "healthcare_web")
from . import directory_only   # noqa: F401  (registers "directory_only")
