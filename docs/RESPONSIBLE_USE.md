# Responsible use

This is a prospecting tool for **your own outreach** — finding local businesses
*you* might want to work with, and auditing their public web presence so you can
pitch something useful. It is not a data-broker kit. The whole design leans that
way: no data ships in the repo, lead files are git-ignored, and the crawler asks
for one homepage per business with a polite, identifiable user-agent.

This page expands the README's short "Use it responsibly" section into something
you can actually act on. **It is not legal advice** — it's an orientation map so
you know which rules exist and where to look. When real money or real volume is
on the line, talk to a lawyer in your jurisdiction.

---

## The one-line rule

**Generate a call list for your own business. Don't resell a list of strangers'
personal data.** Those are legally and ethically different activities, and almost
everything below follows from that distinction.

- *Your own outreach* — you pull public business listings, audit their sites, and
  reach out to offer a service. Normal B2B prospecting.
- *Reselling personal data* — you package contacts and sell or trade them as a
  product. That can make you a **data broker**, with registration and deletion
  obligations (see below). This tool isn't built for it, and the licenses on the
  underlying data mostly don't permit it.

If you're not sure which one you're doing, you're probably drifting toward the
second. Stop and check.

---

## Per-source licensing & attribution

Every source returns the same record shape, but each carries its **own license**.
The data you collect inherits the license of where it came from — and if you
**publish** anything derived from it (a public directory, a map, a report, a
dataset), you owe the attribution below. Internal prospecting use is lighter, but
attribution is cheap, so default to crediting.

