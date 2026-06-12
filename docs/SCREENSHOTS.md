# Screenshots

This page is a placeholder for GUI screenshots and short demo GIFs. None are
committed yet — this is a contributor on-ramp describing **where** images go and
**what** to capture.

## Where images go

Put image files in **`docs/img/`** (the folder exists, with a `.gitkeep`). Keep
them reasonably small (compress PNGs; trim GIFs to a few seconds). Reference them
from this page or others with a relative path, e.g.:

```markdown
![Find-leads form](img/find-leads-form.png)
```

## What to capture

The GUI is documented in [`gui/README.md`](https://github.com/) and launches via
`cd gui && ./run.sh` (browser) or `python gui/desktop_app.py` (native window).
Good first captures:

1. **The Find-leads form** — the main screen where you pick a vertical and a
   market, optionally upload a CRM to de-dupe, and click **Find leads**. Show the
   **"Try a sample"** and **"Check my connection"** buttons too.
2. **A results table** — the tiered leads after a run (Tier A/B/C with score,
   reason, and suggested opener), plus the CSV/XLSX download links.
3. **The demo run** — the offline **"Try a sample"** result, which works with no
   internet and is the safest thing to screenshot (no real scraped data, so
   nothing private gets committed). A short GIF of clicking it and seeing tiered
   output is ideal.

> Tip: prefer the offline demo for any committed screenshot so you never publish
> real business contact data — see [Responsible use](RESPONSIBLE_USE.md).
