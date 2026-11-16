'use strict';
/* Execute the real presentation blocks against synthetic UI/customer content.
   The browser never forwards a request or contacts a PBX. */
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'../..');
const python=process.env.PYTHON||(process.platform==='win32'?'python':'python3');
const admin=cp.execFileSync(python,['-B','-c',"import ast,pathlib,sys; p=pathlib.Path('admin-theme/patch-debrand.py'); t=ast.parse(p.read_text(encoding='utf-8')); sys.stdout.buffer.write(ast.literal_eval(next(n.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DEBRAND_JS' for x in n.targets))).encode('utf-8'))"],{cwd:ROOT,encoding:'utf8'});
const theme=fs.readFileSync(path.join(ROOT,'theme/js/theme.js'),'utf8');
const start=theme.indexOf('(function panelDebrand() {'),end=theme.indexOf('\n        })();',start);
assert(start>=0&&end>start,'Actual panel branding block must be available');
const panel=theme.slice(start,end+'\n        })();'.length);
const fixture=`<!doctype html><html lang="en" dir="ltr"><head><title>IssabelPBX Advanced Settings</title></head><body>
<header><a class="navbar-brand" id="brand" href="https://www.issabel.org/" title="IssabelPBX" aria-label="IssabelPBX"><img alt="IssabelPBX">IssabelPBX</a></header>
<h2 id="heading">IssabelPBX Advanced Settings</h2>
<table id="customers"><tbody><tr><td id="company">Issabel Services</td><td><a id="customer-link" href="https://issabel-customer.example/path">Issabel Customer</a></td></tr></tbody></table>
<form id="native" action="/admin/config.php?display=extensions" method="post"><input name="company" value="Issabel Services"><select name="team"><option selected>Issabel support</option></select><textarea name="notes">Issabel customer notes</textarea><input type="radio" name="enabled" value="yes" checked><input type="radio" name="enabled" value="no"></form>
<div contenteditable="true" id="notes"><span>Issabel customer notes</span></div>
<a id="entered-vendor-link" href="https://www.issabel.org/customer-account">User-entered link</a>
<footer><a class="mt-footer-brand-link" id="footer-brand" href="https://issabel.org/">IssabelPBX</a><div class="legal" id="legal">Copyright Issabel Foundation; GPL-2.0 <a id="license-link" href="https://issabel.org/license">Issabel license</a></div></footer>
<pre id="config"><span>issabel.conf: MyTellPBX owner</span></pre><a id="internal" href="#issabel-panels">Open panels</a>
</body></html>`;
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.MT_BROWSER_CHANNEL?{channel:process.env.MT_BROWSER_CHANNEL}:{}),args:['--no-proxy-server']});
 const report={scope:'isolated real branding blocks; synthetic data only',runtimeNetwork:false,cases:[]};
 try{for(const [name,script]of[['admin',admin],['panel',panel]]){
  const context=await browser.newContext({serviceWorkers:'block'}),page=await context.newPage(),blocked=[];
  await context.route('**/*',route=>{blocked.push(route.request().url());return route.abort();});
  await page.setContent(fixture);
  const before=await page.locator('#native').evaluate(form=>({fields:[...new FormData(form)],action:form.getAttribute('action'),method:form.method,html:form.innerHTML}));
  await page.evaluate(()=>{window.$=()=>({ajaxComplete(){}});});
  await page.addScriptTag({content:script});
  const check=async(label,fn)=>{let error;try{await fn();}catch(e){error=e.message;}report.cases.push({block:name,check:label,pass:!error,...(error?{error}: {})});};
  await check('customer text remains exact',async()=>assert.equal(await page.locator('#company').textContent(),'Issabel Services'));
  await check('user links remain exact',async()=>{assert.equal(await page.locator('#customer-link').getAttribute('href'),'https://issabel-customer.example/path');assert.equal(await page.locator('#entered-vendor-link').getAttribute('href'),'https://www.issabel.org/customer-account');});
  await check('native form data and LTR remain exact',async()=>{assert.deepEqual(await page.locator('#native').evaluate(form=>({fields:[...new FormData(form)],action:form.getAttribute('action'),method:form.method,html:form.innerHTML})),before);assert.equal(await page.locator('html').getAttribute('dir'),'ltr');});
  await check('editable notes remain exact',async()=>assert.equal(await page.locator('#notes').textContent(),'Issabel customer notes'));
  await check('legal attribution and link remain exact',async()=>{assert.equal(await page.locator('#legal').textContent(),'Copyright Issabel Foundation; GPL-2.0 Issabel license');assert.equal(await page.locator('#license-link').getAttribute('href'),'https://issabel.org/license');});
  await check('technical identifiers remain exact',async()=>{assert.equal(await page.locator('#config').textContent(),'issabel.conf: MyTellPBX owner');assert.equal(await page.locator('#internal').getAttribute('href'),'#issabel-panels');});
  await check('known product chrome uses exact brand and website',async()=>{assert.equal(await page.locator('#brand').textContent(),'MytelPBX');assert.equal(await page.locator('#heading').textContent(),'MytelPBX Advanced Settings');assert.equal(await page.title(),'MytelPBX Advanced Settings');assert.equal(await page.locator('#brand').getAttribute('href'),'https://mytel.one');assert.equal(await page.locator('#footer-brand').getAttribute('href'),'https://mytel.one');});
  await check('known brand accessibility attributes update',async()=>{for(const attr of['title','aria-label'])assert.equal(await page.locator('#brand').getAttribute(attr),'MytelPBX');assert.equal(await page.locator('#brand img').getAttribute('alt'),'MytelPBX');});
  await page.evaluate(()=>{const h=document.createElement('h2');h.id='async-brand';h.textContent='IssabelPBX Advanced Settings';document.body.append(h);const td=document.createElement('td');td.id='async-customer';td.textContent='Issabel New Customer';document.querySelector('#customers tr').append(td);});
  await page.waitForTimeout(500);
  await check('async branding preserves async customer data',async()=>{assert.equal(await page.locator('#async-brand').textContent(),'MytelPBX Advanced Settings');assert.equal(await page.locator('#async-customer').textContent(),'Issabel New Customer');});
  await check('no network requests',async()=>assert.deepEqual(blocked,[]));
  await context.close();
 }}finally{await browser.close();}
 report.pass=report.cases.length===20&&report.cases.every(c=>c.pass);
 if(process.env.MT_TEST_OUTPUT){fs.mkdirSync(process.env.MT_TEST_OUTPUT,{recursive:true});fs.writeFileSync(path.join(process.env.MT_TEST_OUTPUT,'branding-context.json'),JSON.stringify(report,null,2)+'\n');}
 console.log(JSON.stringify(report,null,2));if(!report.pass)process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=2;});
