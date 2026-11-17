'use strict';
/* Execute the real presentation blocks against synthetic UI/customer content.
   The browser never forwards a request or contacts a PBX. */
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
const python=process.env.PYTHON||(process.platform==='win32'?'python':'python3');
const admin=cp.execFileSync(python,['-B','-c',"import ast,pathlib,sys; p=pathlib.Path('admin-theme/patch-debrand.py'); t=ast.parse(p.read_text(encoding='utf-8')); sys.stdout.buffer.write(ast.literal_eval(next(n.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DEBRAND_JS' for x in n.targets))).encode('utf-8'))"],{cwd:ROOT,encoding:'utf8'});
const theme=fs.readFileSync(path.join(ROOT,'theme/js/theme.js'),'utf8');
const start=theme.indexOf('(function panelDebrand() {'),end=theme.indexOf('\n        })();',start);
assert(start>=0&&end>start,'Actual panel branding block must be available');
const panel=theme.slice(start,end+'\n        })();'.length);
const subtitles=fs.readFileSync(path.join(ROOT,'installer/payload/admin/assets/mytel/sub.js'),'utf8');
const settingsLabels=['Disable IssabelPBX dbug Logging','Disable IssabelPBX Log','IssabelPBX Log File','IssabelPBX Log Routing','IssabelPBX Web Address'];
const fixture=`<!doctype html><html lang="en" dir="ltr"><head><title>IssabelPBX Advanced Settings</title></head><body>
<header><a class="navbar-brand" id="brand" href="https://www.issabel.org/" title="IssabelPBX" aria-label="IssabelPBX"><img alt="IssabelPBX">IssabelPBX</a></header>
<h2 id="heading">IssabelPBX Advanced Settings</h2>
<h2 id="customer-heading" title="IssabelPBX">Issabel Services</h2>
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
  await check('customer text remains exact',async()=>{assert.equal(await page.locator('#company').textContent(),'Issabel Services');assert.equal(await page.locator('#customer-heading').textContent(),'Issabel Services');assert.equal(await page.locator('#customer-heading').getAttribute('title'),'IssabelPBX');});
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
  for(const [label,title]of[['customer title remains exact','Issabel Services - Customer'],['legal title remains exact','Issabel Foundation License']]){
   await page.evaluate(value=>{document.title=value;document.body.append(document.createElement('span'));},title);
   await page.waitForTimeout(350);
   await check(label,async()=>assert.equal(await page.title(),title));
  }
  await check('no network requests',async()=>assert.deepEqual(blocked,[]));
  await context.close();
 }
 const context=await browser.newContext({serviceWorkers:'block'}),page=await context.newPage(),requests=[];
 await context.route('**/*',route=>{requests.push(route.request().url());return route.abort();});
 await page.setContent('<html dir="ltr"><body><form id="settings">'+settingsLabels.map((label,i)=>'<div class="column tdsearch" id="setting-'+i+'">'+label+'</div><input name="native_'+i+'" value="retained-'+i+'">').join('')+'<select name="PHP_ERROR_HANDLER_OUTPUT"><option selected>issabelpbxlog</option></select><input name="USE_ISSABELPBX_MENU_CONF" value="issabelpbx_menu.conf"></form><div id="customer-label">IssabelPBX Web Address</div><table><tr><td class="column tdsearch" id="customer-table-label">IssabelPBX Log File</td></tr></table><pre id="technical">issabelpbxlog issabelpbx_menu.conf</pre></body></html>');
 const before=await page.locator('#settings').evaluate(f=>[...new FormData(f)]);
 await page.addScriptTag({content:subtitles});
 const check=async(label,fn)=>{let error;try{await fn();}catch(e){error=e.message;}report.cases.push({block:'native-labels',check:label,pass:!error,...(error?{error}: {})});};
 await check('five known native human labels use MytelPBX',async()=>{for(let i=0;i<settingsLabels.length;i++)assert.equal(await page.locator('#setting-'+i).evaluate(el=>[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.nodeValue).join('').trim()),settingsLabels[i].replace('IssabelPBX','MytelPBX'));});
 await check('Persian subtitles survive the label branding',async()=>{for(let i=0;i<settingsLabels.length;i++)assert(await page.locator('#setting-'+i+' > .mt-sub').count());});
 await check('all technical keys and submitted values remain exact',async()=>{assert.deepEqual(await page.locator('#settings').evaluate(f=>[...new FormData(f)]),before);assert.equal(await page.locator('#technical').textContent(),'issabelpbxlog issabelpbx_menu.conf');assert.equal(await page.locator('html').getAttribute('dir'),'ltr');});
 await check('customer labels outside native settings remain exact',async()=>{assert.equal(await page.locator('#customer-label').textContent(),'IssabelPBX Web Address');assert.equal(await page.locator('#customer-table-label').textContent(),'IssabelPBX Log File');});
 await page.evaluate(()=>{const row=document.createElement('div');row.id='late-setting';row.className='column tdsearch';row.textContent='IssabelPBX Web Address';document.querySelector('#settings').append(row);});
 await page.waitForTimeout(500);
 await check('late native label retains subtitle and exact values',async()=>{assert.equal(await page.locator('#late-setting').evaluate(el=>el.firstChild.nodeValue),'MytelPBX Web Address');assert.equal(await page.locator('#late-setting > .mt-sub').count(),1);assert.deepEqual(await page.locator('#settings').evaluate(f=>[...new FormData(f)]),before);});
 await check('native label fixture forwards no requests',async()=>assert.deepEqual(requests,[]));
 await context.close();
 const callbacks={},overlays=[],frameWindow={location:{href:'about:blank'},addEventListener(name,cb){callbacks[name]=cb;},removeEventListener(){}},frame={contentWindow:frameWindow,addEventListener(name,cb){callbacks['frame-'+name]=cb;}};
 const jq=selector=>selector==='#myframe'?{length:1,get:()=>frame}:{LoadingOverlay:(action,options)=>overlays.push({action,options})};
 vm.runInNewContext(fs.readFileSync(path.join(ROOT,'theme/js/iframe-show-loader.js'),'utf8'),{window:{},document:{getElementById:()=>frame},$:jq,setTimeout:cb=>cb(),calcHeight(){}});
 callbacks.unload();
 let loaderError;try{assert.equal(overlays[0].action,'show');assert.equal(overlays[0].options.image,'/themes/mytel/images/mt-spinner.svg');assert(fs.existsSync(path.join(ROOT,'theme/images/mt-spinner.svg')));}catch(e){loaderError=e.message;}
 report.cases.push({block:'loader',check:'real loader callback uses existing Mytel spinner',pass:!loaderError,...(loaderError?{error:loaderError}:{})});
 }finally{await browser.close();}
 report.pass=report.cases.length===31&&report.cases.every(c=>c.pass);
 if(process.env.MT_TEST_OUTPUT){fs.mkdirSync(process.env.MT_TEST_OUTPUT,{recursive:true});fs.writeFileSync(path.join(process.env.MT_TEST_OUTPUT,'branding-context.json'),JSON.stringify(report,null,2)+'\n');}
 console.log(JSON.stringify(report,null,2));if(!report.pass)process.exitCode=1;
})().catch(error=>{console.error(error.message);process.exitCode=2;});
