# Site checks and integration points

This folder is not published. GitHub Pages builds this repository with Jekyll, which skips
paths that start with `_`. Do not add `.nojekyll` without first moving this folder out of
the published tree (a test guards this).

## Checks

Run from the repository root.

| Command | What it checks | Needs |
|---|---|---|
| `python3 _tests/test_site.py` | Routes, sitemap/robots, local assets, internal links and fragments, metadata, heading order, public-status claims, locked phrases, regressions | Python 3 (standard library) |
| `node _tests/render_audit.mjs . <out-dir> / /start-reading/ /no-such-page` | Renders each page at 1366, 390 and 320 px, each at 100% and 200% text, plus 200% page zoom; horizontal overflow; headings that would break mid-word; keyboard focus order and focus-ring contrast; reduced motion; local page weight and requests; full-page screenshots. Exits 1 on a regression. External requests are blocked so results repeat offline. | Node 18+, Playwright with Chromium |
| `python3 _tests/check_external.py` | One read-only GET per external destination. Reports `OK`, `BROKEN` (the destination answered 4xx/5xx) or `NETWORK-BLOCKED` (the check never reached it; not evidence of a broken link). | Network access to the destinations |
| `python3 _tests/make_preview.py <out-dir>` | Builds a relative-path copy with a "review preview" banner for owner review. Never deployed. | Python 3 |

None of these submit the signup form, send email, or contact any purchase system.

## Integration points

**Direct Dispatch links (Start reading page).** Each reading step currently sends readers
to the Substack publication, because no individual Dispatch URL has been opened and
checked. To add one: open the post in a browser, confirm its title and number match the
step, then link that step's heading or add a "Read Dispatch 00N" link, and record the
check in the canonical production record. Add a step only for a Dispatch with publication
evidence; `PUBLISHED_DISPATCHES` in `test_site.py` must be updated in the same change.

**Approved artifacts (home page, Mot Snilloc section).** The site has no purchase links.
Add a product destination only when all three exist: owner publication approval, a live
listing URL, and a completed test purchase with download and file-open check. A product
entry says exactly what the buyer gets. The purchase-language test in `test_site.py` will
fail until it is deliberately updated for that product. Review packages are never linked
as downloads.

**Analytics.** None is installed. Adding tracking needs its own authorization and a
privacy review first.
