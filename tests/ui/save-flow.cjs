'use strict';
/* Detached native forms and local responses only. No production URL or credentials. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const OUT = process.env.MT_TEST_OUTPUT;
const JQUERY = process.env.MT_SAVE_JQUERY;
if (!OUT || !JQUERY) throw new Error('Set MT_TEST_OUTPUT and MT_SAVE_JQUERY to private fixture paths');
fs.mkdirSync(OUT, {recursive: true});
const sourcePath = path.join(ROOT, 'admin-theme/save.js');
const source = fs.existsSync(sourcePath) ? fs.readFileSync(sourcePath, 'utf8') : '';
const jquery = fs.readFileSync(JQUERY, 'utf8');
const ORIGIN = 'https://fixture.invalid';
const KEY = 'mt-pbx-save-pending-v1';
const results = [], coverageRanges = [];

// The parent-owned feedback module is a separate integration contract. This
// fixture records only its public API and renders observable status text.
const feedback = `
window.MTPBXFeedback = {
 ready: function () { return Promise.resolve(this); },
 render: function (kind, state, title, description) {
  var panel = document.getElementById('mt-' + kind + '-status');
  if (!panel) { panel = document.createElement('section'); panel.id = 'mt-' + kind + '-status'; document.body.appendChild(panel); }
  panel.dataset.state = state; panel.textContent = title + ' ' + description;
 },
 busy: function (kind, value) { var p = this.panel(kind); if (p) p.setAttribute('aria-busy', String(value)); },
 elapsed: function () {},
 state: function (kind) { return this.panel(kind)?.dataset.state; },
 panel: function (kind) { return document.getElementById('mt-' + kind + '-status'); },
 watchSave: function (attempt) { this.lastAttempt = attempt; }
};`;

function childHTML(options = {}, marker = '') {
    const module = options.otherModule ? 'queues' : 'sipsettings';
    return `<!doctype html><html><head><meta charset="utf-8">
<script src="/jquery.js"></script>
<script>window.MTPBXFeedback={ready:function(){return Promise.resolve(parent.MTPBXFeedback)}};</script>
<script defer src="/save.js"></script></head><body>
${marker}<h1>Native ${module} fixture</h1>
<form id="mainform" name="editSip" method="post" action="/admin/config.php?display=${module}">
<input type="hidden" name="action" value="edit">
<label>External address<input id="address" name="externip_val" required value="${options.invalid ? '' : '198.51.100.10'}"></label>
<input type="radio" name="nat" value="yes" checked><input type="radio" name="nat" value="no">
<input name="array[]" value="first"><input name="array[]" value="second">
<input name="empty" value=""><input name="excluded" disabled value="private-fixture">
<textarea name="notes">fixture notes</textarea><select name="mode"><option selected value="one">One</option></select>
<input type="checkbox" name="checked" value="1" checked><input type="checkbox" name="unchecked" value="1">
<button id="inside-submit" type="submit" name="native_action" value="save">Native Save</button></form>
<div id="action-bar"><input id="mainformsubmit" name="btnsubmit" type="submit" value="Submit"></div>
<script>
 jQuery('body').on('click','#mainformsubmit',function(){jQuery('#mainform').trigger('submit')});
 ${options.cancelled ? "jQuery('#mainform').on('submit',function(e){e.preventDefault()});" : ''}
</script></body></html>`;
}

(async () => {
    const browser = await chromium.launch({headless: true, channel: 'chrome'});
    async function run(name, test, options = {}) {
        const context = await browser.newContext();
        const page = await context.newPage();
        page.setDefaultTimeout(1800);
        const pending = [], posts = [], external = [], errors = [];
        if (options.storageBlocked) await context.addInitScript(() => {
            Storage.prototype.setItem = function () { throw new Error('storage blocked'); };
        });
        await context.route('**/*', route => {
            const req = route.request(), url = new URL(req.url());
            if (url.origin !== ORIGIN) { external.push(url.origin); return route.abort(); }
            if (req.method() === 'POST') {
                posts.push(new URLSearchParams(req.postData() || ''));
                pending.push(route);
                return;
            }
            if (url.pathname === '/jquery.js') return route.fulfill({contentType: 'application/javascript', body: jquery});
            if (url.pathname === '/save.js') return route.fulfill({contentType: 'application/javascript', body: source});
            if (url.pathname === '/admin/config.php') return route.fulfill({contentType: 'text/html', body: childHTML(options, options.initialMarker || '')});
            return route.fulfill({contentType: 'text/html', body: '<!doctype html><html><body><script>' + feedback + '</script><iframe id="myframe" src="/admin/config.php?display=' + (options.otherModule ? 'queues' : 'sipsettings') + '"></iframe></body></html>'});
        });
        page.on('pageerror', error => errors.push(error.message));
        await page.coverage.startJSCoverage({resetOnNavigation: false});
        try {
            await page.goto(ORIGIN + '/');
            await page.frameLocator('#myframe').locator('#mainform').waitFor();
            const frame = page.frames().find(f => f.url().includes('/admin/config.php'));
            await frame.waitForFunction(() => document.readyState === 'complete');
            await page.waitForTimeout(50);
            const submit = () => frame.locator('#mainformsubmit').click({noWaitAfter: true});
            const waitPost = () => page.waitForFunction(() => !!parent.MTPBXFeedback.lastAttempt).catch(() => {});
            const finish = async (status = 'success', token, includeMarker = true) => {
                await page.waitForTimeout(70);
                assert.equal(pending.length, 1, 'one native request must be in flight');
                const id = token === undefined ? posts[0].get('mt_save_attempt') : token;
                const marker = includeMarker ? '<div hidden id="mt-save-result" data-display="sipsettings" data-attempt="' + (id || '') + '" data-status="' + status + '"></div>' : '';
                await pending.shift().fulfill({status: 200, contentType: 'text/html', body: childHTML(options, marker)});
                await frame.waitForFunction(() => document.readyState === 'complete');
                await page.waitForTimeout(100);
            };
            await test({page, frame, posts, submit, finish, waitPost});
            assert.deepEqual(external, [], 'fixture must never access a real origin');
            assert.deepEqual(errors, [], 'no page JavaScript errors');
            results.push({name, result: 'PASS'});
        } catch (error) {
            results.push({name, result: 'FAIL', error: error.message.split('\n').slice(0, 3).join(' ')});
        } finally {
            for (const route of pending.splice(0)) await route.abort().catch(() => {});
            const entries = await page.coverage.stopJSCoverage().catch(() => []);
            for (const entry of entries) if (entry.url === ORIGIN + '/save.js' && entry.text === source) coverageRanges.push(...entry.ranges);
            await context.close();
        }
    }

    await run('native Submit gives immediate nonblocking progress and preserves successful controls', async ({page, frame, posts, submit}) => {
        await submit(); await page.waitForTimeout(100);
        assert.equal(await page.locator('#mt-save-status[data-state="saving"]').isVisible(), true);
        assert.equal(posts.length, 1);
        assert.match(posts[0].get('mt_save_attempt'), /^[0-9a-f]{32}$/);
        assert.deepEqual(posts[0].getAll('array[]'), ['first', 'second']);
        assert.equal(posts[0].get('externip_val'), '198.51.100.10');
        assert.equal(posts[0].get('nat'), 'yes');
        assert.equal(posts[0].get('empty'), '');
        assert.equal(posts[0].get('notes'), 'fixture notes');
        assert.equal(posts[0].get('mode'), 'one');
        assert.equal(posts[0].get('checked'), '1');
        assert.equal(posts[0].has('unchecked'), false);
        assert.equal(posts[0].has('excluded'), false);
        assert.equal(await frame.locator('#address').isDisabled(), false);
        assert.notEqual(await frame.locator('body').evaluate(e => getComputedStyle(e).pointerEvents), 'none');
        assert.notEqual(await page.locator('body').evaluate(e => getComputedStyle(e).pointerEvents), 'none');
        const record = await frame.evaluate(key => JSON.parse(sessionStorage.getItem(key)), KEY);
        assert.deepEqual(Object.keys(record).sort(), ['display', 'id', 'path', 'started']);
    });
    await run('repeated click and jQuery synthetic Submit cannot send another request', async ({page, frame, posts, submit}) => {
        await submit(); await page.waitForTimeout(100);
        await frame.evaluate(() => { jQuery('#mainform').trigger('submit'); document.querySelector('#mainformsubmit').click(); });
        await page.waitForTimeout(100); assert.equal(posts.length, 1);
    });
    await run('matching server success marker confirms only this attempt', async ({page, frame, submit, finish}) => {
        await submit(); await finish();
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'success');
        assert.equal(await frame.evaluate(key => sessionStorage.getItem(key), KEY), null);
    });
    await run('server validation failure is visible and never reports Saved', async ({page, posts, submit, finish}) => {
        await submit(); await finish('validation-error');
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'error');
        assert.equal(posts.length, 1);
    });
    await run('mismatched attempt marker is an unknown outcome', async ({page, submit, finish}) => {
        await submit(); await finish('success', '0'.repeat(32));
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'unknown');
    });
    await run('HTTP200 without a save result never means success', async ({page, submit, finish}) => {
        await submit(); await finish('success', undefined, false);
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'unknown');
    });
    await run('old success markup without a pending attempt is ignored', async ({page, posts}) => {
        assert.equal(await page.locator('#mt-save-status').count(), 0); assert.equal(posts.length, 0);
    }, {initialMarker: '<div hidden id="mt-save-result" data-display="sipsettings" data-attempt="' + 'a'.repeat(32) + '" data-status="success"></div>'});
    await run('invalid native controls prevent synthetic Submit and feedback', async ({page, posts, submit}) => {
        await submit(); await page.waitForTimeout(100);
        assert.equal(posts.length, 0); assert.equal(await page.locator('#mt-save-status').count(), 0);
    }, {invalid: true});
    await run('existing form validation cancellation is preserved', async ({page, posts, submit}) => {
        await submit(); await page.waitForTimeout(100);
        assert.equal(posts.length, 0); assert.equal(await page.locator('#mt-save-status').count(), 0);
    }, {cancelled: true});
    await run('unrelated module submission remains native and unmodified', async ({page, posts, submit}) => {
        await submit(); await page.waitForTimeout(100);
        assert.equal(posts.length, 1); assert.equal(posts[0].has('mt_save_attempt'), false);
        assert.equal(await page.locator('#mt-save-status').count(), 0);
    }, {otherModule: true});
    await run('Apply in progress blocks Save without losing form values', async ({page, frame, posts, submit}) => {
        await page.evaluate(() => MTPBXFeedback.render('apply', 'applying', 'Applying', ''));
        await submit(); await page.waitForTimeout(100);
        assert.equal(posts.length, 0); assert.equal(await frame.locator('#address').inputValue(), '198.51.100.10');
    });
    await run('native requestSubmit retains the real submitter name and value', async ({page, frame, posts}) => {
        await frame.evaluate(() => document.querySelector('#mainform').requestSubmit(document.querySelector('#inside-submit')));
        await page.waitForTimeout(100); assert.equal(posts.length, 1);
        assert.equal(posts[0].get('native_action'), 'save');
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'saving');
    });
    await run('fragment replacement and repeated script evaluation do not duplicate handlers', async ({page, frame, posts, submit}) => {
        await frame.evaluate(() => { const f = document.querySelector('#mainform'); f.replaceWith(f.cloneNode(true)); });
        await frame.addScriptTag({url: ORIGIN + '/save.js'});
        await submit(); await page.waitForTimeout(100);
        assert.equal(posts.length, 1); assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'saving');
    });
    await run('unavailable sessionStorage does not break native submission', async ({page, posts, submit}) => {
        await submit(); await page.waitForTimeout(100); assert.equal(posts.length, 1);
        assert.match(posts[0].get('mt_save_attempt'), /^[0-9a-f]{32}$/);
        assert.equal(await page.locator('#mt-save-status').getAttribute('data-state'), 'saving');
    }, {storageBlocked: true});

    const ranges = coverageRanges.sort((a, b) => a.start - b.start), merged = [];
    for (const range of ranges) {
        const last = merged[merged.length - 1];
        if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
        else merged.push({...range});
    }
    const covered = merged.reduce((sum, r) => sum + r.end - r.start, 0);
    fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(results, null, 2));
    fs.writeFileSync(path.join(OUT, 'coverage.json'), JSON.stringify({metric: 'V8 executed source bytes across detached browser cases; not statement/branch coverage', bytes: source.length, coveredBytes: covered, percent: source.length ? 100 * covered / source.length : 0}, null, 2));
    console.log(JSON.stringify(results));
    await browser.close();
    if (results.some(result => result.result !== 'PASS')) process.exitCode = 1;
})().catch(error => { console.error(error.stack); process.exit(1); });
