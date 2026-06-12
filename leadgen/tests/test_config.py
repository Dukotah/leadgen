"""
Pure (no-network) tests for the config-file loader: TOML parsing, missing-file
handling, malformed-TOML errors, find_config discovery, and merge_config
CLI-precedence / list+dict merging.
Run:  python leadgen/tests/test_config.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from leadgen.config import load_config, find_config, merge_config, DEFAULT_FILENAME


def _write_tmp(text: str, suffix: str = ".toml") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


SAMPLE = """
default_vertical = "web_design"
default_market = "austin_tx"
sources = ["overture", "osm"]
limit = 200
enrich = true
enrich_cap = 150
out = "austin_web"

[config]
socrata_datasets = ["https://data.example.gov/resource/a.json"]
npi_taxonomies = ["Dentist"]

[config.weights]
no_ssl = 25
old_site = 15
"""


# ── load_config ────────────────────────────────────────────────────────────

def test_load_parses_scalars_and_lists():
    path = _write_tmp(SAMPLE)
    try:
        cfg = load_config(path)
    finally:
        os.remove(path)
    assert cfg["default_vertical"] == "web_design"
    assert cfg["default_market"] == "austin_tx"
    assert cfg["sources"] == ["overture", "osm"]
    assert cfg["limit"] == 200
    assert cfg["enrich"] is True
    assert cfg["enrich_cap"] == 150
    assert cfg["out"] == "austin_web"


def test_load_parses_nested_config_table():
    path = _write_tmp(SAMPLE)
    try:
        cfg = load_config(path)
    finally:
        os.remove(path)
    c = cfg["config"]
    assert c["socrata_datasets"] == ["https://data.example.gov/resource/a.json"]
    assert c["npi_taxonomies"] == ["Dentist"]
    assert c["weights"] == {"no_ssl": 25, "old_site": 15}


def test_load_missing_file_returns_empty_dict():
    assert load_config("this_file_does_not_exist_12345.toml") == {}
    assert load_config("") == {}


def test_load_malformed_toml_raises_valueerror():
    path = _write_tmp("this is = = not valid toml [[[")
    try:
        raised = False
        try:
            load_config(path)
        except ValueError as e:
            raised = True
            assert "malformed TOML" in str(e)
        assert raised, "expected ValueError on malformed TOML"
    finally:
        os.remove(path)


# ── find_config ────────────────────────────────────────────────────────────

def test_find_config_in_start_dir():
    d = tempfile.mkdtemp()
    p = os.path.join(d, DEFAULT_FILENAME)
    with open(p, "w", encoding="utf-8") as f:
        f.write("limit = 1\n")
    try:
        found = find_config(d)
        assert found is not None
        assert os.path.abspath(found) == os.path.abspath(p)
    finally:
        os.remove(p)
        os.rmdir(d)


def test_find_config_missing_returns_none_no_raise():
    d = tempfile.mkdtemp()
    try:
        # No leadgen.toml here; home fallback also (almost certainly) absent.
        assert find_config(d) is None or find_config(d).endswith(DEFAULT_FILENAME)
    finally:
        os.rmdir(d)


# ── merge_config ───────────────────────────────────────────────────────────

def test_merge_cli_wins_over_file():
    file_cfg = {"default_vertical": "web_design", "limit": 200, "enrich": True}
    cli = {"default_vertical": "seo_audit", "limit": 50}
    out = merge_config(cli, file_cfg)
    assert out["default_vertical"] == "seo_audit"  # CLI wins
    assert out["limit"] == 50                       # CLI wins
    assert out["enrich"] is True                    # untouched from file


def test_merge_none_cli_falls_through_to_file():
    file_cfg = {"limit": 200, "out": "austin_web"}
    cli = {"limit": None, "out": None, "default_market": "boulder_co"}
    out = merge_config(cli, file_cfg)
    assert out["limit"] == 200            # None CLI did not clobber
    assert out["out"] == "austin_web"
    assert out["default_market"] == "boulder_co"


def test_merge_lists_merge_without_dupes():
    file_cfg = {"sources": ["overture", "osm"]}
    cli = {"sources": ["osm", "socrata"]}
    out = merge_config(cli, file_cfg)
    assert out["sources"] == ["overture", "osm", "socrata"]


def test_merge_config_table_lists_and_weights():
    file_cfg = {"config": {
        "socrata_datasets": ["a"],
        "weights": {"no_ssl": 25, "old_site": 15},
    }}
    cli = {"config": {
        "socrata_datasets": ["b"],
        "weights": {"old_site": 99},
    }}
    out = merge_config(cli, file_cfg)
    c = out["config"]
    assert c["socrata_datasets"] == ["a", "b"]              # lists concatenate
    assert c["weights"] == {"no_ssl": 25, "old_site": 99}    # CLI weight wins


def test_merge_does_not_mutate_inputs():
    file_cfg = {"sources": ["overture"], "config": {"npi_taxonomies": ["Dentist"]}}
    cli = {"sources": ["osm"]}
    merge_config(cli, file_cfg)
    assert file_cfg["sources"] == ["overture"]
    assert file_cfg["config"]["npi_taxonomies"] == ["Dentist"]
    assert cli["sources"] == ["osm"]


def test_merge_empty_inputs():
    assert merge_config({}, {}) == {}
    assert merge_config(None, None) == {}


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
