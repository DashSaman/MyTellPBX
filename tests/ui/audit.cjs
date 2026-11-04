/* Real-browser visual inventory. No configuration submission or call generation.
 * Required: MT_BASE_URL, MT_PANEL_SESSION. Desk auth comes from an external
 * MT_DESK_PASSWORD_FILE. Evidence is private by default, not a public fixture.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.MT_PLAYWRIGHT_MODULE || 'playwright-core');
const BASE = process.env.MT_BASE_URL;
if (!BASE) throw new Error('MT_BASE_URL is required');
const ORIGIN = new URL(BASE).origin;
const OUTPUT = path.resolve(process.env.MT_EVIDENCE_DIR || 'ui-evidence');
const CANDIDATE = process.env.MT_CANDIDATE_ROOT ? path.resolve(process.env.MT_CANDIDATE_ROOT) : null;
const BUILD = process.env.MT_BUILD_ROOT ? path.resolve(process.env.MT_BUILD_ROOT) : null;
const ARTIFACT = process.env.MT_ARTIFACT_ROOT ? path.resolve(process.env.MT_ARTIFACT_ROOT) : null;
const artifactFiles = new Map();
const artifactInputs = new Set();
let manifestHash = null;
if (ARTIFACT) {
  const bytes = fs.readFileSync(path.join(ARTIFACT, 'manifest.json'));
  manifestHash = crypto.createHash('sha256').update(bytes).digest('hex');
  const manifest = JSON.parse(bytes);
  for (const item of manifest.inputs || []) artifactInputs.add(item.root + ':' + item.path);
  for (const item of manifest.files) {
    const data = fs.readFileSync(path.join(ARTIFACT, item.payload));
    if (data.length !== item.size || crypto.createHash('sha256').update(data).digest('hex') !== item.after) throw new Error('Artifact payload mismatch');
    const prefix = { panel: '/themes/mytel/', admin: '/admin/', phone: '/Phone/', desk: '/MytellDesk/', legacy: '/' }[item.root];
    if (!prefix) throw new Error('Unknown artifact UI root');
    if (item.root !== 'desk' || item.path.startsWith('dist/')) artifactFiles.set(prefix + item.path.replace(/^dist\//, ''), data);
  }
}
const SMOKE = process.argv.includes('--smoke');
const ONLY = process.env.MT_SURFACES ? process.env.MT_SURFACES.split(',') : ['panel', 'admin', 'desk', 'phone'];
const THEMES = process.env.MT_THEMES ? process.env.MT_THEMES.split(',') : ['light', 'dark'];
const WIDTHS = process.env.MT_WIDTHS ? process.env.MT_WIDTHS.split(',').map(Number) : [1440, 390];
fs.mkdirSync(OUTPUT, { recursive: true, mode: 0o700 });

function safeURL(url) {
  const u = new URL(url);
  // Do not retain authorization fragments, WS tokens or customer query values.
  return u.pathname + (u.searchParams.has('menu') ? '?menu=' + u.searchParams.get('menu') : u.searchParams.has('display') ? '?display=' + u.searchParams.get('display') : '');
}

function contentType(file) {
  return file.endsWith('.css') ? 'text/css' : file.endsWith('.js') ? 'application/javascript' : file.endsWith('.html') ? 'text/html' : undefined;
}

function previewGeoipHome(html, template) {
  const fragment = /homePolygon\s*=\s*polygonSeries\.getPolygonById\(home\);(?:\s*if \(!homePolygon\) return;)?\s*homeLatitude\s*=\s*homePolygon\.visualLatitude;\s*homeLongitude\s*=\s*homePolygon\.visualLongitude;/g;
  const patches = template.match(fragment) || [];
  const originals = html.match(fragment) || [];
  if (patches.length !== 2 || originals.length !== 2 || patches.some(patch => !patch.includes('if (!homePolygon) return;'))) throw new Error('GeoIP template preview anchors changed');
  let index = 0;
  return html.replace(fragment, () => patches[index++]);
}

async function installRoutes(context, events) {
  if (typeof context.routeWebSocket !== 'function') throw new Error('Read-only audits require Playwright WebSocket routing');
  await context.routeWebSocket('**/*', socket => {
    if (!events.webSockets) events.webSockets = [];
    events.webSockets.push({ case: events.currentCase || 'discovery', path: safeURL(socket.url()) });
    // Never connect the intercepted socket to production, including SIP/AMI.
    return socket.close();
  });
  await context.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== ORIGIN) {
      events.external.add(url.origin);
      return route.abort('blockedbyclient');
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) {
      events.blocked.push({ case: events.currentCase || 'discovery', method: request.method(), path: safeURL(request.url()) });
      // Optional telemetry must not write production logs during a visual audit.
      return route.fulfill({ status: 405, contentType: 'application/json', body: '{"message":"Read-only visual audit"}' });
    }
    if (!CANDIDATE && !ARTIFACT) return route.continue();
    if (artifactFiles.has(url.pathname)) return route.fulfill({ status: 200, contentType: contentType(url.pathname), body: artifactFiles.get(url.pathname) });
    if (ARTIFACT && url.pathname === '/admin/config.php' && url.searchParams.get('handler') === 'file' && url.searchParams.get('module') === 'asternic_cdr' && url.searchParams.get('file') === 'asternic_cdr.css') {
      const stylesheet = artifactFiles.get('/admin/modules/asternic_cdr/asternic_cdr.css');
      if (stylesheet) return route.fulfill({ status: 200, contentType: 'text/css', body: stylesheet });
    }
    const replacements = {
      '/themes/mytel/css/tokens.css': 'theme/css/tokens.css',
      '/themes/mytel/css/workspace.css': 'theme/css/workspace.css',
      '/themes/mytel/js/theme.js': 'theme/js/theme.js',
      '/themes/mytel/js/mytel-charts.js': 'theme/js/mytel-charts.js',
      '/themes/mytel/js/workspace.js': 'theme/js/workspace.js',
      '/themes/mytel/js/appearance.js': 'theme/js/appearance.js',
      '/themes/mytel/styles.css': 'theme/styles.css',
      '/themes/mytel/help.css': 'theme/help.css',
      '/admin/assets/mytel/workspace.css': 'admin-theme/workspace.css',
      '/admin/assets/mytel/workspace.js': 'admin-theme/workspace.js',
      '/Phone/workspace.css': 'webphone/workspace.css',
      '/Phone/theme.js': 'webphone/theme.js',
    };
    if (!ARTIFACT && replacements[url.pathname]) {
      const file = path.join(CANDIDATE, replacements[url.pathname]);
      return route.fulfill({ status: 200, contentType: contentType(file), body: fs.readFileSync(file) });
    }
    if (!ARTIFACT && url.pathname === '/admin/assets/mytel/skin.css' && BUILD) {
      return route.fulfill({ status: 200, contentType: 'text/css', body: fs.readFileSync(path.join(BUILD, 'admin/assets/mytel/skin.css')) });
    }
    if (!ARTIFACT && url.pathname.startsWith('/MytellDesk/assets/') && BUILD) {
      const filename = path.basename(url.pathname);
      const file = path.join(BUILD, 'frontend/dist/assets', filename);
      if (fs.existsSync(file)) return route.fulfill({ status: 200, contentType: contentType(file), body: fs.readFileSync(file) });
    }
    if (request.isNavigationRequest() && request.resourceType() === 'document') {
      if (url.pathname.startsWith('/MytellDesk/') && !url.pathname.startsWith('/MytellDesk/api/') && (ARTIFACT || BUILD)) {
        const body = ARTIFACT ? artifactFiles.get('/MytellDesk/index.html') : fs.readFileSync(path.join(BUILD, 'frontend/dist/index.html'));
        if (!body) {
          if (artifactInputs.has('desk:dist/index.html')) return route.continue();
          throw new Error('Missing artifact desk document');
        }
        return route.fulfill({ status: 200, contentType: 'text/html', body });
      }
      if (url.pathname === '/Phone/' && (ARTIFACT || BUILD)) {
        const body = ARTIFACT ? artifactFiles.get('/Phone/index.html') : fs.readFileSync(path.join(BUILD, 'phone/index.html'));
        if (!body) {
          if (artifactInputs.has('phone:index.html')) return route.continue();
          throw new Error('Missing artifact phone document');
        }
        return route.fulfill({ status: 200, contentType: 'text/html', body });
      }
      // Do not flatten redirects (notably /mail -> /mail/) or alter unrelated
      // applications. Relative scripts must resolve at the browser's real URL.
      if (!(url.pathname === '/' || url.pathname === '/index.php' || url.pathname.startsWith('/admin/'))) return route.continue();
      let response;
      try { response = await route.fetch({ maxRedirects: 0 }); }
      catch (error) {
        // Record a real failure and let goto fail, but do not kill unrelated
        // remaining cases with an unhandled asynchronous route rejection.
        if (!events.routeErrors) events.routeErrors = [];
        events.routeErrors.push({ key: events.currentCase || 'discovery', path: safeURL(request.url()), error: 'Document fetch failed' });
        await route.abort('failed').catch(() => {});
        return;
      }
      if (response.status() >= 300 && response.status() < 400) return route.fulfill({ response });
      if (!(response.headers()['content-type'] || '').includes('text/html')) return route.fulfill({ response });
      let html = await response.text();
      if (ARTIFACT && url.searchParams.get('menu') === 'sec_geoip_map') {
        const template = artifactFiles.get('/modules/sec_geoip_map/themes/default/map.tpl');
        if (template) html = previewGeoipHome(html, template.toString('utf8'));
      }
      if (url.pathname.startsWith('/admin/') && (!ARTIFACT || artifactFiles.has('/admin/views/header.php'))) {
        // Mirror the PHP migration without editing a served file.
        html = html.replace(/<!-- MyTellPBX theme pre-paint[^>]*-->\s*<script>[\s\S]*?<\/script>\s*(?:<script>\(function\(\)\{var btn=null;[\s\S]*?<\/script>)?/, '');
        html = html.replace(/<script>\/\* MyTellPBX standalone theme toggle[\s\S]*?<\/script>/, '');
        html = html.replace('<head>', '<head><script src="assets/mytel/workspace.js?v=740"></script>');
        html = html.replace('</head>', '<link rel="stylesheet" href="assets/mytel/workspace.css?v=740"></head>');
        html = html.replace('https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css', '/libs/font-icons/font-awesome/css/font-awesome.min.css');
      } else if ((html.includes('mt-body') || html.includes('mt-login-body')) && (!ARTIFACT || artifactFiles.has('/themes/mytel/_common/index.tpl'))) {
        html = html.replace('</head>', '<link rel="stylesheet" href="/themes/mytel/css/workspace.css?v=740"></head>');
        html = html.replace('</body>', '<script src="/themes/mytel/js/workspace.js?v=740"></script></body>');
        const shellBody = /<body\b[^>]*\bclass=["'][^"']*\bmt-body\b[^"']*["'][^>]*>/i;
        if (shellBody.test(html)) {
          const template = relative => {
            const bytes = ARTIFACT ? artifactFiles.get('/themes/mytel/_common/' + relative)
              : fs.readFileSync(path.join(CANDIDATE, 'theme/_common', relative));
            if (!bytes) throw new Error('Missing artifact panel template: ' + relative);
            return bytes.toString('utf8');
          };
          const skip = template('index.tpl').match(/<a\b[^>]*class="mt-skip-link"[^>]*>[\s\S]*?<\/a>/);
          const burger = template('_menu.tpl').match(/<button\b[^>]*id="mt-burger"[^>]*>/);
          if (!skip || !burger) throw new Error('Missing panel accessibility preview anchors');
          html = html.replace(shellBody, tag => tag + '\n' + skip[0]);
          html = html.replace(/<button\b[^>]*id="mt-burger"[^>]*>/, burger[0]);
        }
        html = html.replace(/(<button[^>]*id="mt-burger"[\s\S]*?<\/button>)/, '$1<div class="mt-topbar-context"><small>سامانه مدیریت مرکز تماس</small><strong id="mt-page-context"></strong></div>');
        html = html.replace('<div id="neo-contentbox-maincolumn">', '<div id="neo-contentbox-maincolumn" tabindex="-1">');
        // Candidate legacy list wrapper; the production template is separately
        // checked after deployment, including its colResizable initialization.
        html = html.replace(/(<table class="issabel-standard-table"[\s\S]*?<\/table>)/g, '<div class="mt-table-scroll" role="region" tabindex="0" aria-label="فهرست اطلاعات">$1</div>');
        html = html.replace(/form\.issabel-standard-formgrid>table\.issabel-standard-table/g, 'form.issabel-standard-formgrid>.mt-table-scroll>table.issabel-standard-table');
      }
      return route.fulfill({ response, body: html });
    }
    return route.continue();
  });
}

