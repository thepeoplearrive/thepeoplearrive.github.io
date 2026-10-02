"""Static checks for the site. Standard library only; no network.

Run from the repository root:  python3 _tests/test_site.py

Covers routes, local assets, internal links and fragments, metadata, public-status
claims (what the site may and may not say), locked phrases, and regressions from
earlier versions of the page.
"""
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ORIGIN = 'https://www.thepeoplearrive.com'
SUBSTACK = 'thepeoplearrive.substack.com'

# Public routes -> source file. 404.html is served by GitHub Pages for unknown paths.
PAGES = {
    '/': 'index.html',
    '/start-reading/': 'start-reading/index.html',
}
ERROR_PAGE = '404.html'
ALL_HTML = list(PAGES.values()) + [ERROR_PAGE]

# Locked phrases (docs/BRAND.md "Immutable Elements" in the canonical repository).
HERO_PHRASE = 'Story is protocol.'
THREE_BODY = ('The Adventures taught it. The Playbook holds it. '
              'The People Arrive is what happens when enough of us share it.')

# Dispatches included in this bounded reading path; not the full live inventory.
# Exact URLs/titles were opened in Chrome by the 2026-10-01 correction session.
PUBLISHED_DISPATCHES = {'001', '002'}
VERIFIED_POSTS = {
    'https://thepeoplearrive.substack.com/p/dispatch-001-the-day-the-coupons': 'The Day the Coupons Died',
    'https://thepeoplearrive.substack.com/p/dispatch-002-the-algorithm-knows': "The Algorithm Knows You're Tired",
}

# Per-page budget for local bytes a reader downloads (HTML + CSS + images + icons).
LOCAL_BYTE_BUDGET = 80_000


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []          # (tag, attrs dict)
        self.ids = set()
        self.text = []
        self.title = ''
        self._in_title = False
        self._skip = 0          # inside <script>/<style>
        self.headings = []      # (level, text)
        self._heading = None
        self.comments = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if 'id' in a:
            self.ids.add(a['id'])
        if tag == 'title':
            self._in_title = True
        if tag in ('script', 'style'):
            self._skip += 1
        if re.fullmatch(r'h[1-6]', tag):
            self._heading = [int(tag[1]), '']

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag in ('script', 'style'):
            self._skip -= 1
        if self._heading and tag == f'h{self._heading[0]}':
            self.headings.append((self._heading[0], ' '.join(self._heading[1].split())))
            self._heading = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip:
            return
        self.text.append(data)
        if self._heading:
            self._heading[1] += data

    def handle_comment(self, data):
        self.comments.append(data)

    def visible_text(self):
        return ' '.join(' '.join(self.text).split())

    def find(self, tag, **attrs):
        return [a for t, a in self.tags if t == tag and all(a.get(k) == v for k, v in attrs.items())]


def parse(rel):
    p = Page()
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        p.feed(f.read())
    return p


def resolve_local(path):
    """Map a site path to a file the way GitHub Pages would, or None."""
    path = path.split('#')[0].split('?')[0]
    if not path.startswith('/'):
        return None
    full = os.path.join(ROOT, path.lstrip('/'))
    if path.endswith('/'):
        full = os.path.join(full, 'index.html')
    elif os.path.isdir(full):
        full = os.path.join(full, 'index.html')
    return full if os.path.isfile(full) else None


def links(page):
    out = []
    for tag, a in page.tags:
        for attr in ('href', 'src'):
            if attr in a and a[attr] is not None:
                out.append((tag, attr, a[attr]))
    return out


