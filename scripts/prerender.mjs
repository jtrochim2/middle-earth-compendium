// Builds the published site in site/: a copy of dist/ plus one pre-rendered page per army
// (site/army/<id>/index.html), so search engines and link previews get real HTML.
// Each page is rendered by the app itself in headless Chrome, then given its own
// description, canonical URL, Open Graph tags and structured data. Also writes
// sitemap.xml and 404.html. Run: node scripts/prerender.mjs (CHROME_PATH overrides
// the browser).
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const SITE_URL = 'https://mesbgarmybook.com';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const dist = path.join(root, 'dist'), out = path.join(root, 'site');
const require = createRequire(import.meta.url);
require(path.join(dist, 'model.js'));
const data = globalThis.RosterModel.withoutLegacy(require(path.join(dist, 'data.json')));

const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const armyProfiles = a => data.profiles.filter(p => p.armies.some(x => x.army === a.id));

function findChrome() {
  const candidates = [process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  const found = candidates.find(c => c && fs.existsSync(c));
  if (!found) throw Error('Chrome not found; set CHROME_PATH.');
  return found;
}

// Serves dist/; army paths fall back to index.html, as the app routes them itself.
const types = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml'};
const server = createServer((req, res) => {
  let file = path.join(dist, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!file.startsWith(dist)) { res.writeHead(403).end(); return; }
  if (/^\/army\/[^/]+\/$/.test(new URL(req.url, 'http://x').pathname) || file.endsWith(path.sep)) file = path.join(dist, 'index.html');
  fs.readFile(file, (err, body) => {
    if (err) { res.writeHead(404).end(); return; }
    res.writeHead(200, {'Content-Type': types[path.extname(file)] || 'application/octet-stream'}).end(body);
  });
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const chrome = findChrome();
// Every Chrome still running is stopped when the script exits, including after a failure.
const running = new Set();
process.on('exit', () => { for (const p of running) p.kill('SIGKILL'); });
// Chrome occasionally exits without printing the page; retry before failing the build.
async function render(urlPath) {
  for (let attempt = 1; ; attempt++) {
    try { return await renderOnce(urlPath); } catch (e) { if (attempt === 3) throw e; }
  }
}
function renderOnce(urlPath) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'prerender-'));
  return new Promise((resolve, reject) => {
    const args = ['--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run', `--user-data-dir=${profile}`, '--virtual-time-budget=15000', '--dump-dom', base + urlPath];
    const p = spawn(chrome, args, {stdio: ['ignore', 'pipe', 'ignore']});
    running.add(p);
    let html = '';
    // With a fresh profile Chrome may stay open after printing the page, so stop it once the page is out.
    const timer = setTimeout(() => p.kill('SIGKILL'), 60000);
    p.stdout.on('data', d => { html += d; if (/<\/html>\s*$/i.test(html)) p.kill('SIGKILL'); });
    p.on('close', () => {
      running.delete(p);
      clearTimeout(timer);
      fs.rmSync(profile, {recursive: true, force: true});
      /<\/html>\s*$/i.test(html) ? resolve(html) : reject(Error(`Chrome returned no page for ${urlPath}`));
    });
  });
}

// Removes what the app adds at runtime that a fresh page load would duplicate.
function clean(html) {
  html = html.replace(/<div id="rule-tip"[^>]*><\/div>/, '').replace(/<html([^>]*?) style="[^"]*"/, '<html$1');
  return /^<!doctype/i.test(html) ? html : '<!doctype html>' + html;
}

function headTags({title, description, url, jsonLd}) {
  const image = SITE_URL + '/assets/mesbg-army-book.png';
  return [
    `<link rel="canonical" href="${esc(url)}">`,
    `<meta property="og:type" content="website">`,
    `<meta property="og:site_name" content="MESBG Army Book">`,
    `<meta property="og:title" content="${esc(title)}">`,
    `<meta property="og:description" content="${esc(description)}">`,
    `<meta property="og:url" content="${esc(url)}">`,
    `<meta property="og:image" content="${image}">`,
    `<meta property="og:image:width" content="2048">`,
    `<meta property="og:image:height" content="768">`,
    `<meta name="twitter:card" content="summary_large_image">`,
    `<script type="application/ld+json">${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>`,
  ].join('');
}