| Source | License | What you owe if you publish derived work |
|---|---|---|
| **overture** | CC-BY 4.0 | Credit **"Overture Maps Foundation"** (and its data providers per Overture's attribution guidance). |
| **osm** | ODbL | Credit **"© OpenStreetMap contributors"**; ODbL's share-alike can attach to a derived *database* you publish. |
| **socrata** | per-portal / per-publisher | Each city/county portal sets its own terms — check the dataset's license page; attribute the publishing agency. |
| **arcgis** | per-publisher | Same as Socrata: the layer's owning government/org sets terms; attribute them. |
| **npi** | public domain (US government / CMS NPPES) | No attribution required; crediting CMS NPPES is courteous, not mandatory. |
| **foursquare** | Apache-2.0 (Foursquare OS Places) | Preserve the Apache-2.0 notice; attribute **Foursquare**. It's a frozen 2024-11-19 snapshot — note staleness if you republish. |

A few practical notes:

- **CC-BY and ODbL want credit, not silence.** A visible "Data: Overture Maps
  Foundation; © OpenStreetMap contributors" line on anything public covers the
  common case.
- **ODbL share-alike** is the one with teeth: if you publish a *derived database*
  built on OSM, that derived database may itself need to be ODbL. Pulling a few
  leads into your CRM for outreach is fine; publishing a competing dataset is
  where you read the license closely.
- **Socrata/ArcGIS terms vary wildly.** Some portals are fully open; some restrict
  commercial use or redistribution. The terms live on the dataset page on the
  portal you pulled from — that's the authority, not this doc.
- **NPI is public-domain US gov data**, which is exactly why `npi` records make
  good "needs-a-website" leads — but "public domain" governs *copyright*, not how
  you may *contact* people. Anti-spam law (below) still applies.

---

## Be a polite, identifiable crawler

The website audit fetches each business's homepage **once** to check whether it's
reachable, on HTTPS, mobile-friendly, fast, and which builder it uses. That's a
single light request per lead — not a crawl, not a scrape of their whole site.
Keep it that way:

- **Identify yourself.** Set the `LEADGEN_UA` environment variable to a user-agent
  string with *your own* contact info, so a site owner who checks their logs can
  reach you:

  ```bash
  # macOS / Linux
  export LEADGEN_UA="my-leadgen/1.0 (you@example.com)"
  # Windows PowerShell
  $env:LEADGEN_UA = "my-leadgen/1.0 (you@example.com)"
  ```

- **Respect robots.txt and each site's / source's Terms of Service.** If a site or
  a data portal says don't, don't.
- **Don't hammer the sources.** Use `--limit` and `--enrich-cap` to keep runs
  modest, especially against shared public infrastructure (Overpass mirrors, the
  Socrata/ArcGIS portals, the NPI API, the Foursquare mirror). These are free
  community/government resources — over-querying them ruins it for everyone.
- **The slow source is slow for a reason.** `foursquare` scans a whole open
  mirror (~1–2 min per run). Treat it as a deliberate deep pass, not something to
  loop in a script.

---

## When you actually contact leads: anti-spam & privacy law

Finding a lead is one thing; emailing, calling, or texting them is another, and
that's where the marketing laws live. **None of this is legal advice** — these are
the regimes to be aware of and the obligations they share.

- **CAN-SPAM (US).** For commercial email: no false/misleading headers or subject
  lines, identify the message as an ad where required, include a valid physical
  postal address, and give a working **opt-out** that you honor promptly. Applies
  per-message — there's no "but they're a business" exemption.
- **CASL (Canada).** Stricter: generally requires **consent** (express or implied)
  *before* you send commercial electronic messages, plus clear sender ID and a
  working unsubscribe. Implied consent has narrow conditions and time limits. The
  penalties are real.
- **GDPR / ePrivacy (EU/UK).** Personal data of individuals is protected; you need
  a lawful basis to process it, and ePrivacy rules govern electronic marketing
  (often consent-based, with a narrow "soft opt-in" for existing customers).
  People have rights to access and erasure. A named person at a business is still
  a person.

Cross-cutting obligations that show up in basically all of them:

- **Honor opt-outs/unsubscribes** quickly and permanently.
- **Don't disguise who you are** — accurate sender identity and headers.
- **Keep records** of consent / suppression so you can prove compliance.
- Phone and SMS outreach have their *own* rules (e.g. US TCPA, do-not-call
  registries). A generated phone list is not a green light to dial.

### Generating a list vs. selling one

Worth repeating because it changes your legal footing:

- **For your own business:** you're a company doing B2B outreach. Standard
  marketing law applies; stay clean and you're on solid ground.
- **Selling/brokering the data:** you may become a **data broker**. For example,
  **California's DELETE Act** requires data brokers to register and to honor a
  centralized deletion mechanism; other US states and the EU have their own broker
  / privacy regimes. The source licenses above also frequently *prohibit*
  redistribution. This tool is not designed for that path — if you go there,
  you're on your own legally, and you should get advice first.

---

## Never commit scraped data

Lead files are **regenerated per run** and must never land in a repo. The
`.gitignore` enforces this — `*.csv`, `*.xlsx`, `*.jsonl`, `*.parquet`, `*.sqlite`
and the GUI's `gui/_output/` are all ignored by design:

```gitignore
# Scraped / generated lead data — NEVER commit this.
*.csv
*.xlsx
*.jsonl
*.parquet
*.sqlite
```

Keep it that way. The repo stays a **tool**, not a dataset — which keeps you out
of data-broker territory and keeps other people's contact details off the public
internet. If you add new output formats, add them to `.gitignore` too.

---

## TL;DR

- It's for **your** outreach. Don't resell strangers' personal data.
- **Attribute** Overture and OpenStreetMap (and others) on anything you publish;
  check Socrata/ArcGIS portal terms before redistributing.
- Set `LEADGEN_UA` to your contact, respect robots/ToS, and don't hammer free
  sources.
- Before you contact anyone: know **CAN-SPAM / CASL / GDPR** — accurate identity,
  honor opt-outs, mind consent.
- Selling lists can make you a **data broker** (e.g. California DELETE Act). Don't
  drift into it by accident.
- **Never commit scraped data.** The `.gitignore` already has your back.

*Not legal advice. When in doubt, ask a lawyer in your jurisdiction.*
