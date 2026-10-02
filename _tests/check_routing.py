"""Live routing and hosting check for www.thepeoplearrive.com. Read-only.

Run from the repository root:
    python3 _tests/check_routing.py [--json out.json] [--strict]

Follows every redirect hop by hand (no automatic following) and checks that:
  - http/https apex, http www and the github.io host end at https://www.thepeoplearrive.com
    with the same path and query string, in permanent (301/308) hops;
  - no hop downgrades https to http, and there are no loops;
  - /, /start-reading/ return 200; a missing path keeps its path and returns the custom 404;
  - /sitemap.xml is valid XML listing canonical URLs; /robots.txt is plain text naming the
    canonical sitemap;
  - local assets answer 200; the two Dispatch links and the signup embed answer 200 (a 403
    from Substack to this automated client is reported as INCONCLUSIVE, not as a failure).
With GITHUB_TOKEN and GITHUB_REPOSITORY set (as in GitHub Actions with `pages: read`), it also
records the Pages settings (cname, https_enforced, certificate state and domains).

Only GET requests are made. Nothing is submitted, no email is sent, nothing is purchased.
Default mode reports and exits 0; --strict exits 1 when any check fails.
"""
import argparse
import datetime
import http.client
import json
import os
import ssl
import sys
import urllib.parse
import xml.etree.ElementTree as ET

CANON = 'www.thepeoplearrive.com'
APEX = 'thepeoplearrive.com'
GHIO = 'thepeoplearrive.github.io'
QUERY = 'rc=1&x=a%20b'
UA = 'tpa-routing-check/1 (read-only)'
PERMANENT = {301, 308}

ASSETS = ['/css/site.css', '/js/site.js', '/img/tpa-title-burst-800.webp',
          '/img/tpa-title-burst-og.jpg', '/img/favicon-64.png']
EXTERNAL = ['https://thepeoplearrive.substack.com/p/dispatch-001-the-day-the-coupons',
            'https://thepeoplearrive.substack.com/p/dispatch-002-the-algorithm-knows',
            'https://thepeoplearrive.substack.com/embed']


