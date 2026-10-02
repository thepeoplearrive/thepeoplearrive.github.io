// Rendered audit for the static site: layout overflow, text zoom, keyboard focus,
// headings, images, reduced motion and local page weight.
//
// Usage: node _tests/render_audit.mjs <site-root> <out-dir> [page ...]
// Example: node _tests/render_audit.mjs . /tmp/audit / /start-reading/ /missing-page
//
// External requests (Substack embed, etc.) are blocked on purpose so results are
// repeatable offline; they are listed in the report as "external" and never loaded.
// Nothing is submitted, no form is filled, and no email is sent.
import { createRequire } from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const require = createRequire(import.meta.url);
function loadPlaywright() {
  const candidates = ['playwright', '/opt/node22/lib/node_modules/playwright'];
  for (const c of candidates) { try { return require(c); } catch {} }
  throw new Error('playwright not found; install it or set NODE_PATH');
}
const { chromium } = loadPlaywright();

const [root = '.', outDir = 'audit-out', ...pageArgs] = process.argv.slice(2);
const pages = pageArgs.length ? pageArgs : ['/'];
const siteRoot = path.resolve(root);
fs.mkdirSync(outDir, { recursive: true });

const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.webp': 'image/webp', '.png': 'image/png', '.svg': 'image/svg+xml', '.xml': 'application/xml', '.txt': 'text/plain', '.ico': 'image/x-icon' };

// Mimics GitHub Pages: /dir/ -> /dir/index.html, unknown path -> /404.html with status 404.
function serve() {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x');
    let p = decodeURIComponent(url.pathname);
    let file = path.join(siteRoot, p);
    if (!file.startsWith(siteRoot)) { res.writeHead(403); return res.end(); }
    if (fs.existsSync(file) && fs.statSync(file).isDirectory()) {
      if (!p.endsWith('/')) { res.writeHead(301, { Location: p + '/' }); return res.end(); }
      file = path.join(file, 'index.html');
    }
    if (!fs.existsSync(file) && fs.existsSync(file + '.html')) file += '.html';
    let status = 200;
    if (!fs.existsSync(file) || path.basename(file).startsWith('_') || p.split('/').some(s => s.startsWith('_'))) {
      status = 404; file = path.join(siteRoot, '404.html');
      if (!fs.existsSync(file)) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('GitHub Pages default 404'); }
    }
    const body = fs.readFileSync(file);
    res.writeHead(status, { 'content-type': TYPES[path.extname(file)] || 'application/octet-stream', 'content-length': body.length });
    res.end(body);
  });
  return new Promise(r => server.listen(0, '127.0.0.1', () => r(server)));
}

const VIEWPORTS = [
  { name: 'desktop-1366', width: 1366, height: 900 },
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'mobile-320', width: 320, height: 640 },
];

function lum(rgb) {
  const [r, g, b] = rgb.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  if (!a || !b) return null;
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
  return Math.round(((x + 0.05) / (y + 0.05)) * 100) / 100;
}

async function inspect(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const vw = doc.clientWidth;
    const overflowing = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.right > vw + 1 || r.left < -1)) {
        const cs = getComputedStyle(el);
        if (cs.position === 'absolute' && r.bottom < 0) continue; // off-screen skip link
        overflowing.push(`${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : ''} [${Math.round(r.left)}..${Math.round(r.right)}]`);
      }
    }
    return {
      title: document.title,
      clientWidth: vw,
      scrollWidth: doc.scrollWidth,
      horizontalOverflow: doc.scrollWidth > vw,
      overflowing: overflowing.slice(0, 12),
      headings: [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => `${h.tagName}: ${h.textContent.trim().replace(/\s+/g, ' ')}`),
      images: [...document.images].map(i => ({ src: i.getAttribute('src'), alt: i.getAttribute('alt'), natural: `${i.naturalWidth}x${i.naturalHeight}`, rendered: `${Math.round(i.getBoundingClientRect().width)}x${Math.round(i.getBoundingClientRect().height)}`, loading: i.getAttribute('loading') })),
      iframes: [...document.querySelectorAll('iframe')].map(f => ({ src: f.getAttribute('src'), title: f.getAttribute('title') })),
      landmarks: [...document.querySelectorAll('header,nav,main,footer,[role]')].map(e => e.tagName.toLowerCase() + (e.getAttribute('aria-label') ? `[${e.getAttribute('aria-label')}]` : '')),
      // Headings whose longest word would need a forced mid-word break to fit.
      headingWordBreaks: [...document.querySelectorAll('h1,h2,h3')].filter(h => {
        const c = h.cloneNode(true); c.style.overflowWrap = 'normal'; c.style.wordBreak = 'normal';
        c.style.position = 'absolute'; c.style.visibility = 'hidden'; c.style.width = h.clientWidth + 'px';
        h.parentElement.appendChild(c); const ok = c.scrollWidth <= c.clientWidth + 1; c.remove(); return !ok;
      }).map(h => h.tagName + ': ' + h.textContent.trim()),
      h1FontPx: (() => { const h = document.querySelector('h1'); return h ? parseFloat(getComputedStyle(h).fontSize) : null; })(),
      bodyFontPx: parseFloat(getComputedStyle(document.body).fontSize),
    };
  });
}

