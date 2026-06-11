# Building the desktop app (Windows / macOS / Linux)

The Lead Engine can ship as a single double-click binary — no Python, no setup:

- **Windows** → `LeadEngine-windows.exe`
- **macOS** → `LeadEngine-macos`
- **Linux** → `LeadEngine-linux`

There are two ways to produce them.

## Option A — GitHub Actions (no build machine needed) ✅ recommended

The workflow at `.github/workflows/build.yml` builds all three on real Windows,
macOS, and Linux runners, smoke-tests that each one boots and serves the UI, and
uploads them.

**To get the binaries:**
1. Push the repo to GitHub.
2. Go to the repo's **Actions** tab → **Build desktop apps** → **Run workflow**.
3. When it finishes (~5 min), open the run and download the per-OS artifacts.

**To cut a versioned release** (also attaches all three binaries to a public
GitHub Release, so you can hand people a permanent download link):
```bash
git tag v1.0.0
git push origin v1.0.0
```
Or run the workflow manually and fill in the **release_tag** input.

## Option B — build locally

Requires Python 3.10+ on PATH. From the repo root:
```bash
pip install -r gui/requirements.txt pyinstaller
pyinstaller --clean --noconfirm gui/LeadEngine.spec
```
The binary lands in `dist/` (`LeadEngine.exe` on Windows, `LeadEngine` on
macOS/Linux). On Windows you can also just double-click `gui\build.bat`, which
installs deps, runs the self-tests, and builds.

PyInstaller only builds for the OS it runs on, so build on each platform you want
to ship (that's exactly what Option A automates).

## What's in the build

- **Entry point:** `gui/launch.py` — starts the Flask server on a free port and
  opens a native window (or the default browser if a native webview isn't
  available, e.g. on a headless Linux box).
- **Spec:** `gui/LeadEngine.spec` — bundles the whole `leadgen` engine, all
  registered verticals (force-included because they register via import
  side-effects), `duckdb`/`openpyxl`/`requests`, and the demo fixtures. It bundles
  **no lead data** — output is generated per run.

## Notes

- First launch may take a few seconds while the one-file bundle unpacks.
- Unsigned binaries trip OS gatekeepers the first time: Windows SmartScreen
  ("More info → Run anyway") and macOS Gatekeeper (right-click → Open). Code
  signing is out of scope here; the CI build is reproducible from source.
- The binary still needs internet to scrape live data, but **Demo mode (“Try a
  sample”) works fully offline** — a good first thing to click.
