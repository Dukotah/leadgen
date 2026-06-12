# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for
anything that could put users at risk.

- Use GitHub's **[Report a vulnerability](../../security/advisories/new)** form
  (Security → Advisories) to open a private advisory, **or**
- Email the maintainers at **security@example.com** *(replace with your contact)*.

Include enough to reproduce: affected version/commit, steps, and the impact you
observed. We'll acknowledge your report, investigate, and keep you posted on a fix.
Please give us reasonable time to ship a fix before any public disclosure.

## Supported versions

leadgen is pre-1.x in spirit and ships from the latest release. Security fixes
land on the **latest released version** and `main`; older tags are not
back-patched.

| Version | Supported |
|---|---|
| latest release / `main` | ✅ |
| older releases | ❌ |

## Threat model (what this tool is)

leadgen is a **local** tool. It runs on your machine, takes no inbound
connections, and stores no credentials — it is **key-free** by design. Its only
network activity is **outbound requests** to open public data sources (Overture,
OpenStreetMap/Overpass, Socrata, NPI, ArcGIS, the Foursquare open mirror) and a
single polite fetch of each prospect's own homepage during the website audit
(identify yourself via the `LEADGEN_UA` environment variable).

The optional GUI/desktop app serves a local web UI bound to localhost for your own
use; don't expose it to untrusted networks.

Because it processes data fetched from third-party sources, the security surface
is mostly **parsing untrusted input** (HTML, JSON, CSV, geo data). Reports about
crashes, resource exhaustion, or injection from crafted source data are in scope
and welcome.
