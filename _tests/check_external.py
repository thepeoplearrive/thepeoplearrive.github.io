"""Check every external destination the pages link to, read-only.

Run from the repository root:  python3 _tests/check_external.py

Each URL gets one GET (no forms, no signups, no cookies kept). Results are classified as:
  OK              2xx/3xx from the destination
  BROKEN          the destination answered 4xx/5xx
  NETWORK-BLOCKED the request never reached the destination (proxy refusal, DNS, TLS,
                  timeout). This is a limit of the checking environment, not evidence
                  that the link is broken.
Exit code is 1 only for BROKEN.
"""
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PAGES = ['index.html', 'start-reading/index.html', '404.html']


def external_urls():
    urls = set()
    for rel in PAGES:
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            raw = re.sub(r'<!--.*?-->', '', f.read(), flags=re.S)
        for m in re.finditer(r'(?:href|src)="(https?://[^"]+)"', raw):
            url = m.group(1)
            if not url.startswith('https://www.thepeoplearrive.com/'):  # own canonical/OG URLs
                urls.add(url)
    # The live site itself, to compare with the repository.
    urls.add('https://www.thepeoplearrive.com/')
    return sorted(urls)


def check(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'tpa-link-check/1 (read-only)'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return 'OK', str(resp.status)
    except urllib.error.HTTPError as e:
        return 'BROKEN', f'HTTP {e.code}'
    except urllib.error.URLError as e:
        reason = e.reason
        text = str(reason)
        # Proxy CONNECT refusals surface as OSError("Tunnel connection failed: 403 ...").
        return 'NETWORK-BLOCKED', text[:120]
    except (socket.timeout, ssl.SSLError, ConnectionError, OSError) as e:
        return 'NETWORK-BLOCKED', str(e)[:120]


def main():
    broken = 0
    for url in external_urls():
        status, detail = check(url)
        broken += status == 'BROKEN'
        print(f'{status:16} {url}  ({detail})')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