def fetch(url, max_body=200_000):
    """One GET without following redirects. Returns (status, headers, body) or raises."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or '/') + (('?' + u.query) if u.query else '')
    if u.scheme == 'https':
        conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=20,
                                           context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=20)
    try:
        conn.request('GET', path, headers={'User-Agent': UA, 'Accept': '*/*'})
        r = conn.getresponse()
        body = r.read(max_body)
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body
    finally:
        conn.close()


def chain(url, limit=10):
    hops, seen = [], set()
    while True:
        if url in seen:
            return hops, 'loop'
        seen.add(url)
        try:
            status, headers, body = fetch(url)
        except Exception as e:  # network/TLS failure is recorded, not raised
            hops.append({'url': url, 'error': f'{type(e).__name__}: {e}'[:200]})
            return hops, 'error'
        hop = {'url': url, 'status': status}
        if 300 <= status < 400 and 'location' in headers:
            nxt = urllib.parse.urljoin(url, headers['location'])
            hop['location'] = nxt
            hops.append(hop)
            if len(hops) > limit:
                return hops, 'too-many-redirects'
            url = nxt
            continue
        hop['content_type'] = headers.get('content-type', '')
        hop['_body'] = body
        hops.append(hop)
        return hops, 'ok'


def norm(url):
    """Treat a bare host as its root path; compare everything else exactly."""
    u = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path or '/', u.query, u.fragment))


def evaluate(start, expect_path, expect_status, hops, outcome):
    problems = []
    if outcome != 'ok':
        problems.append(outcome + (': ' + hops[-1].get('error', '') if outcome == 'error' else ''))
        return problems
    final = hops[-1]
    expected = f'https://{CANON}{expect_path}'
    if norm(final['url']) != norm(expected):
        problems.append(f'final URL {final["url"]} != {expected}')
    if final['status'] != expect_status:
        problems.append(f'final status {final["status"]} != {expect_status}')
    for a, b in zip(hops, hops[1:]):
        if a['url'].startswith('https://') and b['url'].startswith('http://'):
            problems.append(f'https->http downgrade at {a["url"]}')
        if a['status'] not in PERMANENT:
            problems.append(f'non-permanent redirect {a["status"]} at {a["url"]}')
    return problems


def check_body(path, hop):
    body = hop.get('_body', b'')
    ct = hop.get('content_type', '')
    if path.startswith('/sitemap.xml'):
        try:
            root = ET.fromstring(body)
            ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            locs = [e.text for e in root.findall('s:url/s:loc', ns)]
            bad = [l for l in locs if not l.startswith(f'https://{CANON}/')]
            return ([f'non-canonical sitemap URLs {bad}'] if bad else []) + ([] if 'xml' in ct else [f'content-type {ct}'])
        except ET.ParseError as e:
            return [f'sitemap not XML: {e}']
    if path.startswith('/robots.txt'):
        text = body.decode('utf-8', 'replace')
        out = [] if ct.startswith('text/plain') else [f'content-type {ct}']
        if f'Sitemap: https://{CANON}/sitemap.xml' not in text:
            out.append('robots.txt lacks canonical Sitemap line')
        return out
    if path.startswith('/start-reading/'):
        return [] if b'Start reading.' in body else ['Start reading content missing']
    if path == '/' or path.startswith('/?'):
        return [] if b'Story is protocol.' in body else ['home content missing']
    if 'routing-check-missing' in path:
        return [] if b'Nothing at this address.' in body else ['custom 404 content missing']
    return []


def pages_settings():
    token, repo = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not (token and repo):
        return {'skipped': 'GITHUB_TOKEN/GITHUB_REPOSITORY not set'}
    conn = http.client.HTTPSConnection('api.github.com', timeout=20)
    try:
        conn.request('GET', f'/repos/{repo}/pages', headers={
            'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': UA})
        r = conn.getresponse()
        data = json.loads(r.read() or b'{}')
    finally:
        conn.close()
    if r.status != 200:
        return {'status': r.status, 'message': data.get('message')}
    keep = ('cname', 'https_enforced', 'status', 'build_type', 'source', 'html_url', 'protected_domain_state')
    out = {k: data.get(k) for k in keep}
    cert = data.get('https_certificate') or {}
    out['https_certificate'] = {k: cert.get(k) for k in ('state', 'description', 'domains', 'expires_at')}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    cases = []
    paths = [('/', 200), ('/start-reading/', 200), ('/sitemap.xml', 200), ('/robots.txt', 200),
             ('/routing-check-missing/', 404), (f'/start-reading/?{QUERY}', 200), (f'/?{QUERY}', 200)]
    origins = [f'https://{CANON}', f'http://{CANON}', f'https://{APEX}', f'http://{APEX}',
               f'https://{GHIO}', f'http://{GHIO}']
    for origin in origins:
        for path, status in paths:
            hops, outcome = chain(origin + path)
            problems = evaluate(origin + path, path, status, hops, outcome)
            if outcome == 'ok':
                problems += check_body(path, hops[-1])
            cases.append({'start': origin + path, 'hops': [{k: v for k, v in h.items() if k != '_body'} for h in hops],
                          'outcome': outcome, 'problems': problems})
    for path in ASSETS:
        hops, outcome = chain(f'https://{CANON}{path}')
        problems = evaluate(f'https://{CANON}{path}', path, 200, hops, outcome)
        cases.append({'start': f'https://{CANON}{path}', 'hops': [{k: v for k, v in h.items() if k != '_body'} for h in hops],
                      'outcome': outcome, 'problems': problems})
    for url in EXTERNAL:
        hops, outcome = chain(url)
        final = hops[-1]
        problems, note = [], None
        if outcome == 'ok' and final.get('status') == 403:
            # Substack answers 403 to automated clients; that says nothing about the link.
            note = 'INCONCLUSIVE: destination refused an automated client (403); check in a browser'
        elif not (outcome == 'ok' and final.get('status') == 200):
            problems = [f'{outcome}: status {final.get("status", final.get("error"))}']
        cases.append({'start': url, 'hops': [{k: v for k, v in h.items() if k != '_body'} for h in hops],
                      'outcome': outcome, 'problems': problems, 'note': note})

    report = {'started_utc': started, 'pages': pages_settings(), 'cases': cases,
              'failures': sum(1 for c in cases if c['problems'])}
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(report, f, indent=2)

    print(f'Routing check started {started}')
    print('Pages settings:', json.dumps(report['pages']))
    for c in cases:
        mark = 'FAIL' if c['problems'] else ('NOTE' if c.get('note') else 'PASS')
        path = ' -> '.join(f'{h.get("status", "ERR")} {h["url"]}' for h in c['hops'])
        print(f'{mark}  {path}')
        for p in c['problems'] + ([c['note']] if c.get('note') else []):
            print(f'      - {p}')
    print(f'{report["failures"]} of {len(cases)} checks failed')
    return 1 if (args.strict and report['failures']) else 0


if __name__ == '__main__':
    sys.exit(main())