/* Resolved text contrast, with ancestor alpha composition. Gradient and canvas
 * pixels require screenshot review and are not falsely reported as AA-passing. */
function inspectDOM() {
  const root = document.documentElement;
  const theme = root.dataset.mtTheme || root.dataset.theme || 'unknown';
  const colorCanvas = document.createElement('canvas');
  colorCanvas.width = colorCanvas.height = 1;
  const colorContext = colorCanvas.getContext('2d', { willReadFrequently: true });
  const colorCache = new Map();
  const rgba = color => {
    if (colorCache.has(color)) return colorCache.get(color);
    if (!color || !CSS.supports('color', color)) return null;
    if (!/^rgba?\(/.test(color)) {
      colorContext.clearRect(0, 0, 1, 1);
      colorContext.fillStyle = color;
      colorContext.fillRect(0, 0, 1, 1);
      const data = [...colorContext.getImageData(0, 0, 1, 1).data];
      const result = data.slice(0, 3).concat(data[3] / 255);
      colorCache.set(color, result);
      return result;
    }
    const values = String(color).match(/[\d.]+/g);
    const result = values && values.length >= 3 ? values.map(Number).slice(0, 4) : null;
    colorCache.set(color, result);
    return result;
  };
  const mix = (front, back) => {
    const a = front.length === 4 ? front[3] : 1;
    return [0, 1, 2].map(i => front[i] * a + back[i] * (1 - a));
  };
  const lum = c => c.slice(0, 3).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((v, n, i) => v + n * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => (Math.max(lum(a), lum(b)) + .05) / (Math.min(lum(a), lum(b)) + .05);
  function selector(el) {
    const parts = [];
    for (let node = el; node && node !== document.body; node = node.parentElement) {
      let part = node.tagName.toLowerCase();
      if (node.id) part += '#' + CSS.escape(node.id);
      else if (typeof node.className === 'string' && node.className.trim()) part += '.' + node.className.trim().split(/\s+/).slice(0, 2).map(CSS.escape).join('.');
      parts.unshift(part);
      if (document.querySelectorAll(parts.join(' > ')).length === 1) return parts.join(' > ');
      const siblings = node.parentElement ? [...node.parentElement.children].filter(sibling => sibling.tagName === node.tagName) : [];
      if (siblings.length > 1) parts[0] += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      if (parts.length >= 5) break;
    }
    return parts.join(' > ');
  }
  function visible(el) {
    if (!el.getClientRects().length || el.closest('[hidden], [inert], [aria-hidden="true"]')) return false;
    for (let p = el; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) < .1) return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.right > 0 && r.left < innerWidth && r.bottom > 0;
  }
  function background(el) {
    const layers = [];
    for (let p = el; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.backgroundImage !== 'none') return null;
      const color = rgba(s.backgroundColor);
      if (color) layers.unshift(color);
    }
    return layers.reduce((value, layer) => mix(layer, value), theme === 'dark' ? [12, 20, 34] : [255, 255, 255]);
  }
  const lowContrast = [], seen = new Set();
  let checked = 0, gradientText = 0;
  function check(el, color, kind) {
    if (!visible(el) || el.closest('svg, canvas, .fa, .glyphicon, .ti') || el.matches(':disabled, [aria-disabled="true"]')) return;
    const s = getComputedStyle(el);
    const fg = rgba(color || s.color), bg = background(el);
    if (!bg || !fg || (fg.length === 4 && fg[3] === 0)) { gradientText++; return; }
    const effective = mix(fg, bg);
    const minimum = Number.parseFloat(s.fontSize) >= 24 || (Number.parseFloat(s.fontSize) >= 18.66 && Number(s.fontWeight) >= 700) ? 3 : 4.5;
    const score = ratio(effective, bg);
    checked++;
    if (score + .03 < minimum) {
      const key = selector(el) + ':' + color + ':' + bg.join(',');
      if (!seen.has(key)) { seen.add(key); lowContrast.push({ selector: selector(el), kind, ratio: +score.toFixed(2), required: minimum, fg: color || s.color, bg: bg.map(Math.round) }); }
    }
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    if (!node.nodeValue.trim()) continue;
    const el = node.parentElement;
    if (!el || el.closest('script, style, option, select, textarea, noscript')) continue;
    check(el, null, 'text');
  }
  document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]), select, textarea').forEach(el => {
    check(el, getComputedStyle(el).color, 'control');
    if (!el.value && el.placeholder) check(el, getComputedStyle(el, '::placeholder').color, 'placeholder');
  });
  const lightBlocks = [], overflow = [];
  document.querySelectorAll('body *').forEach(el => {
    if (!visible(el)) return;
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    const color = rgba(s.backgroundColor);
    // QR codes deliberately keep their white quiet zone in both themes.
    if (theme === 'dark' && color && (color.length < 4 || color[3] > .8) && lum(color) > .8 && r.width > 120 && r.height > 28 && !el.closest('.mt-brand, .mt-login-brandpane, .acct-qr-code')) lightBlocks.push({ selector: selector(el), width: Math.round(r.width), height: Math.round(r.height), background: s.backgroundColor });
    if (r.width > innerWidth + 8 && !el.closest('.dataTables_wrapper, .mt-table-scroll, .mt-cdr-table-scroll, .ui-table-wrap, .table-container') && !['absolute', 'fixed'].includes(s.position)) overflow.push({ selector: selector(el), width: Math.round(r.width), scrollable: ['auto', 'scroll'].includes(s.overflowX) });
  });
  return {
    theme, direction: getComputedStyle(document.body).direction,
    font: getComputedStyle(document.body).fontFamily,
    title: document.title,
    documentOverflow: Math.max(document.body.scrollWidth, root.scrollWidth) - innerWidth,
    lowContrast, checkedText: checked, gradientText, lightBlocks: lightBlocks.slice(0, 25), wideElements: overflow.slice(0, 20),
    bodyLength: document.body.innerText.trim().length,
    login: !!document.querySelector('#input_user'),
    module: document.getElementById('issabel_framework_module_id')?.value || null,
    unavailable: /(?:DB Error:|SQLSTATE\[|Fatal error:|Call to undefined function|not (?:currently )?installed|module (?:is )?not found)/i.test(document.body.innerText),
    themeIcons: [...document.querySelectorAll('.mt-theme-toggle, .mt-admin-theme-toggle, .theme-toggle, .mt-phone-theme-toggle')].map(b => ({ visible: visible(b), icon: !!b.querySelector('svg'), name: b.getAttribute('aria-label'), pressed: b.getAttribute('aria-pressed') })),
  };
}

