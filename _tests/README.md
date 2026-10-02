# Site checks and integration points

This folder is not published. GitHub Pages builds this repository with Jekyll, which skips
paths that start with `_`. Do not add `.nojekyll` without first moving this folder out of
the published tree (a test guards this).

## Checks

Run from the repository root.

| Command | What it checks | Needs |
|---|---|---|
| `python3 _tests/test_site.py` | Routes, sitemap/robots, local assets, internal links and fragments, metadata, heading order, public-status claims, locked phrases, regressions | Python 3 (standard library) |
| `node _tests/render_audit.mjs . <out-dir> / /start-reading/ /no-such-page` | Renders each page at 1366, 390 and 320 px, normal and 200% root-font scaling; checks every text element doubles, overflow and heading word breaks. Keyboard traversal runs at every view, including the reduced-viewport/DPR approximation of desktop page zoom. Checks outer-frame focus only, reduced motion and offline local bytes. Exits 1 on a regression. External requests are blocked. | Node 18+, Playwright with Chromium (or `BROWSER_EXECUTABLE_PATH` pointing to local Chrome) |
| `python3 _tests/check_external.py` | One read-only GET per external destination. Reports `OK`, `BROKEN` (the destination answered 4xx/5xx) or `NETWORK-BLOCKED` (the check never reached it; not evidence of a broken link). | Network access to the destinations |
| `python3 _tests/make_preview.py <out-dir>` | Builds a relative-path copy with a "review preview" banner for owner review. Never deployed. | Python 3 |
| `python3 _tests/test_preview.py` | Rejects checkout/ancestor and existing-directory destinations without changing files; checks a new preview is usable. | Python 3 |

None of these submit the signup form, send email, or contact any purchase system.
Root-font scaling is not real browser text-only zoom. Reduced viewport/DPR is not
actual browser page zoom. Neither checks the live cross-origin form or a real device.
The preview helper refuses any existing output directory; choose a fresh path.

## Integration points

**Direct Dispatch links (Start reading page).** The headings link to Dispatches 001 and
002, opened in Chrome on 2026-10-01 New York / 2026-10-02 UTC. Titles and numbers match;
each returned HTTP 200. These are the existing 2025 posts, not the current canonical
manuscript or approval of a rewritten edition. Shared buttons open the publication home.
Before adding another step, verify its live title/number/URL and its version/publication
context. Record evidence in the canonical repository; update `PUBLISHED_DISPATCHES` and
`VERIFIED_POSTS` in `test_site.py` together. The set describes this path, not the whole
public inventory: Dispatch 003 and Signal 000 were also observed live in this session.

**Approved artifacts (home page, Mot Snilloc section).** The site has no purchase links.
Add a product destination only when all three exist: owner publication approval, a live
listing URL, and a completed test purchase with download and file-open check. A product
entry says exactly what the buyer gets. The purchase-language test in `test_site.py` will
fail until it is deliberately updated for that product. Review packages are never linked
as downloads.

**Analytics.** None is installed. Adding tracking needs its own authorization and a
privacy review first.
