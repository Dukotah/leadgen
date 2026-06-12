"""
Config-file loader for the lead engine.

Lets users keep their settings in a ``leadgen.toml`` file instead of typing
long CLI flag lists every run. Pure stdlib (``tomllib``, Python 3.11+); no
third-party deps and no network.

Schema (every key is optional)
------------------------------
Top-level table:

    default_vertical = "web_design"   # str — vertical key (see `leadgen --list`)
    default_market   = "austin_tx"    # str — named market or geocodable place
    sources          = ["overture", "osm"]   # list[str] — data sources
    limit            = 200            # int  — cap on businesses collected
    enrich           = true           # bool — run per-site enrichment
    enrich_cap       = 150            # int  — enrich only the top-N (cost control)
    out              = "austin_web"   # str  — output filename stem

Valid `sources` values: overture, osm, socrata, npi, foursquare, arcgis.

Per-vertical overrides live in a ``[config]`` table (shallow-merged over the
vertical's own ``config`` for the run):

    [config]
    socrata_datasets = ["https://data.austintexas.gov/resource/abcd-1234.json"]
    arcgis_layers    = ["https://services.arcgis.com/.../FeatureServer/0"]
    npi_taxonomies   = ["Dentist", "Family Medicine"]

    [config.weights]
    no_ssl   = 25
    old_site = 15

These map directly onto the keys ``pipeline.run_pipeline`` reads from the
per-run config (``socrata_datasets``, ``arcgis_layers``, ``npi_taxonomies``),
and the scoring ``weights`` blob the verticals consume.

Public API
----------
    load_config(path="leadgen.toml") -> dict
    find_config(start_dir=".")        -> str | None
    merge_config(cli_args, file_cfg)  -> dict
"""
from __future__ import annotations

import os
import tomllib

DEFAULT_FILENAME = "leadgen.toml"

# Keys that name a per-vertical config override (live under [config]); the ones
# that are lists merge by concatenation, the rest (dicts) merge key-by-key.
_CONFIG_LIST_KEYS = ("socrata_datasets", "arcgis_layers", "npi_taxonomies")


def load_config(path: str = DEFAULT_FILENAME) -> dict:
    """Parse a TOML config file and return it as a plain dict.

    Returns ``{}`` if the file does not exist (missing config is not an error).
    Raises ``ValueError`` with a clear message if the file exists but contains
    malformed TOML.
    """
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"malformed TOML in {path}: {e}") from e
    except OSError as e:
        # Treat an unreadable/vanished file the same as missing.
        return {}
    return data if isinstance(data, dict) else {}


def find_config(start_dir: str = ".") -> str | None:
    """Locate a ``leadgen.toml``.

    Looks in ``start_dir`` first, then falls back to
    ``~/.config/leadgen/leadgen.toml``. Returns the absolute path of the first
    file found, or ``None``. Never raises on a missing file.
    """
    candidates = [os.path.join(start_dir or ".", DEFAULT_FILENAME)]
    try:
        home = os.path.expanduser("~")
        candidates.append(os.path.join(home, ".config", "leadgen", DEFAULT_FILENAME))
    except Exception:
        pass
    for c in candidates:
        try:
            if os.path.isfile(c):
                return os.path.abspath(c)
        except OSError:
            continue
    return None


def _merge_config_table(cli_cfg: dict, file_cfg: dict) -> dict:
    """Merge the per-vertical ``[config]`` tables. List keys concatenate
    (file values first, then CLI), the ``weights`` dict merges key-by-key with
    CLI winning, and any other scalar key takes the CLI value when present."""
    out: dict = dict(file_cfg) if isinstance(file_cfg, dict) else {}
    cli_cfg = cli_cfg if isinstance(cli_cfg, dict) else {}

    for key in _CONFIG_LIST_KEYS:
        f_list = out.get(key)
        c_list = cli_cfg.get(key)
        if f_list or c_list:
            merged: list = []
            for item in (list(f_list or []) + list(c_list or [])):
                if item not in merged:
                    merged.append(item)
            out[key] = merged

    f_weights = out.get("weights")
    c_weights = cli_cfg.get("weights")
    if isinstance(f_weights, dict) or isinstance(c_weights, dict):
        w = dict(f_weights) if isinstance(f_weights, dict) else {}
        if isinstance(c_weights, dict):
            w.update(c_weights)
        out["weights"] = w

    handled = set(_CONFIG_LIST_KEYS) | {"weights"}
    for k, v in cli_cfg.items():
        if k in handled:
            continue
        if v is not None:
            out[k] = v
    return out


def merge_config(cli_args: dict, file_cfg: dict) -> dict:
    """Combine command-line args with a parsed config-file dict.

    CLI values win over file values. ``None`` CLI values are treated as
    "unset" and fall through to the file value, so a caller can pass the raw
    argparse namespace as a dict without clobbering file settings with
    ``None``. Lists (``sources``) and the per-vertical ``config`` table merge
    sensibly rather than being blindly overwritten.

    Returns a brand-new plain dict; neither input is mutated.
    """
    cli_args = dict(cli_args or {})
    out: dict = dict(file_cfg or {})

    # The [config] table gets its own structured merge.
    cli_table = cli_args.pop("config", None)
    file_table = out.get("config")
    if isinstance(cli_table, dict) or isinstance(file_table, dict):
        out["config"] = _merge_config_table(cli_table or {}, file_table or {})

    for k, v in cli_args.items():
        if v is None:
            continue  # unset CLI flag — keep the file value
        if isinstance(v, list) and isinstance(out.get(k), list):
            merged = list(out[k])
            for item in v:
                if item not in merged:
                    merged.append(item)
            out[k] = merged
        else:
            out[k] = v
    return out
