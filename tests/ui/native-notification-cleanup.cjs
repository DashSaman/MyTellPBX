'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

const source = fs.readFileSync(process.argv[2], 'utf8');
const toast = source.match(/^function sweet_toast\([^\n]*\) \{[\s\S]*?^\}/m)?.[0];
assert(toast, 'Expected the native sweet_toast function in pbxlib.js');

(async () => {
    const browser = await chromium.launch({ channel: process.env.MT_TEST_BROWSER || 'chrome' });
    const errors = [];
    const extraRequests = [];
    try {
        const target = 'https://pbx.invalid/admin/config.php?display=extensions';
        const page = await browser.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', route => {
            if (route.request().isNavigationRequest() && route.request().url() === target) {
                return route.fulfill({ contentType: 'text/html', body: '<!doctype html><main></main>' });
            }
            const request = route.request();
            const url = new URL(request.url());
            extraRequests.push({ method: request.method(), path: url.pathname, action: url.searchParams.get('action') });
            return route.abort('blockedbyclient');
        });
        await page.goto(target);
        await page.evaluate(() => {
            window.Toast = {
                fire(options) {
                    const button = document.createElement('button');
                    button.textContent = options.title;
                    function close() {
                        if (!button.isConnected) return;
                        button.remove();
                        options.didDestroy?.();
                    }
                    button.addEventListener('click', close);
                    document.querySelector('main').append(button);
                    setTimeout(close, options.timer);
                },
            };
        });
        await page.addScriptTag({ content: toast });
        await page.evaluate(() => sweet_toast('warning', 'Fixture deleted', 1000));
        const deletionNotice = page.getByRole('button', { name: 'Fixture deleted', exact: true });
        await deletionNotice.click();
        await deletionNotice.waitFor({ state: 'detached' });
        await page.evaluate(() => sweet_toast('success', 'Fixture saved', 30));
        await page.getByRole('button', { name: 'Fixture saved', exact: true }).waitFor({ state: 'detached' });
        await page.waitForTimeout(200);
        assert.deepEqual({ errors, extraRequests }, { errors: [], extraRequests: [] });
        console.log('Native dismissal and timeout finished without a session request or page error.');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