class Routes(unittest.TestCase):
    def test_route_files_exist(self):
        for route, rel in PAGES.items():
            self.assertTrue(os.path.isfile(os.path.join(ROOT, rel)), route)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, ERROR_PAGE)))

    def test_cname_is_custom_domain(self):
        with open(os.path.join(ROOT, 'CNAME')) as f:
            self.assertEqual(f.read().strip(), 'www.thepeoplearrive.com')

    def test_sitemap_lists_exactly_the_public_pages(self):
        tree = ET.parse(os.path.join(ROOT, 'sitemap.xml'))
        ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        locs = [e.text for e in tree.getroot().findall('s:url/s:loc', ns)]
        self.assertEqual(sorted(locs), sorted(ORIGIN + r for r in PAGES))
        for loc in locs:
            self.assertIsNotNone(resolve_local(urlparse(loc).path), loc)

    def test_robots_allows_and_points_to_sitemap(self):
        with open(os.path.join(ROOT, 'robots.txt')) as f:
            robots = f.read()
        self.assertIn('Allow: /', robots)
        self.assertNotIn('Disallow: /\n', robots)
        self.assertIn(f'Sitemap: {ORIGIN}/sitemap.xml', robots)

    def test_dev_files_are_not_published(self):
        # Jekyll (GitHub Pages default build) skips underscore paths, so tests stay out of the site.
        self.assertFalse(os.path.exists(os.path.join(ROOT, '.nojekyll')),
                         '.nojekyll would publish _tests/; exclude it some other way first')


class LocalAssetsAndLinks(unittest.TestCase):
    def test_every_local_reference_resolves_to_a_nonempty_file(self):
        for rel in ALL_HTML:
            for tag, attr, url in links(parse(rel)):
                u = urlparse(url)
                if u.scheme or url.startswith('#') or url.startswith('mailto:'):
                    continue
                target = resolve_local(url)
                self.assertIsNotNone(target, f'{rel}: {tag} {attr}={url}')
                self.assertGreater(os.path.getsize(target), 0, f'{rel}: zero-byte {url}')

    def test_internal_fragments_exist(self):
        for rel in ALL_HTML:
            page = parse(rel)
            for tag, attr, url in links(page):
                if attr != 'href' or urlparse(url).scheme:
                    continue
                if '#' not in url:
                    continue
                path, frag = url.split('#', 1)
                target_page = page if not path else parse(os.path.relpath(resolve_local(path), ROOT))
                self.assertIn(frag, target_page.ids, f'{rel}: missing #{frag} for {url}')

    def test_images_have_alt_and_dimensions(self):
        for rel in ALL_HTML:
            for img in parse(rel).find('img'):
                self.assertIn('alt', img, f'{rel}: {img.get("src")}')
                self.assertTrue(img.get('width') and img.get('height'), f'{rel}: {img.get("src")} lacks width/height')

    def test_iframes_have_titles_and_a_plain_link_fallback(self):
        for rel in ALL_HTML:
            page = parse(rel)
            frames = page.find('iframe')
            for fr in frames:
                self.assertTrue(fr.get('title'), rel)
                self.assertEqual(fr.get('loading'), 'lazy', rel)
            if frames:
                self.assertIn('Form not showing? Subscribe on Substack.', page.visible_text(), rel)

    def test_external_links_only_go_to_substack(self):
        for rel in ALL_HTML:
            for tag, attr, url in links(parse(rel)):
                u = urlparse(url)
                if u.scheme in ('http', 'https'):
                    self.assertEqual(u.scheme, 'https', url)
                    if tag == 'link' or (tag == 'meta'):
                        continue
                    self.assertEqual(u.netloc, SUBSTACK, f'{rel}: unexpected external host {url}')

    def test_local_weight_within_budget(self):
        for rel in ALL_HTML:
            total = os.path.getsize(os.path.join(ROOT, rel))
            seen = set()
            for tag, attr, url in links(parse(rel)):
                if tag in ('img', 'link', 'script') and not urlparse(url).scheme:
                    target = resolve_local(url)
                    if target and target not in seen and (tag != 'link' or 'stylesheet' in str(parse(rel).find('link', href=url))):
                        seen.add(target)
                        total += os.path.getsize(target)
            self.assertLess(total, LOCAL_BYTE_BUDGET, f'{rel}: {total} bytes')


