# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Lead Engine desktop app.

Build (on Windows):  pyinstaller gui/LeadEngine.spec
Output:              dist/LeadEngine.exe  (one self-contained file)

Notes
-----
- The verticals in leadgen/verticals are imported for their REGISTER side effect,
  so PyInstaller's static analysis can miss them — they're forced via hiddenimports.
- duckdb is heavy and only needed for the Overture source; it's included so the
  bundled app supports both sources out of the box.
"""
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Resolve the repo root from this spec's location (gui/ → repo root).
REPO = os.path.dirname(os.path.abspath(SPECPATH))  # noqa: F821 (SPECPATH injected)
GUI = os.path.join(REPO, "gui")

def _safe_submodules(pkg):
    """collect_submodules but never fail the whole build if a package is missing
    or imports badly on the build host (e.g. an optional native backend)."""
    try:
        return collect_submodules(pkg)
    except Exception as e:
        print(f"[spec] skipping submodules for {pkg!r}: {e}")
        return []


hiddenimports = []
hiddenimports += _safe_submodules("leadgen")            # all engine modules
hiddenimports += _safe_submodules("leadgen.verticals")  # registered side-effects
hiddenimports += ["duckdb", "openpyxl", "requests"]
# pywebview's platform backends are optional; include only if importable here.
hiddenimports += _safe_submodules("webview")

# Demo fixtures live in leadgen/tests/fixtures.py (a .py module), so they're
# already pulled in via collect_submodules above — no separate data files needed.
# The app ships as a tool only: it bundles no lead data.
datas = []

block_cipher = None

a = Analysis(
    [os.path.join(GUI, "launch.py")],
    pathex=[REPO, GUI],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 'cryptography' is excluded: the app's HTTP(S) uses stdlib ssl, not this
    # package, and pulling it in triggers a hook that can crash on some build
    # hosts with a broken native binding. Safe to drop for our use.
    excludes=["tkinter", "matplotlib", "numpy.tests", "pytest", "cryptography"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="LeadEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window on double-click
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(GUI, "icon.ico") if os.path.exists(os.path.join(GUI, "icon.ico")) else None,
)
