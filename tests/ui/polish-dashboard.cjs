/* Dashboard feedback and text boundaries. All applet requests are browser-local
 * fixtures; no configuration, history cleanup, service actions or calls run. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),os=require('node:os');
const{chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright-core');
const{installRoutes}=require('./audit.cjs');
const origin=new URL(process.env.MT_BASE_URL).origin,out=path.resolve(process.env.MT_EVIDENCE_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'mytell-dashboard-')));
fs.mkdirSync(out,{recursive:true});const result={checks:[],localFeeds:[],blockedWrites:[],harnessSha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex')};let browser;
const save=()=>fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
async function check(name,key,fn){try{await fn();result.checks.push({name,key,pass:true});}catch(e){result.checks.push({name,key,pass:false,error:e.message.slice(0,400)});}save();}
(async()=>{assert(process.env.MT_PANEL_SESSION,'Authenticated panel session required');browser=await chromium.launch({executablePath:process.env.MT_CHROMIUM_PATH||undefined,channel:process.env.MT_CHROMIUM_PATH?undefined:'chrome',headless:true});
for(const width of (process.env.MT_UI_WIDTHS||'1440,390').split(',').map(Number))for(const theme of ['light','dark']){
 const key=width+'-'+theme,context=await browser.newContext({ignoreHTTPSErrors:process.env.MT_SELF_SIGNED==='1',serviceWorkers:'block',viewport:{width,height:1000}}),events={blocked:[],external:new Set()};await installRoutes(context,events);await context.addCookies([{name:'issabelSession',value:process.env.MT_PANEL_SESSION,url:origin}]);await context.addInitScript(t=>localStorage.setItem('mt-theme',t),theme);
 let mode='error';
 await context.route('**/index.php**',async route=>{const req=route.request(),u=new URL(req.url()),params=new URLSearchParams(u.search);for(const[k,v]of new URLSearchParams(req.postData()||''))params.set(k,v);const action=params.get('action'),applet=params.get('applet');
  if(u.origin===origin&&params.get('menu')==='dashboard'&&['getContent','updateStatus'].includes(action)){
   result.localFeeds.push({key,mode,applet,action});
   const fail=mode==='error'||mode==='partial'&&applet!=='SystemResources';
   if(mode==='html')return route.fulfill({contentType:'text/html',body:'<!doctype html><title>Expired session fixture</title>'});
   if(fail)return route.fulfill({status:503,contentType:'application/json',body:'{"status":"error","message":"Unavailable fixture"}'});
   if(action==='updateStatus'&&applet==='SystemResources')return route.fulfill({json:{status:{cpugauge:0,memgauge:.2,swapgauge:0}}});
   return route.fulfill({json:{status:'success',html:mode==='empty'?'   ':'<div class="fixture-dashboard-content">Read-only fixture data</div>'}});
  }
  if(action)return route.fulfill({status:405,body:'Read-only fixture blocked action'});return route.fallback();
 });
 const p=await context.newPage();await p.goto(origin+'/index.php?menu=dashboard',{waitUntil:'domcontentloaded'});await p.locator('#mt-fresh').waitFor();
 const state=()=>p.locator('#mt-fresh').getAttribute('data-state');
 async function expectState(expected){await p.waitForFunction(s=>document.getElementById('mt-fresh')?.dataset.state===s,expected,{timeout:2000});assert.equal(await state(),expected);assert.equal(await p.locator('#mt-fresh').getAttribute('role'),'status');assert.equal(await p.locator('#mt-fresh').getAttribute('aria-live'),'polite');assert.doesNotMatch(await p.locator('#mt-fresh').textContent(),/در حال دریافت/);}
 async function poll(applet='SystemResources',action='getContent'){await p.evaluate(({applet,action})=>new Promise(resolve=>jQuery.ajax({url:'index.php',data:{menu:'dashboard',rawmode:'yes',applet,action}}).always(()=>resolve())),{applet,action});}
 await check('HTTP503 has visible accessible dashboard failure feedback',key,()=>expectState('error'));
 mode='empty';await poll();await poll('CommunicationActivity');await poll('PerformanceGraphic');await poll('HardDrives');await check('successful empty feeds stop indefinite loading',key,()=>expectState('empty'));
 mode='partial';await poll();await poll('CommunicationActivity');await poll('PerformanceGraphic');await poll('HardDrives');await check('healthy metrics do not hide a failed sibling feed',key,()=>expectState('partial'));
 mode='ready';for(const applet of ['SystemResources','CommunicationActivity','PerformanceGraphic','HardDrives'])await poll(applet);
 await check('healthy feed recovery clears only resolved failures',key,()=>expectState('ready'));
 await check('unchanged successful polling advances observation freshness',key,async()=>{const before=await p.evaluate(()=>window.__mtFreshAt);await p.waitForTimeout(30);await poll('SystemResources','updateStatus');assert((await p.evaluate(()=>window.__mtFreshAt))>before);await expectState('ready');});
 mode='html';await poll();await check('HTTP200 login HTML is a failed feed and retained data stays qualified',key,()=>expectState('partial'));
 await check('dashboard feedback remains inside viewport',key,async()=>assert((await p.evaluate(()=>Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)-innerWidth))<=3));
 if(width===1440&&theme==='light'){
  await check('system information stays literal when source text contains markup',key,async()=>{
   await p.evaluate(()=>{window.__mtDashInjected=0;const full=document.querySelector('#Applet_SystemResources .appletwindow_fullcontent'),line=document.createElement('div'),lab=document.createElement('span'),value=document.createElement('span');line.className='neo-applet-tline';lab.className='neo-applet-titem';lab.textContent='پردازنده';value.className='neo-applet-tdesc';value.textContent='<img src=x onerror="window.__mtDashInjected=1">';line.append(lab,value);full.replaceChildren(line);jQuery(document).trigger('ajaxComplete',[{status:200,responseText:'{}'},{url:'index.php?menu=unrelated'}]);});await p.waitForTimeout(1500);assert.equal(await p.evaluate(()=>window.__mtDashInjected),0);assert.match(await p.locator('#mt-dash-sys').textContent(),/<img/);assert.equal(await p.locator('#mt-dash-sys img').count(),0);
  });
  await check('unrelated and failed responses cannot replace trusted disk readings',key,async()=>{
   await p.evaluate(()=>{window.__mtDisk={total:10,usedPct:20};jQuery(document).trigger('ajaxComplete',[{status:200,responseText:'{"status":"success","html":"Hard Disk Capacity: 999 GB Used 88%"}'},{url:'index.php?menu=cdrreport'}]);});assert.deepEqual(await p.evaluate(()=>window.__mtDisk),{total:10,usedPct:20});
   await p.evaluate(()=>jQuery(document).trigger('ajaxComplete',[{status:503,responseText:'{"status":"error","html":"Hard Disk Capacity: 888 GB Used 77%"}'},{url:'index.php?menu=dashboard&action=getContent&applet=HardDrives'}]));assert.deepEqual(await p.evaluate(()=>window.__mtDisk),{total:10,usedPct:20});
  });
  await check('aborted navigation does not replace an observed feed state',key,async()=>{const before=await state();await p.evaluate(()=>jQuery(document).trigger('ajaxComplete',[{status:0,statusText:'abort',responseText:''},{url:'index.php?menu=dashboard&action=getContent&applet=SystemResources'}]));assert.equal(await state(),before);});
 }
 await p.screenshot({path:path.join(out,key+'.png'),mask:[p.locator('input,.mt-user-name,.user-info,#mt-dash-sys')],maskColor:'#7a8899'});result.blockedWrites.push(...events.blocked);await context.close();
}
 result.completed=new Date().toISOString();save();await browser.close();console.log(JSON.stringify({checks:result.checks.length,failed:result.checks.filter(x=>!x.pass)}));process.exitCode=result.checks.some(x=>!x.pass)?1:0;
})().catch(async e=>{result.fatal=e.message;save();if(browser)await browser.close();process.exitCode=2;});