class Metadata(unittest.TestCase):
    def test_document_basics(self):
        for rel in ALL_HTML:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
                raw = f.read()
            self.assertTrue(raw.startswith('<!doctype html>'), rel)
            self.assertIn('<html lang="en">', raw, rel)
            page = parse(rel)
            self.assertTrue(page.find('meta', charset='utf-8'), rel)
            self.assertTrue(page.find('meta', name='viewport'), rel)
            self.assertTrue(page.title.strip(), rel)
            self.assertEqual(len(page.find('main')), 1, rel)
            skip = page.find('a', **{'class': 'skip'})
            self.assertTrue(skip and skip[0]['href'] == '#main', rel)

    def test_public_pages_have_unique_titles_descriptions_and_canonicals(self):
        titles, descs = set(), set()
        for route, rel in PAGES.items():
            page = parse(rel)
            desc = page.find('meta', name='description')
            self.assertTrue(desc, rel)
            d = desc[0]['content']
            self.assertTrue(50 <= len(d) <= 160, f'{rel}: description length {len(d)}')
            self.assertNotIn(page.title, titles)
            self.assertNotIn(d, descs)
            titles.add(page.title)
            descs.add(d)
            canon = page.find('link', rel='canonical')
            self.assertEqual(canon[0]['href'], ORIGIN + route, rel)
            og = {a.get('property'): a.get('content') for t, a in page.tags if t == 'meta' and a.get('property', '').startswith('og:')}
            self.assertEqual(og.get('og:url'), ORIGIN + route, rel)
            for key in ('og:title', 'og:description', 'og:image', 'og:image:alt', 'og:image:width', 'og:image:height'):
                self.assertTrue(og.get(key), f'{rel}: {key}')
            img = urlparse(og['og:image'])
            self.assertEqual(f'{img.scheme}://{img.netloc}', ORIGIN, rel)
            self.assertIsNotNone(resolve_local(img.path), og['og:image'])

    def test_error_page_is_not_indexed(self):
        page = parse(ERROR_PAGE)
        self.assertTrue(page.find('meta', name='robots', content='noindex'))
        self.assertFalse(page.find('link', rel='canonical'))
        # Served at arbitrary depths, so every local reference must be root-relative.
        for tag, attr, url in links(page):
            if not urlparse(url).scheme and not url.startswith('#'):
                self.assertTrue(url.startswith('/'), url)

    def test_one_h1_and_no_skipped_heading_levels(self):
        for rel in ALL_HTML:
            levels = [lvl for lvl, _ in parse(rel).headings]
            self.assertEqual(levels.count(1), 1, rel)
            self.assertEqual(levels[0], 1, rel)
            for prev, cur in zip(levels, levels[1:]):
                self.assertLessEqual(cur - prev, 1, f'{rel}: h{prev} -> h{cur}')

    def test_current_page_is_marked_in_navigation(self):
        nav = [a for t, a in parse(PAGES['/start-reading/']).tags if t == 'a' and a.get('aria-current') == 'page']
        self.assertEqual([a['href'] for a in nav], ['/start-reading/'])