async function settle(page, item) {
  await page.waitForLoadState('networkidle', { timeout: 3500 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  if (item.surface === 'desk') await page.locator('.app, .login-page').waitFor({ state: 'visible', timeout: 15000 });
  if (item.name === 'dashboard' && item.surface === 'panel') await page.locator('#mt-dash').waitFor({ state: 'visible', timeout: 12000 });
  if (item.name === 'email_template' && item.surface === 'panel') await page.locator('.mt-tpl').waitFor({ state: 'visible', timeout: 12000 });
  if (item.name === 'calendar' && item.surface === 'panel') {
    await page.locator('#calendar_main.mt-jmonth-active .mt-jmonth-table tbody tr').first().waitFor({ state: 'visible', timeout: 12000 });
    await page.locator('.mt-calside[data-mt-key] .mt-mini[data-d]').first().waitFor({ state: 'visible', timeout: 12000 });
  }
}

async function deskAuth(context) {
  if (!process.env.MT_DESK_PASSWORD_FILE) return null;
  const password = fs.readFileSync(process.env.MT_DESK_PASSWORD_FILE, 'utf8').trim().replace(/^OPDESK_BRIDGE_PW=/, '');
  const response = await context.request.post(ORIGIN + '/MytellDesk/api/auth/login', { data: { login: process.env.MT_DESK_USERNAME || 'admin', password } });
  if (!response.ok()) throw new Error('Desk authentication failed: ' + response.status());
  const data = await response.json();
  if (!data.access_token) throw new Error('Desk authentication returned no access token');
  return { token: data.access_token, user: data.user };
}

async function inventory(context) {
  const page = await context.newPage();
  const items = [];
  await page.goto(ORIGIN + '/index.php?menu=dashboard', { waitUntil: 'domcontentloaded' });
  await page.locator('#main-menu').waitFor();
  const panels = await page.locator('#main-menu a[href*="menu="]').evaluateAll(links => links.map(a => ({ href: a.getAttribute('href'), label: a.textContent.trim() })));
  const panelNames = new Set();
  for (const item of panels) {
    const u = new URL(item.href, ORIGIN);
    const name = u.searchParams.get('menu');
    if (!panelNames.has(name) && /^[\w-]+$/.test(name)) { panelNames.add(name); items.push({ surface: 'panel', name, path: '/index.php?menu=' + name }); }
  }
  await page.goto(ORIGIN + '/admin/config.php?display=extensions', { waitUntil: 'domcontentloaded' });
  const admins = await page.locator('.navbar-dropdown a[href*="display="]').evaluateAll(links => links.map(a => a.getAttribute('href')));
  const adminPaths = new Set();
  for (const href of admins) {
    const u = new URL(href, ORIGIN + '/admin/');
    const name = u.searchParams.get('display');
    if (u.pathname.endsWith('/config.php') && /^[\w-]+$/.test(name) && !adminPaths.has(u.pathname + u.search)) {
      adminPaths.add(u.pathname + u.search);
      items.push({ surface: 'admin', name, path: u.pathname + u.search });
    }
  }
  // These are route constants from App.tsx and SettingsPanel.tsx, not guessed URLs.
  for (const name of ['dashboard', 'extensions', 'calls', 'queues', 'call-log', 'contacts', 'groups', 'users', 'analytics', 'recordings', 'logs', 'settings', 'profile']) items.push({ surface: 'desk', name, path: '/MytellDesk/' + name });
  for (const tab of ['integrations', 'api-keys', 'qos', 'analytics', 'sip-tls', 'codecs', 'mobile-wake', 'recording', 'not-ready-codes']) items.push({ surface: 'desk', name: 'settings-' + tab, path: '/MytellDesk/settings?tab=' + tab });
  for (const name of ['panel-login', 'desk-login', 'phone-login']) items.push({ surface: name.startsWith('panel') ? 'panel' : name.startsWith('desk') ? 'desk' : 'phone', name, path: name.startsWith('panel') ? '/index.php?menu=dashboard' : name.startsWith('desk') ? '/MytellDesk/' : '/Phone/', anonymous: true });
  await page.close();
  const include = process.env.MT_INCLUDE ? process.env.MT_INCLUDE.split(',') : null;
  return items.filter(item => ONLY.includes(item.surface))
    .filter(item => !include || include.includes(item.name) || include.includes(item.surface + ':' + item.name))
    .filter(item => !SMOKE || (item.surface === 'panel' ? ['dashboard', 'cdrreport', 'userlist', 'calendar', 'sec_advanced_settings', 'panel-login', 'pbxadmin'].includes(item.name) : item.surface === 'admin' ? ['extensions', 'advancedsettings', 'sipsettings', 'queues', 'dahdi'].includes(item.name) : item.surface === 'desk' ? ['dashboard', 'extensions', 'call-log', 'settings', 'settings-recording', 'desk-login'].includes(item.name) : true));
}

function hasFindings(item) {
  return !!(item.error || item.status >= 400 || item.unavailable || item.documentOverflow > 3 ||
    item.lightBlocks?.length || item.lowContrast?.length || item.pageErrors?.length || item.resources?.length ||
    (item.surface === 'admin' && item.direction !== 'ltr') ||
    item.frames?.some(frame => hasFindings({ ...frame, surface: new URL(frame.path, ORIGIN).pathname.startsWith('/admin/') ? 'admin' : frame.surface })));
}

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.MT_CHROMIUM_PATH || undefined, args: process.env.MT_CHROMIUM_NO_SANDBOX === '1' ? ['--no-sandbox', '--disable-dev-shm-usage'] : [] });
  const report = { mode: CANDIDATE || ARTIFACT ? 'candidate-response-overrides' : 'live', artifactManifestSha256: manifestHash, harnessSha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'), started: new Date().toISOString(), inventory: [], cases: [], errors: [], blockedWrites: [], blockedWebSockets: [], externalOrigins: [] };
  try {
    const discovery = await browser.newContext({ ignoreHTTPSErrors: process.env.MT_SELF_SIGNED === '1', serviceWorkers: 'block' });
    await discovery.addCookies([{ name: 'issabelSession', value: process.env.MT_PANEL_SESSION || '', url: ORIGIN }]);
    const discoveryEvents = { external: new Set(), blocked: [] };
    await installRoutes(discovery, discoveryEvents);
    report.inventory = await inventory(discovery);
    const auth = ONLY.includes('desk') ? await deskAuth(discovery) : null;
    report.blockedWrites.push(...discoveryEvents.blocked);
    report.errors.push(...(discoveryEvents.routeErrors || []));
    report.blockedWebSockets.push(...(discoveryEvents.webSockets || []));
    report.externalOrigins.push(...discoveryEvents.external);
    await discovery.close();
    fs.writeFileSync(path.join(OUTPUT, 'inventory.json'), JSON.stringify(report.inventory, null, 2));
    for (const width of WIDTHS) for (const theme of THEMES) {
      const context = await browser.newContext({ ignoreHTTPSErrors: process.env.MT_SELF_SIGNED === '1', viewport: { width, height: width < 700 ? 844 : 1000 }, serviceWorkers: 'block', reducedMotion: 'reduce' });
      const events = { external: new Set(), blocked: [] };
      await installRoutes(context, events);
      await context.addCookies([{ name: 'issabelSession', value: process.env.MT_PANEL_SESSION || '', url: ORIGIN }]);
      await context.addInitScript(({ theme, auth }) => {
        localStorage.setItem('mt-theme', theme); localStorage.setItem('opdesk:theme', theme);
        if (auth) { localStorage.setItem('opdesk_token', auth.token); localStorage.setItem('opdesk_user', JSON.stringify(auth.user)); }
      }, { theme, auth });
      const page = await context.newPage();
      let pageErrors = [], resources = [];
      page.on('pageerror', error => pageErrors.push(error.message.slice(0, 300)));
      page.on('response', response => { if (response.status() >= 400 && new URL(response.url()).origin === ORIGIN) resources.push({ status: response.status(), path: safeURL(response.url()) }); });
      page.on('requestfailed', request => { if (request.resourceType() === 'document') resources.push({ error: 'Document load failed', path: safeURL(request.url()) }); });
      for (const item of report.inventory) {
        const key = [item.surface, item.name, theme, width].join('-');
        events.currentCase = key;
        pageErrors = []; resources = [];
        try {
          let active = page;
          let anonymous;
          if (item.anonymous) {
            anonymous = await browser.newContext({ ignoreHTTPSErrors: process.env.MT_SELF_SIGNED === '1', viewport: { width, height: width < 700 ? 844 : 1000 }, serviceWorkers: 'block', reducedMotion: 'reduce' });
            await installRoutes(anonymous, events);
            await anonymous.addInitScript(theme => { localStorage.setItem('mt-theme', theme); localStorage.setItem('opdesk:theme', theme); }, theme);
            active = await anonymous.newPage();
            active.on('pageerror', error => pageErrors.push(error.message.slice(0, 300)));
            active.on('response', response => { if (response.status() >= 400 && new URL(response.url()).origin === ORIGIN) resources.push({ status: response.status(), path: safeURL(response.url()) }); });
            active.on('requestfailed', request => { if (request.resourceType() === 'document') resources.push({ error: 'Document load failed', path: safeURL(request.url()) }); });
          }
          const response = await active.goto(ORIGIN + item.path, { waitUntil: 'domcontentloaded', timeout: 40000 });
          await settle(active, item);
          const dom = await active.evaluate(inspectDOM);
          const frames = [];
          for (const frame of active.frames().filter(f => f !== active.mainFrame() && f.url() !== 'about:blank')) {
            const element = await frame.frameElement();
            if (await element.isVisible()) {
              let previewReloaded = false;
              // Chromium does not intercept the final hop of an HTTP redirect.
              // Reload a missing PBX preview at its real, already-resolved URL;
              // do not flatten redirects or change relative resource resolution.
              if ((CANDIDATE || ARTIFACT) && new URL(frame.url()).origin === ORIGIN && new URL(frame.url()).pathname.startsWith('/admin/') && !(await frame.locator('link[href*="mytel/workspace.css"]').count())) {
                await frame.goto(frame.url(), { waitUntil: 'domcontentloaded', timeout: 40000 });
                previewReloaded = true;
              }
              await frame.waitForLoadState('networkidle', { timeout: 3500 }).catch(() => {});
              await frame.evaluate(() => document.fonts.ready);
              frames.push({ path: safeURL(frame.url()), previewReloaded, ...(await frame.evaluate(inspectDOM)) });
            }
          }
          const filename = key + '.jpg';
          await active.screenshot({ path: path.join(OUTPUT, filename), fullPage: true, type: 'jpeg', quality: 78, animations: 'disabled', maskColor: '#24344b', mask: [active.locator('input[type="password"], input[name*="secret"], input[name*="password"], input[name*="token"]')] });
          report.cases.push({ ...item, key, theme, width, status: response?.status(), ...dom, frames, screenshot: filename, pageErrors: [...pageErrors], resources: [...resources] });
          if (anonymous) await anonymous.close();
        } catch (error) {
          report.errors.push({ key, error: String(error.message).slice(0, 700) });
        }
        fs.writeFileSync(path.join(OUTPUT, 'report.json'), JSON.stringify(report, null, 2));
      }
      report.blockedWrites.push(...events.blocked);
      report.errors.push(...(events.routeErrors || []));
      report.blockedWebSockets.push(...(events.webSockets || []));
      report.externalOrigins.push(...events.external);
      await context.close();
    }
  } finally {
    report.finished = new Date().toISOString();
    fs.writeFileSync(path.join(OUTPUT, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
  const problems = report.cases.filter(hasFindings);
  console.log(JSON.stringify({ mode: report.mode, inventory: report.inventory.length, cases: report.cases.length, errors: report.errors, pagesWithFindings: problems.map(c => ({ key: c.key, unavailable: c.unavailable, overflow: c.documentOverflow, contrast: c.lowContrast.length, lightBlocks: c.lightBlocks.length, errors: c.pageErrors.length, resources: c.resources.length, frames: c.frames.filter(frame => hasFindings({ ...frame, surface: new URL(frame.path, ORIGIN).pathname.startsWith('/admin/') ? 'admin' : frame.surface })).map(frame => frame.path) })), blockedWrites: report.blockedWrites.length, blockedWebSockets: report.blockedWebSockets.length }, null, 2));
  if (!report.cases.length || report.errors.length || problems.length || report.blockedWrites.length) process.exitCode = 1;
}

module.exports = { installRoutes, inspectDOM, settle, deskAuth, inventory, hasFindings, previewGeoipHome, artifactManifestSha256: manifestHash };
if (require.main === module) main().catch(error => { fs.writeFileSync(path.join(OUTPUT, 'fatal.txt'), error.stack); console.error(error.stack); process.exitCode = 1; });