async function keyboardWalk(page, maxTabs = 40) {
  const stops = [];
  await page.evaluate(() => { document.activeElement && document.activeElement.blur(); window.scrollTo({ top: 0, behavior: 'instant' }); });
  for (let i = 0; i < maxTabs; i++) {
    await page.keyboard.press('Tab');
    await page.waitForTimeout(40); // let focus handlers (embed focus ring) run
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      // Smooth scrolling can leave the element mid-scroll; settle it before sampling.
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const cs = getComputedStyle(el);
      const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map(s => parseFloat(s)); if (p.length === 4 && p[3] === 0) return null; return p.slice(0, 3); };
      const r = el.getBoundingClientRect();
      // The outline paints just outside the element: sample what is actually rendered
      // there (handles absolutely positioned links such as the skip link).
      const off = parseFloat(cs.outlineOffset) || 0, w = parseFloat(cs.outlineWidth) || 0;
      const sx = Math.max(0, Math.min(innerWidth - 1, r.left - off - w / 2));
      const sy = Math.max(0, Math.min(innerHeight - 1, r.top + r.height / 2));
      let bg = null;
      let n = document.elementsFromPoint(sx, sy).find(e => e !== el && !el.contains(e)) || el.parentElement;
      while (n && !bg) { bg = parse(getComputedStyle(n).backgroundColor); n = n.parentElement; }
      return {
        tag: el.tagName.toLowerCase(), text: (el.getAttribute('aria-label') || el.textContent || el.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 60),
        href: el.getAttribute('href'), outlineStyle: cs.outlineStyle, outlineWidth: cs.outlineWidth, outline: parse(cs.outlineColor), backdrop: bg || [255, 255, 255],
        inViewport: r.top >= 0 && r.bottom <= innerHeight && r.width > 0,
      };
    });
    if (!info) break;
    if (stops.length && stops[0].href === info.href && stops[0].text === info.text) break; // wrapped
    info.focusContrast = info.outlineStyle !== 'none' ? contrast(info.outline, info.backdrop) : 0;
    stops.push(info);
  }
  return stops;
}

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: fs.existsSync('/opt/pw-browsers/chromium') ? undefined : undefined });
const report = { generated: new Date().toISOString(), siteRoot, pages: {} };

for (const p of pages) {
  const slug = p === '/' ? 'home' : p.replace(/^\/|\/$/g, '').replace(/[^a-z0-9]+/gi, '-');
  const entry = { status: null, views: {}, keyboard: {}, weight: null, reducedMotion: null };

  // Page weight and requests: fresh context, mobile viewport, no cache.
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();
    const local = [], external = [];
    await page.route('**/*', route => {
      const u = route.request().url();
      if (u.startsWith(base)) return route.continue();
      external.push(u); return route.abort();
    });
    page.on('response', async resp => {
      if (!resp.url().startsWith(base)) return;
      let size = 0; try { size = (await resp.body()).length; } catch {}
      local.push({ url: resp.url().slice(base.length), status: resp.status(), bytes: size });
    });
    await page.addInitScript(() => {
      window.__lcp = null; window.__cls = 0;
      new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lcp = { t: Math.round(e.startTime), el: e.element ? e.element.tagName + (e.element.getAttribute('src') ? ' ' + e.element.getAttribute('src') : '') : null }; }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
    });
    const resp = await page.goto(base + p, { waitUntil: 'load' });
    entry.status = resp.status();
    await page.waitForTimeout(400);
    // Scroll through so lazy images that would load for a reader are counted.
    await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); } });
    await page.waitForTimeout(300);
    const vitals = await page.evaluate(() => ({ lcp: window.__lcp, cls: Math.round(window.__cls * 1000) / 1000 }));
    entry.weight = { localRequests: local.length, localBytes: local.reduce((s, r) => s + r.bytes, 0), files: local, externalBlocked: [...new Set(external)], lcp: vitals.lcp, cls: vitals.cls };
    await ctx.close();
  }

  for (const vp of VIEWPORTS) {
    for (const zoom of [100, 200]) {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
      await page.goto(base + p, { waitUntil: 'load' });
      if (zoom === 200) await page.addStyleTag({ content: 'html{font-size:200% !important}' });
      await page.waitForTimeout(150);
      const key = `${vp.name}${zoom === 200 ? '-text200' : ''}`;
      entry.views[key] = await inspect(page);
      await page.screenshot({ path: path.join(outDir, `${slug}--${key}.png`), fullPage: true });
      if (zoom === 100 && vp.name !== 'mobile-320') entry.keyboard[vp.name] = await keyboardWalk(page);
      if (zoom === 100 && vp.name === 'desktop-1366') {
        // First focus stop (skip link) screenshot.
        await page.evaluate(() => { document.activeElement && document.activeElement.blur(); window.scrollTo({ top: 0, behavior: 'instant' }); });
        await page.keyboard.press('Tab');
        await page.screenshot({ path: path.join(outDir, `${slug}--${key}-focus1.png`) });
      }
      await ctx.close();
    }
  }
  // 200% browser page zoom at 1366 px equals a 683 px CSS viewport at DPR 2.
  {
    const ctx = await browser.newContext({ viewport: { width: 683, height: 450 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base + p, { waitUntil: 'load' });
    entry.views['desktop-1366-pagezoom200'] = await inspect(page);
    await page.screenshot({ path: path.join(outDir, `${slug}--desktop-1366-pagezoom200.png`), fullPage: true });
    await ctx.close();
  }
  {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    await page.route('**/*', route => route.request().url().startsWith(base) ? route.continue() : route.abort());
    await page.goto(base + p, { waitUntil: 'load' });
    entry.reducedMotion = await page.evaluate(() => {
      const moving = [...document.querySelectorAll('*')].filter(e => { const cs = getComputedStyle(e); return (parseFloat(cs.animationDuration) > 0.01 && cs.animationName !== 'none') || parseFloat(cs.transitionDuration) > 0.01; }).map(e => e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : ''));
      return { scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior, animatedOrTransitioning: moving.slice(0, 10) };
    });
    await ctx.close();
  }
  report.pages[p] = entry;
}

