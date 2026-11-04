/* Read-only interaction checks. Never submit forms, register a phone or call. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.MT_PLAYWRIGHT_MODULE || 'playwright-core');
const { installRoutes, inspectDOM, settle, deskAuth, artifactManifestSha256 } = require('./audit.cjs');
const ORIGIN = new URL(process.env.MT_BASE_URL).origin;
const output = path.resolve(process.env.MT_EVIDENCE_DIR || 'ui-evidence');
const include = process.env.MT_INTERACTION_INCLUDE;

async function main() {
  fs.mkdirSync(output, { recursive: true, mode: 0o700 });
  const browser = await chromium.launch({ executablePath: process.env.MT_CHROMIUM_PATH || undefined,
    args: process.env.MT_CHROMIUM_NO_SANDBOX === '1' ? ['--no-sandbox', '--disable-dev-shm-usage'] : [] });
  const report = { artifactManifestSha256, harnessSha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'), selection: include || null, checks: [], blockedWrites: [], blockedWebSockets: [], routeErrors: [], finished: null };
  try {
    const authContext = await browser.newContext({ ignoreHTTPSErrors: process.env.MT_SELF_SIGNED === '1' });
    const auth = await deskAuth(authContext);
    await authContext.close();
    for (const width of [1440, 390]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({ ignoreHTTPSErrors: process.env.MT_SELF_SIGNED === '1',
        viewport: { width, height: 1000 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
      const events = { blocked: [], external: new Set(), currentCase: `interactions-${theme}-${width}` };
      await installRoutes(context, events);
      await context.addCookies([{ name: 'issabelSession', value: process.env.MT_PANEL_SESSION || '', url: ORIGIN }]);
      await context.addInitScript(({ theme, auth }) => {
        if (!localStorage.getItem('mt-theme')) localStorage.setItem('mt-theme', theme);
        if (!localStorage.getItem('opdesk:theme')) localStorage.setItem('opdesk:theme', theme);
        if (auth) { localStorage.setItem('opdesk_token', auth.token); localStorage.setItem('opdesk_user', JSON.stringify(auth.user)); }
      }, { theme, auth });
      const page = await context.newPage();
      const pageErrors = [], resources = [];
      page.on('pageerror', error => pageErrors.push(error.message.slice(0, 300)));
      page.on('response', response => { if (response.status() >= 400) resources.push({ status: response.status(), path: new URL(response.url()).pathname }); });
      page.on('requestfailed', request => { if (request.resourceType() === 'document') resources.push('Document load failed'); });
      const check = async (name, fn) => {
        if (include && name !== include) return;
        pageErrors.length = resources.length = 0;
        let behaviorPassed = false;
        try {
          await fn();
          behaviorPassed = true;
          for (const frame of page.frames()) {
            if (frame !== page.mainFrame() && !(await (await frame.frameElement()).isVisible())) continue;
            assert.equal((await frame.evaluate(inspectDOM)).unavailable, false, 'Page or iframe is unavailable');
          }
          assert.deepEqual(pageErrors, [], 'Page or iframe JavaScript errors');
          assert.deepEqual(resources, [], 'Failed page or iframe resources');
          report.checks.push({ name, width, theme, passed: true, behaviorPassed, pageErrors: [...pageErrors], resources: [...resources] });
        }
        catch (error) { report.checks.push({ name, width, theme, passed: false, behaviorPassed, pageErrors: [...pageErrors], resources: [...resources], error: error.message.slice(0, 350) }); }
      };
      const goto = async (route, surface, name) => {
        const response = await page.goto(ORIGIN + route, { waitUntil: 'domcontentloaded' });
        assert.ok(response && response.status() < 400, 'Page is unavailable');
        await settle(page, { surface, name });
      };
      const themeCheck = async (selector, attribute) => {
        const before = await page.locator('html').getAttribute(attribute);
        const after = before === 'dark' ? 'light' : 'dark';
        const button = page.locator(selector + ':visible').first();
        assert.equal(await button.locator('svg').count(), 1);
        assert.ok(await button.getAttribute('aria-label'));
        await button.focus(); await page.keyboard.press('Enter');
        await page.waitForFunction(({ attribute, after }) => document.documentElement.getAttribute(attribute) === after, { attribute, after });
        await page.reload({ waitUntil: 'domcontentloaded' });
        await settle(page, {});
        assert.equal(await page.locator('html').getAttribute(attribute), after);
        await page.evaluate(({ before, key }) => localStorage.setItem(key, before), { before, key: attribute === 'data-theme' ? 'opdesk:theme' : 'mt-theme' });
        await page.reload({ waitUntil: 'domcontentloaded' });
        await settle(page, {});
      };
      await check('panel drawer and focus return', async () => {
        await goto('/index.php?menu=dashboard', 'panel', 'dashboard');
        if (width < 992) {
          assert.equal(await page.locator('#mt-sidebar').evaluate(el => el.inert), true);
          await page.locator('#mt-burger').click();
          await page.waitForFunction(() => document.querySelector('#mt-burger').getAttribute('aria-expanded') === 'true');
          assert.equal(await page.locator('#mt-sidebar').evaluate(el => el.inert), false);
          assert.equal(await page.locator('#mt-sidebar').evaluate(el => el.contains(document.activeElement)), true);
          await page.keyboard.press('Escape');
          await page.waitForFunction(() => document.activeElement.id === 'mt-burger' && document.querySelector('#mt-sidebar').inert);
        } else {
          await page.locator('.mt-skip-link').focus();
          assert.equal(await page.locator('.mt-skip-link').evaluate(el => getComputedStyle(el).outlineStyle), 'solid');
        }
      });
      await check('panel keyboard theme and persistence', async () => {
        if (width < 992) await page.locator('#mt-burger').click();
        await themeCheck('.mt-theme-toggle', 'data-mt-theme');
      });
      await check('Jalali month navigation, dropdown and local scroll', async () => {
        await goto('/index.php?menu=calendar', 'panel', 'calendar');
        const title = await page.locator('#mt-jmonth-title').textContent();
        await page.getByRole('button', { name: 'ماه بعد' }).click();
        await page.waitForFunction(title => document.querySelector('#mt-jmonth-title').textContent !== title, title);
        await page.getByRole('button', { name: 'ماه قبل' }).click();
        await page.waitForFunction(title => document.querySelector('#mt-jmonth-title').textContent === title, title);
        const month = Number(await page.locator('.mt-cal-jm').inputValue());
        await page.locator('.mt-cal-jm').selectOption(String(month === 12 ? 1 : month + 1));
        await page.locator('.mt-calside-today').click();
        const geometry = await page.evaluate(() => {
          const scroll = document.querySelector('.mt-jmonth-scroll');
          return { document: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth) - innerWidth,
            local: scroll.scrollWidth > scroll.clientWidth, columns: document.querySelectorAll('.mt-jweekday').length };
        });
        assert.equal(geometry.columns, 7); assert.ok(geometry.document <= 3);
        if (width < 700) assert.equal(geometry.local, true);
      });
      await check('report filter, date focus and export menu without submission', async () => {
        await goto('/index.php?menu=cdrreport', 'panel', 'cdrreport');
        const mirror = page.locator('.mt-date-mirror:visible').first();
        if (!(await mirror.isVisible())) {
          await page.locator('a[href="#filters"]:visible, #neo-table-filter-button-arrow:visible').first().click();
        }
        await mirror.waitFor({ state: 'visible' });
        await page.screenshot({ path: path.join(output, `report-filter-${theme}-${width}.png`), fullPage: true });
        await mirror.focus();
        await page.locator('.mt-dp').waitFor({ state: 'visible' });
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.mt-dp').count(), 0);
        assert.equal(await mirror.evaluate(el => el === document.activeElement), true);
        if (await page.locator('#export_button:visible').count()) {
          await page.locator('#export_button').click();
          await page.locator('#subMenuExport').waitFor({ state: 'visible' });
        }
      });
      await check('PBX stays LTR and keeps native field order', async () => {
        await goto('/admin/config.php?display=extensions', 'admin', 'extensions');
        const order = () => page.locator('form input,form select,form textarea').evaluateAll(els => els.map(el => el.name));
        const before = await order();
        if (!(await page.locator('.mt-admin-theme-toggle:visible').count())) {
          await page.locator('.navbar-burger:visible').click();
        }
        await themeCheck('.mt-admin-theme-toggle', 'data-mt-theme');
        assert.deepEqual(await order(), before);
        assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).direction), 'ltr');
      });
      await check('desk keyboard theme and persistence', async () => {
        assert.ok(auth, 'External desk authentication is required');
        await goto('/MytellDesk/dashboard', 'desk', 'dashboard');
        await themeCheck('.theme-toggle', 'data-theme');
      });
      await check('standalone phone theme without registration', async () => {
        await goto('/Phone/', 'phone', 'phone-login');
        await themeCheck('.mt-phone-theme-toggle', 'data-mt-theme');
      });
      report.blockedWrites.push(...events.blocked);
      report.routeErrors.push(...(events.routeErrors || []));
      report.blockedWebSockets.push(...(events.webSockets || []));
      await context.close();
    }
  } finally {
    report.finished = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'interactions.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
  console.log(JSON.stringify({ checks: report.checks.length, failures: report.checks.filter(c => !c.passed), blockedWrites: report.blockedWrites.length, blockedWebSockets: report.blockedWebSockets.length }, null, 2));
  if (!report.checks.length || report.checks.some(c => !c.passed) || report.blockedWrites.length || report.routeErrors.length) process.exitCode = 1;
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
