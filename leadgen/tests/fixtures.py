"""
Generic business-website HTML fixtures for testing the audit + enrichment
heuristics offline. Each mimics a real-world scenario the extractors must handle:

  TEAM_PAGE    a firm with a staff/team page — distinct profile links + a named
               owner (tests roster sizing and decision-maker extraction)
  DUP_LINKS    a team where every person is linked twice (photo + name) — the
               classic over-count trap the roster estimator must avoid
  WIX_SITE     a DIY (Wix) site with no mobile viewport — audit should flag both
  CLEAN_SITE   a modern site: mobile viewport, no DIY builder — should look clean
  COMPETITOR_TESTIMONIALS   a competitor's client/testimonial wall (suppression)
"""

TEAM_PAGE = """
<html><head><title>Reyes &amp; Co</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body>
<nav><a href="/team">Our Team</a><a href="/services">Services</a></nav>
<section class="team">
  <h2>meet the team</h2>
  <div class="member"><a href="/team/maria-reyes">Maria Reyes</a> — Owner</div>
  <div class="member"><a href="/team/david-cho">David Cho</a> — Associate</div>
  <div class="member"><a href="/team/ana-ruiz">Ana Ruiz</a> — Associate</div>
  <div class="member"><a href="/team/sam-lee">Sam Lee</a> — Office Manager</div>
</section>
</body></html>
"""

# Every person appears as TWO links (image + name) — naive link-counting doubles it.
DUP_LINKS = """
<html><body><section class="roster">
  <div class="card"><a href="/team/aa/"><img alt="Pat AA"></a><a href="/team/aa/">Pat AA</a></div>
  <div class="card"><a href="/team/bb/"><img alt="Pat BB"></a><a href="/team/bb/">Pat BB</a></div>
  <div class="card"><a href="/team/cc/"><img alt="Pat CC"></a><a href="/team/cc/">Pat CC</a></div>
</section></body></html>
"""

WIX_SITE = """
<html><head><title>Joe's Diner</title></head>
<body><h1>Joe's Diner</h1><p>Best burgers in town.</p>
<!-- built on wix.com --><script src="https://static.wix.com/app.js"></script>
</body></html>
"""

CLEAN_SITE = """
<html><head><title>Bright Smile Dental</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body><h1>Bright Smile Dental</h1><p>Modern dentistry. Book online.</p></body></html>
"""

# Competitor testimonial / client-logo page (for suppression tests).
COMPETITOR_TESTIMONIALS = """
<html><body>
<h1>What our clients say</h1>
<blockquote>"They transformed our online presence!" — Jane Doe, Acme Plumbing</blockquote>
<blockquote>"Best decision we made." — Mark Lin, Summit Auto Repair</blockquote>
<div class="logos">
  <img alt="Bright Smile Dental" src="/l1.png">
  <img alt="Harbor Cafe" src="/l2.png">
</div>
</body></html>
"""

ALL = {
    "TEAM_PAGE": TEAM_PAGE, "DUP_LINKS": DUP_LINKS, "WIX_SITE": WIX_SITE,
    "CLEAN_SITE": CLEAN_SITE, "COMPETITOR_TESTIMONIALS": COMPETITOR_TESTIMONIALS,
}
