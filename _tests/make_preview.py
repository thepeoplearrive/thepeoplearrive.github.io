"""Build a self-contained review preview of the site in a separate folder.

Run from the repository root:  python3 _tests/make_preview.py <out-dir>

The live site uses root-relative paths (/css/site.css). Hosts that serve the preview from
a sub-path need relative paths, so this copies the public files, rewrites local paths,
and adds a visible "review preview" banner. The output is for owner review only; it is
never deployed and is not committed.
"""
import os
import re
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PAGES = ['index.html', 'start-reading/index.html', '404.html']
BANNER = ('<div style="background:#fff3c4;color:#2b2b2b;font:600 14px/1.4 Arial,sans-serif;'
          'padding:8px 16px;text-align:center">Review preview of a proposed change. '
          'Not the live site. The Substack form and links may not load here.</div>')


def relativize(html, depth):
    up = '../' * depth
    def fix(m):
        attr, path = m.group(1), m.group(2)
        if path.startswith('//'):
            return m.group(0)
        target, _, frag = path.lstrip('/').partition('#')
        if target == '' or target.endswith('/'):
            target += 'index.html'
        if frag:
            target += '#' + frag
        return f'{attr}="{up}{target}"'
    return re.sub(r'(href|src)="(/[^"]*)"', fix, html)


def main(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    for rel in PAGES:
        depth = rel.count('/')
        with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
            html = f.read()
        html = relativize(html, depth)
        html = html.replace('<body>', '<body>\n' + BANNER, 1)
        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(html)
    for d in ('css', 'js'):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(out, d))
    os.makedirs(os.path.join(out, 'img'))
    for name in ('tpa-title-burst-800.webp', 'favicon-64.png', 'apple-touch-icon-180.png'):
        shutil.copy(os.path.join(ROOT, 'img', name), os.path.join(out, 'img', name))
    print(f'preview written to {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'preview-out')
