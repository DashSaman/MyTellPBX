/* Dashboard feedback and text boundaries. All applet requests are browser-local
 * fixtures; no configuration, history cleanup, service actions or calls run. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),os=require('node:os');
const{chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright-core');
const{installRoutes}=require('./audit.cjs');
const fixtureHTML={SystemResources:'<input id="cpugauge_value" value="0"><input id="memgauge_value" value="0.2"><input id="swapgauge_value" value="0">',CommunicationActivity:'<span id="communication_activity_rx_bytes">0</span><span id="communication_activity_tx_bytes">0</span>',PerformanceGraphic:'<div id="dashboard-applet-performancegraph" style="width:400px;height:200px"></div><script>$.plot("#dashboard-applet-performancegraph",[{"data":[[0,0]]}],{});</script>',HardDrives:'<div id="dashboard-applet-hd-usage"></div>Hard Disk Capacity: 10 GB Used 20%'};
const origin=new URL(process.env.MT_BASE_URL).origin,out=path.resolve(process.env.MT_EVIDENCE_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'mytell-dashboard-')));
fs.mkdirSync(out,{recursive:true});const result={checks:[],localFeeds:[],blockedWrites:[],harnessSha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex')};let browser;
const save=()=>fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
async function check(name,key,fn){try{await fn();result.checks.push({name,key,pass:true});}catch(e){result.checks.push({name,key,pass:false,error:e.message.slice(0,400)});}save();}
(async()=>{assert(process.env.MT_PANEL_SESSION,'Authenticated panel session required');browser=await chromium.launch({executablePath:process.env.MT_CHROMIUM_PATH||undefined,channel:process.env.MT_CHROMIUM_PATH?undefined:'chrome',headless:true});
for(const width of (process.env.MT_UI_WIDTHS||'1440,390').split(',').map(Number))for(const theme of ['light','dark']){
 const key=width+'-'+theme,context=await browser.newContext({ignoreHTTPSErrors:process.env.MT_SELF_SIGNED==='1',serviceWorkers:'block',viewport:{width,height:1000}}),events={blocked:[],external:new Set()};await installRoutes(context,events);await context.addCookies([{name:'issabelSession',value:process.env.MT_PANEL_SESSION,url:origin}]);await context.addInitScript(t=>localStorage.setItem('mt-theme',t),theme);
 let mode='error';const pending=[];
 await context.route('**/index.php**',async route=>{const req=route.request(),u=new URL(req.url()),params=new URLSearchParams(u.search);for(const[k,v]of new URLSearchParams(req.postData()||''))params.set(k,v);const action=params.get('action'),applet=params.get('applet');
  if(u.origin===origin&&['dashboard','index'].includes(params.get('menu'))&&['getContent','updateStatus'].includes(action)){
   result.localFeeds.push({key,mode,applet,action});
   if(mode==='hang'){pending.push(route);return;}
   const fail=mode==='error'||mode==='partial'&&applet!=='SystemResources';
   if(mode==='html')return route.fulfill({contentType:'text/html',body:'<!doctype html><title>Expired session fixture</title>'});
   if(fail)return route.fulfill({status:503,contentType:'application/json',body:'{"status":"error","message":"Unavailable fixture"}'});
   if(action==='updateStatus'&&applet==='SystemResources')return route.fulfill({json:{status:{cpugauge:0,memgauge:.2,swapgauge:0}}});
   return route.fulfill({json:{status:'success',html:mode==='empty'?'   ':mode==='malformed'?'<div>Unexpected nonempty response</div>':fixtureHTML[applet]||'<div>Fixture data</div>'}});
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
 mode='malformed';await poll();await check('nonempty malformed success HTML cannot claim healthy metrics',key,()=>expectState('partial'));
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
 if(width===1440&&theme==='light'){
  mode='ready';for(const name of ['SystemResources','CommunicationActivity','PerformanceGraphic','HardDrives'])await poll(name);
  async function observe(applet,action,data,status=200){await p.evaluate(({applet,action,data,status})=>{const xhr={status,responseText:JSON.stringify(data)},settings={url:'index.php?menu=index&applet='+applet+'&action='+action};jQuery(document).trigger('ajaxSend',[xhr,settings]);jQuery(document).trigger('ajaxComplete',[xhr,settings]);},{applet,action,data,status});}
  await check('native formatted traffic strings remain valid successful observations',key,async()=>{await observe('CommunicationActivity','updateStatus',{status:'success',rx_bytes:'1,234.56',tx_bytes:'0.20'});await expectState('ready');});
  await check('blank gauge fractions cannot be interpreted as valid zero',key,async()=>{await observe('SystemResources','getContent',{status:'success',html:'<input id="cpugauge_value" value="   "><input id="memgauge_value" value="0"><input id="swapgauge_value" value="0">'});await expectState('partial');await poll();});
  await check('an empty performance host has an explicit no-data qualification',key,async()=>{await observe('PerformanceGraphic','getContent',{status:'success',html:'<div id="dashboard-applet-performancegraph"></div><script>$.plot("#dashboard-applet-performancegraph",[],{});</script>'});await expectState('partial');await poll('PerformanceGraphic');});
  await check('native thousands separators preserve actual disk capacity',key,async()=>{await observe('HardDrives','getContent',{status:'success',html:'<div id="dashboard-applet-hd-usage"></div>Hard Disk Capacity: 1,234.56 GB Used 20%'});assert.equal(await p.evaluate(()=>window.__mtDisk.total),1234.56);});
  await check('a late older failure cannot overwrite a newer successful observation',key,async()=>{await p.evaluate(html=>{const settings={url:'index.php?menu=dashboard&action=getContent&applet=SystemResources'},older={status:503,responseText:'{}'},newer={status:200,responseText:JSON.stringify({status:'success',html})};jQuery(document).trigger('ajaxSend',[older,settings]);jQuery(document).trigger('ajaxSend',[newer,settings]);jQuery(document).trigger('ajaxComplete',[newer,settings]);jQuery(document).trigger('ajaxComplete',[older,settings]);},fixtureHTML.SystemResources);await expectState('ready');});
  await check('a healthy feed cannot hide a latest sibling request hung past its deadline',key,async()=>{
   for(const name of ['SystemResources','CommunicationActivity','PerformanceGraphic','HardDrives'])await poll(name);
   await p.evaluate(()=>{const now=Date.now,at=now(),pending={status:200,responseText:''},settings={url:'index.php?menu=index&applet=CommunicationActivity&action=getContent'};jQuery(document).trigger('ajaxSend',[pending,settings]);try{Date.now=()=>at+16000;const xhr={status:200,responseText:JSON.stringify({status:{cpugauge:0,memgauge:.2,swapgauge:0}})},healthy={url:'index.php?menu=index&applet=SystemResources&action=updateStatus'};jQuery(document).trigger('ajaxSend',[xhr,healthy]);jQuery(document).trigger('ajaxComplete',[xhr,healthy]);}finally{Date.now=now;}});await expectState('partial');await poll('CommunicationActivity');
  });
  await check('recent healthy metrics do not make an expired dynamic sibling fresh',key,async()=>{
   for(const name of ['SystemResources','CommunicationActivity','PerformanceGraphic','HardDrives'])await poll(name);
   await p.evaluate(()=>{const now=Date.now,at=now();try{Date.now=()=>at+91000;const xhr={status:200,responseText:JSON.stringify({status:{cpugauge:0,memgauge:.2,swapgauge:0}})},settings={url:'index.php?menu=index&applet=SystemResources&action=updateStatus'};jQuery(document).trigger('ajaxSend',[xhr,settings]);jQuery(document).trigger('ajaxComplete',[xhr,settings]);}finally{Date.now=now;}});await expectState('partial');
  });
  await check('a same-grid dashboard rebuild rejects the preceding element response',key,async()=>{await p.evaluate(html=>{const settings={url:'index.php?menu=dashboard&action=getContent&applet=SystemResources'},xhr={status:200,responseText:JSON.stringify({status:'success',html})};jQuery(document).trigger('ajaxSend',[xhr,settings]);const old=document.getElementById('mt-dash');old.replaceWith(old.cloneNode(true));jQuery(document).trigger('ajaxComplete',[xhr,settings]);},fixtureHTML.SystemResources);assert.equal(await state(),'loading');});
  await check('a rebuilt dashboard cannot inherit ready from cached globals or old requests',key,async()=>{
   await p.evaluate(()=>{const settings={url:'index.php?menu=dashboard&action=getContent&applet=SystemResources'},xhr={status:200,responseText:JSON.stringify({status:'success',html:'<input id="cpugauge_value" value="0"><input id="memgauge_value" value="0"><input id="swapgauge_value" value="0">'})};window.__mtLateFixture={xhr,settings};jQuery(document).trigger('ajaxSend',[xhr,settings]);for(const id of ['applet_grid','mt-dash']){const old=document.getElementById(id);old.replaceWith(old.cloneNode(true));}window.__mtFreshAt=Date.now();window.__mtSys={CPU:0,RAM:20,SWAP:0};window.__mtDisk={total:10,usedPct:20};jQuery(document).trigger('ajaxComplete',[xhr,settings]);});
   assert.equal(await state(),'loading');assert.equal(await p.evaluate(()=>window.__mtFreshAt),0);
  });
  await check('a hung initial feed reaches bounded visible feedback without retrying',key,async()=>{
   mode='hang';const hung=await context.newPage();await hung.clock.install();await hung.goto(origin+'/index.php?menu=dashboard',{waitUntil:'domcontentloaded'});await hung.locator('#mt-fresh').waitFor();await hung.clock.fastForward(15001);await hung.clock.fastForward(15001);assert.equal(await hung.locator('#mt-fresh').getAttribute('data-state'),'error');assert.doesNotMatch(await hung.locator('#mt-fresh').textContent(),/در حال دریافت/);await hung.close();
  });
  await check('an absent optional applet does not leave the remaining feeds pending',key,async()=>{
   mode='ready';await p.evaluate(()=>document.getElementById('Applet_PerformanceGraphic')?.remove());for(const name of ['SystemResources','CommunicationActivity','HardDrives'])await poll(name);await expectState('ready');
  });
 }
 await p.screenshot({path:path.join(out,key+'.png'),mask:[p.locator('input,.mt-user-name,.user-info,#mt-dash-sys')],maskColor:'#7a8899'});result.blockedWrites.push(...events.blocked);await context.close();
}
 result.completed=new Date().toISOString();save();await browser.close();console.log(JSON.stringify({checks:result.checks.length,failed:result.checks.filter(x=>!x.pass)}));process.exitCode=result.checks.some(x=>!x.pass)?1:0;
})().catch(async e=>{result.fatal=e.message;save();if(browser)await browser.close();process.exitCode=2;});
