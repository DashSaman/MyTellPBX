/* Intercepts every Apply request. Never reloads or writes PBX configuration. */
'use strict';
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.MT_TEST_URL;
const candidate = process.env.MT_ADMIN_CANDIDATE;
const results = [];
if (!base || !process.env.MT_TEST_PASSWORD) throw new Error('Set MT_TEST_URL and MT_TEST_PASSWORD');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const context = await browser.newContext({ignoreHTTPSErrors:true, viewport:{width:1440,height:1000}});
  const login = await context.newPage();
  await login.goto(base);
  await login.locator('[name="input_user"]').fill(process.env.MT_TEST_USER || 'admin');
  await login.locator('[name="input_pass"]').fill(process.env.MT_TEST_PASSWORD);
  await Promise.all([login.waitForNavigation(), login.locator('[name="submit_login"]').click()]);
  await login.close();

  async function run(name, body, response = {status:true, num_errors:0}) {
    const page = await context.newPage();
    const pending=[];
    await page.route('**/*', async route => {
      const req=route.request(), url=new URL(req.url());
      if (url.origin !== new URL(base).origin) return route.abort();
      if (req.method() !== 'GET') {
        if (req.method()==='POST' && new URLSearchParams(req.postData()||'').get('handler')==='reload') {
          pending.push(route);
          return;
        }
        return route.fulfill({status:405, body:'Test blocked mutation'});
      }
      if(candidate && url.pathname.startsWith('/admin/')) {
        const file=path.join(candidate,url.pathname.slice('/admin/'.length));
        if(fs.existsSync(file) && /\.(js|css)$/.test(file)) return route.fulfill({path:file});
      }
      return route.continue();
    });
    try {
      await page.goto(base+'/admin/config.php?display=extensions', {waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>typeof window.ipbx_reload==='function');
      if(candidate) {
        await page.addStyleTag({path:path.join(candidate,'assets/mytel/workspace.css')});
        await page.addStyleTag({path:path.join(candidate,'assets/mytel/apply.css')});
        await page.addScriptTag({path:path.join(candidate,'assets/mytel/apply.js')});
      }
      await page.evaluate(()=>{ipbx.conf.reload_needed=true; toggle_reload_button('show');});
      const finish = async (data=response, status=200) => {
        await page.waitForTimeout(80);
        await Promise.all(pending.splice(0).map(r=>r.fulfill({status,contentType:'application/json',body:JSON.stringify(data)})));
        await page.waitForTimeout(150);
      };
      await body({page,pending,finish});
      results.push({name,result:'PASS'});
    } catch(e) { results.push({name,result:'FAIL',error:e.message.split('\n').slice(0,4).join(' ')}); }
    finally {
      await Promise.all(pending.splice(0).map(r=>r.fulfill({contentType:'application/json',body:JSON.stringify(response)}).catch(()=>{})));
      await page.close();
    }
  }

  await run('confirmation off sends once and does not prompt', async({page,pending})=>{
    await page.evaluate(()=>{window.promptCount=0;ipbx.conf.RELOADCONFIRM=false;window.sweet_confirm=()=>{promptCount++;return Promise.resolve(0);};ipbx_reload_confirm();});
    await page.waitForTimeout(120);
    assert.equal(await page.evaluate(()=>promptCount),0);
    assert.equal(pending.length,1);
  });
  await run('cancelled confirmation never sends Apply',async({page,pending})=>{
    await page.evaluate(()=>{ipbx.conf.RELOADCONFIRM=true;window.sweet_confirm=()=>Promise.resolve(0);ipbx_reload_confirm();});
    await page.waitForTimeout(120);assert.equal(pending.length,0);
  });
  await run('repeated activation sends one request',async({page,pending})=>{
    await page.evaluate(()=>{ipbx_reload();ipbx_reload();ipbx_reload();});
    await page.waitForTimeout(120);assert.equal(pending.length,1);
  });
  await run('Apply has visible feedback and leaves body readable',async({page})=>{
    await page.locator('#button_reload').click();
    // Some installations have confirmation enabled; confirm only the browser-local mock.
    if(await page.locator('.swal2-confirm').isVisible()) await page.locator('.swal2-confirm').click();
    await page.waitForTimeout(150);
    assert.notEqual(await page.locator('body').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
    assert.equal(await page.locator('#mt-apply-status[data-state="applying"]').isVisible(),true);
  });
  await run('unrelated request cannot dismiss Apply feedback',async({page})=>{
    await page.evaluate(()=>ipbx_reload());await page.waitForTimeout(1100);
    await page.evaluate(()=>fetch('/themes/mytel/css/fonts.css'));
    await page.waitForTimeout(700);
    assert.equal(await page.locator('#mt-apply-status[data-state="applying"]').isVisible(),true);
  });
  await run('server error retains pending changes and restores controls',async({page,finish})=>{
    await page.evaluate(()=>ipbx_reload());await finish({status:false,message:'Configuration rejected',num_errors:1});
    assert.equal(await page.evaluate(()=>ipbx.conf.reload_needed),true);
    assert.equal(await page.locator('#mt-apply-status[data-state="error"]').isVisible(),true);
    assert.notEqual(await page.locator('body').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
  });
  await run('success explicitly confirms and clears pending changes',async({page,finish})=>{
    await page.evaluate(()=>ipbx_reload());await finish();
    assert.equal(await page.evaluate(()=>ipbx.conf.reload_needed),false);
    assert.equal(await page.locator('#mt-apply-status[data-state="success"]').isVisible(),true);
  });
  await run('warnings are distinct from clean success',async({page,finish})=>{
    await page.evaluate(()=>ipbx_reload());await finish({status:true,num_errors:2,message:'Post hook failed'});
    assert.equal(await page.locator('#mt-apply-status[data-state="warning"]').isVisible(),true);
  });
  await run('error details never execute returned HTML',async({page,finish})=>{
    await page.evaluate(()=>{window.mtInjected=0;ipbx_reload();});
    await finish({status:false,num_errors:1,message:'<img src=x onerror="window.mtInjected=1">',retrieve_conf:'<b>Diagnostic</b>'});
    assert.equal(await page.evaluate(()=>window.mtInjected),0);
    assert.equal(await page.locator('#mt-apply-status pre').textContent().then(t=>t.includes('<img')),true);
  });
  await run('malformed JSON leaves pending state and shows unknown result',async({page,pending})=>{
    await page.evaluate(()=>ipbx_reload());await page.waitForTimeout(100);
    await pending.shift().fulfill({contentType:'application/json',body:'not JSON'});await page.waitForTimeout(150);
    assert.equal(await page.evaluate(()=>ipbx.conf.reload_needed),true);
    assert.equal(await page.locator('#mt-apply-status[data-state="unknown"]').isVisible(),true);
  });
  await run('permission failure directs user to login',async({page,finish})=>{
    await page.evaluate(()=>ipbx_reload());await finish({error:'unauthorized'},401);
    assert.equal(await page.locator('#mt-apply-status[data-state="permission"]').isVisible(),true);
  });
  await run('timeout is uncertain and does not automatically repeat Apply',async({page,pending})=>{
    await page.clock.install();await page.evaluate(()=>ipbx_reload());await page.waitForTimeout(120);
    await page.clock.fastForward(121000);await page.waitForTimeout(100);
    assert.equal(pending.length,1);
    assert.equal(await page.evaluate(()=>ipbx.conf.reload_needed),true);
    assert.equal(await page.locator('#mt-apply-status[data-state="unknown"]').isVisible(),true);
  });
  await browser.close();
  console.log(JSON.stringify(results,null,2));
  process.exitCode=results.some(r=>r.result==='FAIL')?1:0;
})().catch(e=>{console.error(e.message);process.exit(1)});
