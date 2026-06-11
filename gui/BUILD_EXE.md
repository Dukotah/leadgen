# Building the Windows .exe

The Lead Engine can ship as a single double-click `LeadEngine.exe` — no Python,
no setup. There are two ways to produce it.

## Option A — GitHub Actions (no Windows machine needed) ✅ recommended

A workflow at `.github/workflows/build-exe.yml` builds the `.exe` on a real
Windows runner, smoke-tests that it boots, and uploads it.

**To get an .exe:**
1. Push this branch to GitHub.
2. Go to the repo's **Actions** tab → **Build Windows EXE** → **Run workflow**.
3. When it finishes (~5 min), open the run and download the **LeadEngine-windows**
   artifact. Inside is `LeadEngine.exe`.

**To cut a versioned release** (also attaches the .exe to a GitHub Release):
```bash
git tag v1.0.0
git push origin v1.0.0
```
The workflow builds and attaches `LeadEngine.exe` to the `v1.0.0` release, so you
can send your mom a permanent download link.

## Option B — build locally on a Windows PC

Requires Python 3.10+ installed and on PATH.
```
double-click gui\build.bat
```
It installs dependencies, runs the self-tests, and produces `dist\LeadEngine.exe`.
Equivalently, by hand:
```
pip install -r gui/requirements.txt pyinstaller
pyinstaller --clean --noconfirm gui/LeadEngine.spec
```

## What's in the build

- **Entry point:** `gui/launch.py` — starts the Flask server on a free port and
  opens a native window (or the default browser if pywebview isn't available).
- **Spec:** `gui/LeadEngine.spec` — bundles the whole `leadgen` engine, all
  verticals (force-included because they register via import side-effects),
  `duckdb`/`openpyxl`/`requests`, and the demo fixtures. Produces one
  console-less file.
- **Verified:** the spec has been built and the resulting binary boot-tested
  (serves the UI and completes a demo run) on Linux; the Windows job in CI runs
  the same spec and smoke-tests the `.exe` before uploading.

## Notes

- First launch may take a few seconds while the one-file bundle unpacks.
- Windows SmartScreen may warn on an unsigned .exe the first time — "More info →
  Run anyway". Code-signing is out of scope here; the CI build is reproducible
  from source if she'd rather build it herself.
- The `.exe` still needs internet to scrape live data, but **Demo mode works
  fully offline** — a good first thing to click.
