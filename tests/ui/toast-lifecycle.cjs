/*
 * Embedded Apply lifecycle regression. Configuration writes/reloads are local mocks.
 * Required: MT_TEST_URL, MT_TEST_PASSWORD. Optional: MT_TEST_USER (admin),
 * MT_TEST_OUTPUT (otherwise a new OS temp directory), MT_TEST_BROWSER (chrome),
 * MT_TOAST_APPLY_SOURCE (one apply.js override), MT_ADMIN_CANDIDATE (admin asset root).
 * Install Playwright or expose it through NODE_PATH. Never persist credentials.
 * Exit 0 = all checks pass, 1 = lifecycle regression, 2 = fixture/setup failure.
 */
'use strict';
const {chromium} = require('playwright');
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), os = require('node:os');
if (!process.env.MT_TEST_URL || !process.env.MT_TEST_PASSWORD) throw new Error('Set MT_TEST_URL and MT_TEST_PASSWORD');
const target = new URL(process.env.MT_TEST_URL);
if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password || target.search || target.hash || target.pathname !== '/') throw new Error('MT_TEST_URL must be an HTTP(S) origin without credentials or query');
const ORIGIN = target.origin;
const OUT = process.env.MT_TEST_OUTPUT ? path.resolve(process.env.MT_TEST_OUTPUT) : fs.mkdtempSync(path.join(os.tmpdir(), 'mytell-toast-'));
const CANDIDATE = process.env.MT_ADMIN_CANDIDATE ? path.resolve(process.env.MT_ADMIN_CANDIDATE) : null;
const APPLY = process.env.MT_TOAST_APPLY_SOURCE ? fs.readFileSync(path.resolve(process.env.MT_TOAST_APPLY_SOURCE)) : null;
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
fs.mkdirSync(OUT, {recursive: true});
let browser, context, page, frame, loginPosts = 0, allowForm = false, sipHtml = null, phase = 'setup';
const assetTasks = [];
const evidence = {
    schema: 1,
    purpose: 'Close parent Apply result after actual iframe/form/Unpoly lifecycle; all writes intercepted',
    sourceOverride: APPLY ? {asset: 'apply.js', sha256: digest(APPLY)} : null,
    candidateAssetRoot: !!CANDIDATE,
    forwardedRequests: {login: 0, reads: 0, otherWrites: 0},
    localReloads: [], localSubmits: [], blocked: [], errors: [], assets: [], assertions: [], cases: []
};
function save() { fs.writeFileSync(path.join(OUT, 'result.json'), JSON.stringify(evidence, null, 2)); }
function claim(name, pass, data) { evidence.assertions.push({name, pass: !!pass, ...(data ? {data} : {})}); save(); }
function safe(url) { const u = new URL(url); return u.pathname + (u.searchParams.has('display') ? '?display=' + u.searchParams.get('display') : u.searchParams.has('menu') ? '?menu=' + u.searchParams.get('menu') : ''); }
function sanitize(message) { return String(message).split(ORIGIN).join('[target]').split(process.env.MT_TEST_PASSWORD).join('[redacted]').slice(0, 600); }
async function forwardRead(route) {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) {
        // Defense in depth: even an earlier guard regression cannot forward a write.
        throw new Error('Refused to forward a non-read request');
    }
    evidence.forwardedRequests.reads++;
    return route.continue();
}
async function install() {
    await context.routeWebSocket('**/*', socket => socket.close());
    await context.route('**/*', async route => {
        const req = route.request(), u = new URL(req.url()), method = req.method(), body = new URLSearchParams(req.postData() || '');
        try {
            if (u.origin !== ORIGIN) return await route.abort('blockedbyclient');
            if (method === 'POST' && loginPosts === 0 && req.isNavigationRequest() && ['/', '/index.php'].includes(u.pathname) && body.has('input_user') && body.has('input_pass')) {
                loginPosts++; evidence.forwardedRequests.login++;
                return await route.continue();
            }
            if (method === 'POST' && u.pathname === '/admin/config.php' && body.get('handler') === 'reload') {
                evidence.localReloads.push({phase, navigation: req.isNavigationRequest(), resourceType: req.resourceType()});
                await new Promise(resolve => setTimeout(resolve, 250));
                return await route.fulfill({status: 200, contentType: 'application/json', body: '{"status":true,"num_errors":0}'});
            }
            if (method === 'POST' && u.pathname === '/admin/config.php' && allowForm && sipHtml && (body.get('display') === 'sipsettings' || u.searchParams.get('display') === 'sipsettings')) {
                allowForm = false;
                evidence.localSubmits.push({phase, navigation: req.isNavigationRequest(), resourceType: req.resourceType(), upTarget: req.headers()['x-up-target'] || null});
                return await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8', headers: {'x-up-location': ORIGIN + '/admin/config.php?display=sipsettings'}, body: sipHtml});
            }
            if (!['GET', 'HEAD', 'OPTIONS'].includes(method) || u.searchParams.has('action') || u.searchParams.get('handler') === 'reload') {
                evidence.blocked.push({phase, method, path: safe(req.url()), action: u.searchParams.get('action')});
                return await route.fulfill({status: 405, contentType: 'application/json', body: '{"preview":"write/action blocked locally"}'});
            }
            if (APPLY && u.pathname === '/admin/assets/mytel/apply.js') return await route.fulfill({status: 200, contentType: 'application/javascript; charset=utf-8', body: APPLY});
            if (CANDIDATE && u.pathname.startsWith('/admin/assets/') && /\.(js|css)$/.test(u.pathname)) {
                const file = path.resolve(CANDIDATE, u.pathname.slice('/admin/'.length));
                if (file.startsWith(CANDIDATE + path.sep) && fs.existsSync(file)) {
                    const bytes = fs.readFileSync(file);
                    return await route.fulfill({status: 200, contentType: file.endsWith('.css') ? 'text/css; charset=utf-8' : 'application/javascript; charset=utf-8', body: bytes});
                }
            }
            if (method === 'GET' && u.pathname === '/admin/config.php' && u.searchParams.get('display') === 'sipsettings') {
                evidence.forwardedRequests.reads++;
                const response = await route.fetch({maxRedirects: 0, timeout: 20000});
                if (response.status() === 200 && /text\/html/.test(response.headers()['content-type'] || '')) {
                    sipHtml = await response.body();
                    return await route.fulfill({response, body: sipHtml});
                }
                return await route.fulfill({response});
            }
            return await forwardRead(route);
        } catch (error) {
            evidence.errors.push({kind: 'route', phase, path: safe(req.url()), error: sanitize(error.message)});
            await route.abort('failed').catch(() => {});
        }
    });
}
async function ready() {
    await frame.waitForFunction(() => window.__mtApplyReady && window.__mtAdminWorkspace && window.ipbx);
    await frame.waitForTimeout(250);
}
async function apply() {
    await frame.evaluate(() => {
        ipbx.conf.reload_needed = true; ipbx.conf.RELOADCONFIRM = false; toggle_reload_button('show');
        ipbx_reload();
    });
    await page.waitForFunction(() => document.querySelector('#mt-apply-status')?.dataset.state === 'success');
    await frame.waitForFunction(() => document.getElementById('button_reload')?.getAttribute('aria-busy') === 'false');
}
async function closeState() {
    return page.evaluate(() => {
        const panel = document.getElementById('mt-apply-status'), button = panel?.querySelector('.mt-apply-close');
        const rect = button?.getBoundingClientRect();
        return {panelCount: document.querySelectorAll('#mt-apply-status').length, state: panel?.dataset.state || null, closeVisible: !!(rect?.width && rect?.height && !button.hidden), parentPointer: getComputedStyle(document.body).pointerEvents};
    });
}
async function closeResult(label) {
    const before = await closeState();
    if (before.panelCount) await page.locator('#mt-apply-status .mt-apply-close').click();
    await page.waitForTimeout(100);
    const after = await closeState();
    evidence.cases.push({label, before, after});
    claim(label, after.panelCount === 0);
    if (after.panelCount) await page.locator('#mt-apply-status').screenshot({path: path.join(OUT, label + '.png')});
    // Browser-only cleanup between independent scenarios.
    await page.evaluate(() => document.getElementById('mt-apply-status')?.remove());
}
(async () => {
    browser = await chromium.launch({channel: process.env.MT_TEST_BROWSER || 'chrome', headless: true});
    context = await browser.newContext({ignoreHTTPSErrors: true, viewport: {width: 1440, height: 1000}});
    await context.addInitScript(() => { window.__toastRealm = Math.random().toString(36); });
    await install();
    page = await context.newPage(); page.setDefaultTimeout(12000);
    page.on('pageerror', error => evidence.errors.push({kind: 'javascript', phase, error: sanitize(error.message)}));
    page.on('response', response => {
        if (new URL(response.url()).pathname === '/admin/assets/mytel/apply.js') assetTasks.push(response.body().then(bytes => evidence.assets.push({phase, path: '/admin/assets/mytel/apply.js', sha256: digest(bytes)})).catch(error => evidence.errors.push({kind: 'asset-read', phase, error: sanitize(error.message)})));
    });
    await page.goto(ORIGIN, {waitUntil: 'domcontentloaded'});
    await page.locator('[name=input_user]').fill(process.env.MT_TEST_USER || 'admin'); await page.locator('[name=input_pass]').fill(process.env.MT_TEST_PASSWORD);
    await Promise.all([page.waitForNavigation({waitUntil: 'domcontentloaded'}), page.locator('[name=submit_login]').click()]);
    await page.goto(ORIGIN + '/index.php?menu=pbxadmin', {waitUntil: 'domcontentloaded'});
    await page.frameLocator('#myframe').locator('#page').waitFor();
    frame = await (await page.locator('#myframe').elementHandle()).contentFrame();
    await frame.goto(ORIGIN + '/admin/config.php?display=sipsettings', {waitUntil: 'domcontentloaded'}); await ready();
    evidence.sipOwner = await frame.evaluate(() => ({
        forms: [...document.forms].map(f => ({id: f.id, name: f.name, method: f.getAttribute('method'), action: new URL(f.getAttribute('action') || '', location.href).pathname + new URL(f.getAttribute('action') || '', location.href).search, upTarget: f.getAttribute('up-target')})),
        submitButtons: [...document.querySelectorAll('#mainformsubmit,button[type=submit],input[type=submit]')].map(b => ({id: b.id, type: b.type, formId: b.form?.id || null, dataTarget: b.getAttribute('data-target')})),
        unpoly: !!window.up, upVersion: window.up?.version
    }));
    phase = 'control-before-navigation'; await apply(); await closeResult('close-before-navigation');
    phase = 'full-iframe-navigation'; await apply();
    const oldRealm = await frame.evaluate(() => window.__toastRealm);
    await frame.goto(ORIGIN + '/admin/config.php?display=sipsettings', {waitUntil: 'domcontentloaded'}); await ready();
    claim('Full iframe navigation changed execution context', oldRealm !== await frame.evaluate(() => window.__toastRealm));
    await closeResult('close-after-full-iframe-navigation');
    phase = 'native-sip-submit'; await apply();
    const submitRealm = await frame.evaluate(() => window.__toastRealm);
    allowForm = true;
    const beforeSubmitCount = evidence.localSubmits.length;
    if (await frame.locator('#mainformsubmit').count()) await frame.locator('#mainformsubmit').click();
    else if (await frame.locator('button[type=submit],input[type=submit]').count()) await frame.locator('button[type=submit],input[type=submit]').first().click();
    await page.waitForTimeout(350);
    evidence.submitButtonPosted = evidence.localSubmits.length > beforeSubmitCount;
    if (!evidence.submitButtonPosted) throw new Error('Native SIP action-bar Submit did not post; cannot validate submit lifecycle');
    await page.waitForTimeout(700); await ready();
    claim('Exactly one native SIP submit answered locally', evidence.localSubmits.length === beforeSubmitCount + 1);
    evidence.submitChangedRealm = submitRealm !== await frame.evaluate(() => window.__toastRealm);
    await closeResult('close-after-native-sip-submit');
    phase = 'actual-unpoly-fragment-replacement';
    await apply();
    const unpolyRealm = await frame.evaluate(() => window.__toastRealm);
    for (let i = 0; i < 3; i++) {
        await frame.evaluate(async () => {
            await up.render({target: '#page', url: location.pathname + location.search, history: false, cache: false});
        });
        await ready();
    }
    claim('Actual Unpoly replacements retained iframe execution context', unpolyRealm === await frame.evaluate(() => window.__toastRealm));
    await closeResult('close-after-actual-unpoly-replacements');
    phase = 'single-flight-after-unpoly-reinitialization';
    const countBefore = evidence.localReloads.length;
    await frame.evaluate(() => {
        ipbx.conf.reload_needed = true; ipbx.conf.RELOADCONFIRM = false; toggle_reload_button('show');
        document.getElementById('button_reload').click(); ipbx_reload(); ipbx_reload();
    });
    await page.waitForFunction(() => document.querySelector('#mt-apply-status')?.dataset.state === 'success');
    await frame.waitForFunction(() => document.getElementById('button_reload')?.getAttribute('aria-busy') === 'false');
    claim('Repeated fragment init and duplicate triggers send only one reload', evidence.localReloads.length === countBefore + 1);
    await closeResult('close-after-fragment-reinitialization');
    await Promise.all(assetTasks);
    claim('Apply implementation hash captured', evidence.assets.length > 0);
    claim('No JavaScript or route errors during native lifecycle', evidence.errors.length === 0);
    claim('Only login was forwarded; all settings writes and reloads were local mocks', evidence.forwardedRequests.login === 1 && evidence.forwardedRequests.otherWrites === 0 && evidence.blocked.filter(x => !['GET','HEAD','OPTIONS'].includes(x.method)).length === 0);
    evidence.status = evidence.assertions.every(x => x.pass) ? 'passed' : 'regression-reproduced';
    evidence.loginPosts = loginPosts; save();
    await browser.close();
    console.log(JSON.stringify({status: evidence.status, checks: evidence.assertions.length, failures: evidence.assertions.filter(x => !x.pass).map(x => x.name), output: OUT}));
    process.exitCode = evidence.status === 'passed' ? 0 : 1;
})().catch(async error => {
    evidence.status = 'fixture-error'; evidence.failure = sanitize(error.message); save();
    if (browser) await browser.close().catch(() => {});
    console.error(JSON.stringify({status: evidence.status, failure: evidence.failure, output: OUT})); process.exitCode = 2;
});