class PublicStatusClaims(unittest.TestCase):
    """What the public site may claim, per the canonical publication records."""

    def text(self, rel):
        return parse(rel).visible_text()

    def test_locked_phrases_are_verbatim(self):
        home = self.text('index.html')
        self.assertIn(HERO_PHRASE, home)
        self.assertIn(THREE_BODY, home)
        self.assertEqual(parse('index.html').headings[0], (1, HERO_PHRASE))

    def test_no_purchase_or_price_calls_to_action(self):
        banned = re.compile(r'gumroad|\bbuy\b|checkout|add to cart|order now|pre-?order|\$\s?\d|price|shop\b|store\b|download now', re.I)
        for rel in ALL_HTML:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
                raw = f.read()
            # Comments document the integration point and may name the rule; strip them.
            raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
            self.assertIsNone(banned.search(raw), f'{rel}: {banned.search(raw)}')

    def test_no_release_dates_cadence_or_availability_promises(self):
        banned = re.compile(r'coming soon|available now|out now|launch(es|ing)?\b|every (week|tuesday|friday|month)|weekly|'
                            r'(?-i:\b(January|February|March|April|May|June|July|August|September|October|November|December)\b)|'
                            r'\b20(2[6-9]|3\d)\b|pre-?order|release date|this (fall|winter|spring|summer)', re.I)
        for rel in ALL_HTML:
            m = banned.search(self.text(rel).replace('© 2026', ''))
            self.assertIsNone(m, f'{rel}: {m}')

    def test_unpublished_bodies_are_described_as_in_development(self):
        for rel in ALL_HTML:
            t = self.text(rel)
            for body in ('Human Playbook', 'Adventures'):
                if body in t:
                    self.assertIn('in development', t.lower(), f'{rel}: {body} named without status')
            self.assertNotRegex(t, r'(Human Playbook|Adventures)[^.]*\b(is|are) (published|available|out)\b')

    def test_only_evidenced_dispatches_are_called_published(self):
        t = self.text('start-reading/index.html')
        numbers = set(re.findall(r'Dispatch (\d{3})', t))
        self.assertTrue(numbers <= PUBLISHED_DISPATCHES, numbers)
        self.assertEqual(t.count('Published'), len(PUBLISHED_DISPATCHES))
        # The explicitly verified path contains 001 before 002.
        self.assertLess(t.index('Dispatch 001'), t.index('Dispatch 002'))
        self.assertIn('The Day the Coupons Died', t)
        self.assertIn("The Algorithm Knows You're Tired", t)

    def test_reading_steps_have_the_verified_individual_destinations(self):
        page = parse('start-reading/index.html')
        for url in VERIFIED_POSTS:
            self.assertEqual(len(page.find('a', href=url)), 1, url)
        post_links = [a['href'] for a in page.find('a') if '/p/' in a.get('href', '')]
        self.assertEqual(post_links, list(VERIFIED_POSTS))
        self.assertIn('open the published Dispatches directly', page.visible_text())
        self.assertNotIn('Chapter 1:', page.visible_text())

    def test_book_one_is_not_claimed_published(self):
        for rel in ALL_HTML:
            self.assertNotRegex(self.text(rel), r'Book I (is|has been) (published|available|out)')

    def test_no_internal_or_private_material(self):
        banned = re.compile(r'third thing|canon|governance|owner approval|andrea|sunset walk of life|repository|'
                            r'manuscript|bloom map|guild|node \d|LD-\d|draft(ed)? dispatch', re.I)
        for rel in ALL_HTML:
            m = banned.search(self.text(rel))
            self.assertIsNone(m, f'{rel}: {m}')

    def test_bobbyx_is_not_presented_as_narrator_or_speaker(self):
        for rel in ALL_HTML:
            self.assertNotRegex(self.text(rel), r'(?i)bobbyx (says|narrat|tells|speaks|writes|invites)')

    def test_no_unverified_contact_or_social_destinations(self):
        for rel in ALL_HTML:
            with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
                raw = f.read()
            self.assertNotRegex(raw, r'(?i)mailto:|instagram|twitter\.com|x\.com/|threads\.net|facebook')


class Regressions(unittest.TestCase):
    def raw(self, rel):
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            return f.read()

    def test_no_popup_or_new_window_scripts(self):
        for rel in ALL_HTML:
            self.assertNotIn('window.open', self.raw(rel))
            self.assertNotIn('/popup', self.raw(rel))
            self.assertNotIn('target="_blank"', self.raw(rel))

    def test_no_broken_or_heavy_legacy_assets(self):
        for rel in ALL_HTML:
            r = self.raw(rel)
            self.assertNotIn('fiber-paper.png', r)
            self.assertNotIn('ritual-kitchen-signal', r)
            self.assertNotIn('dispatch-001-boot-sequence', r)
            self.assertNotRegex(r, r'<img[^>]+tpa-title-burst\.webp')
            self.assertNotIn('thepeoplearrive.github.io', r)

    def test_stylesheet_keeps_focus_reduced_motion_and_mobile_rules(self):
        css = self.raw('css/site.css')
        self.assertIn('a:focus-visible', css)
        self.assertIn('iframe:focus', css)
        self.assertIn('.signup.has-focus', css)  # ring around the embed while it holds focus
        self.assertIn("classList.toggle('has-focus'", self.raw('js/site.js'))
        self.assertIn('.skip:focus-visible { outline-color:var(--signal); }', css)
        self.assertIn('prefers-reduced-motion:reduce', css)
        self.assertIn('@media (max-width:50rem)', css)
        self.assertIn('overflow-wrap:break-word', css)
        self.assertRegex(css, r'Georgia')  # owner decision 2026-09-30: keep Georgia/Arial

    def test_plain_brand_footer(self):
        for rel in ALL_HTML:
            r = self.raw(rel)
            self.assertIn('The People Arrive</span>', r)
            self.assertNotIn('a brand of', r)


if __name__ == '__main__':
    result = unittest.main(exit=False, verbosity=2).result
    sys.exit(0 if result.wasSuccessful() else 1)