await browser.close();
server.close();
fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify(report, null, 2));

// Short console summary.
for (const [p, e] of Object.entries(report.pages)) {
  console.log(`\n== ${p}  status ${e.status}`);
  console.log(`   weight: ${e.weight.localRequests} local requests, ${e.weight.localBytes} B; external blocked: ${e.weight.externalBlocked.length}; LCP ${e.weight.lcp && e.weight.lcp.t}ms (${e.weight.lcp && e.weight.lcp.el}); CLS ${e.weight.cls}`);
  for (const [k, v] of Object.entries(e.views)) console.log(`   ${k.padEnd(28)} scroll ${v.scrollWidth}/${v.clientWidth}${v.horizontalOverflow ? '  OVERFLOW ' + v.overflowing.slice(0, 3).join(' | ') : ''}${v.headingWordBreaks.length ? '  WORD-BREAK ' + v.headingWordBreaks.join(' | ') : ''}  h1 ${v.h1FontPx}px`);
  for (const [k, stops] of Object.entries(e.keyboard)) {
    const weak = stops.filter(s => s.focusContrast !== null && s.focusContrast < 3);
    console.log(`   keyboard ${k}: ${stops.length} stops; min focus contrast ${Math.min(...stops.map(s => s.focusContrast ?? 99))}; weak ${weak.length}${weak.length ? ' -> ' + weak.map(s => s.text).join(', ') : ''}`);
  }
  console.log(`   reduced motion: ${JSON.stringify(e.reducedMotion)}`);
}

// Fail (exit 1) on regressions so this can gate a change: horizontal overflow, headings
// that need mid-word breaks, focus indicators under 3:1, missing focus ring, or a public
// page that does not return 200.
const failures = [];
for (const [p, e] of Object.entries(report.pages)) {
  const expect404 = /no-such|missing|404/.test(p);
  if (expect404 ? e.status !== 404 : e.status !== 200) failures.push(`${p}: status ${e.status}`);
  for (const [k, v] of Object.entries(e.views)) {
    if (v.horizontalOverflow) failures.push(`${p} ${k}: horizontal overflow ${v.scrollWidth}/${v.clientWidth}`);
    if (v.headingWordBreaks.length) failures.push(`${p} ${k}: heading word breaks ${v.headingWordBreaks.join(' | ')}`);
  }
  for (const [k, stops] of Object.entries(e.keyboard)) {
    for (const s of stops) if (s.focusContrast !== null && s.focusContrast < 3) failures.push(`${p} ${k}: weak focus on "${s.text}" (${s.focusContrast})`);
    if (stops.length && stops[0].href !== '#main') failures.push(`${p} ${k}: first focus stop is not the skip link`);
  }
  if (e.reducedMotion.scrollBehavior !== 'auto' || e.reducedMotion.animatedOrTransitioning.length) failures.push(`${p}: motion under prefers-reduced-motion`);
}
if (failures.length) { console.error('\nFAILURES:\n' + failures.join('\n')); process.exit(1); }
console.log('\nRendered audit: no failures.');