function finish(html, meta) {
  html = clean(html);
  const desc = /<meta name="description" content="[^"]*">/;
  if (!desc.test(html)) throw Error('No meta description in ' + meta.url);
  html = html.replace(desc, `<meta name="description" content="${esc(meta.description)}">`);
  return html.replace('</head>', headTags(meta) + '</head>');
}

function armyDescription(a) {
  const ps = armyProfiles(a), heroes = ps.filter(p => p.role === 'Hero').sort((x, y) => y.points - x.points).map(p => p.name);
  const named = [...new Set(heroes)].slice(0, 3);
  return `${a.name} (Forces of ${a.side}) for the Middle-earth Strategy Battle Game: ${ps.length} profiles with stats, points and equipment, plus army rules.${named.length ? ` Heroes: ${named.join(' · ')}.` : ''}`;
}

function check(html, a) {
  const title = html.match(/<h1 id="army-title">([^<]*)<\/h1>/)?.[1];
  if (title !== a.name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')) throw Error(`Page for ${a.id} rendered "${title}" instead of its army.`);
  if (/<div id="repository" hidden/.test(html) || !/class="profile-card"/.test(html)) throw Error(`Page for ${a.id} has no profiles.`);
  if (!/<div id="load-error" role="alert" hidden/.test(html)) throw Error(`Page for ${a.id} shows the load error; check the browser console.`);
  if (data.armies.some(x => !html.includes(`href="/army/${x.id}/"`))) throw Error(`Page for ${a.id} is missing links to other armies.`);
}

fs.rmSync(out, {recursive: true, force: true});
fs.cpSync(dist, out, {recursive: true});

const pages = [{path: '/', army: null}, ...data.armies.map(a => ({path: `/army/${a.id}/`, army: a}))];
let next = 0;
async function worker() {
  while (next < pages.length) {
    const page = pages[next++], a = page.army;
    const url = SITE_URL + page.path;
    let html = await render(page.path);
    if (a) {
      check(html, a);
      html = finish(html, {
        title: `${a.name} — Profiles & Army Rules | MESBG Army Book`, description: armyDescription(a), url,
        jsonLd: {'@context': 'https://schema.org', '@type': 'BreadcrumbList', itemListElement: [
          {'@type': 'ListItem', position: 1, name: 'MESBG Army Book', item: SITE_URL + '/'},
          {'@type': 'ListItem', position: 2, name: a.name, item: url}]},
      });
      fs.mkdirSync(path.join(out, 'army', a.id), {recursive: true});
      fs.writeFileSync(path.join(out, 'army', a.id, 'index.html'), html);
    } else {
      check(html, data.armies.find(x => x.id === 'riders-of-theoden'));
      const description = `An unofficial fan reference for the Middle-earth Strategy Battle Game: browse all ${data.armies.length} armies and ${data.profiles.length} hero and warrior profiles with stats, points and rules, and build your warbands.`;
      html = finish(html, {
        title: 'MESBG Army Book — Unofficial Armies, Profiles & Warband Builder', description, url,
        jsonLd: {'@context': 'https://schema.org', '@type': 'WebSite', name: 'MESBG Army Book', url: SITE_URL + '/'},
      });
      fs.writeFileSync(path.join(out, 'index.html'), html);
    }
    process.stdout.write('.');
  }
}
try {
  await Promise.all(Array.from({length: Math.min(6, os.cpus().length)}, worker));
} finally {
  server.close();
}

// Unknown paths get the plain app (it shows the default army), kept out of search results.
fs.writeFileSync(path.join(out, '404.html'), fs.readFileSync(path.join(dist, 'index.html'), 'utf8').replace('<head>', '<head><meta name="robots" content="noindex">'));
fs.writeFileSync(path.join(out, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${pages.map(p => `  <url><loc>${SITE_URL}${p.path}</loc></url>`).join('\n')}\n</urlset>\n`);
console.log(`\n${pages.length} pages pre-rendered into site/.`);
