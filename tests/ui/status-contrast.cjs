'use strict';
/* Inert reproductions of observed native status DOM; every request stays local.
 * logfiles.css: .red{color:red}, #log_view.pre background#0f192a/white,
 * native SHA ddc9080cb18c77dc36cf215ebde81ea4a15a2ad0f77dda9b6a5f0e15e700b6a4.
 * dashboard/page.index.php show_syslog() emits the critical li/syslog_text/h4,
 * tooltip-icon span and date span (source98341244ad55a7881ad3c5a7a1a6c29aa0727f2bcff27d0e598c2951c70f57ef).
 * Historical RCONFFAIL measured inherited white on rgb246,146,29; its data is
 * replaced by synthetic labels here, with no native DB or notification action.
 */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright');
const ROOT=path.resolve(__dirname,'../..'),OUT=process.env.MT_TEST_OUTPUT;
assert(OUT,'Set MT_TEST_OUTPUT to private evidence');fs.mkdirSync(OUT,{recursive:true});
const ORIGIN='https://status-style-fixture.invalid',sources={
 '/workspace.css':'admin-theme/workspace.css','/dark.css':'admin-theme/mt-admin-dark.css',
 '/skin.css':'installer/payload/admin/assets/mytel/skin.css','/themes/mytel/css/tokens.css':'theme/css/tokens.css'
};
const bytes=Object.fromEntries(Object.entries(sources).map(([url,file])=>[url,fs.readFileSync(path.join(ROOT,file))]));
const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
const nativeCSS=`.red{color:red}.orange{color:orange}#log_view.pre{font-family:"Courier New",Courier,monospace;font-size:.85em;overflow:scroll;background-color:#0f192a;color:white;padding:10px;border-radius:10px;margin-bottom:3em;margin-top:3em}
#syslog li.notify_critical{background:#f6921d;color:white}#syslog li.notify_critical h4{color:inherit}`;
const report={scope:'local real-browser CSS cascade and measured native status DOM',networkForwarded:false,configWrites:false,
 hashes:Object.fromEntries(Object.entries(bytes).map(([url,body])=>[sources[url],crypto.createHash('sha256').update(body).digest('hex')])),cases:[]};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.MT_BROWSER_CHANNEL?{channel:process.env.MT_BROWSER_CHANNEL}:{}),args:['--no-proxy-server']});
 try{for(const width of [1440,390])for(const theme of ['light','dark'])for(const reversed of [false,true]){
  const context=await browser.newContext({viewport:{width,height:600},serviceWorkers:'block'}),page=await context.newPage(),blocked=[];
  await context.route('**/*',route=>{
   const url=new URL(route.request().url());if(url.origin!==ORIGIN){blocked.push('[external]');return route.abort();}
   if(url.pathname==='/')return route.fulfill({contentType:'text/html;charset=utf-8',body:`<!doctype html><html lang="en" dir="ltr" data-mt-theme="${theme}"><head><meta charset="utf-8"><link rel="stylesheet" href="/skin.css">${(reversed?['dark','workspace']:['workspace','dark']).map(name=>'<link rel="stylesheet" href="/'+name+'.css">').join('')}<style>${nativeCSS}</style></head><body>
<main class="content"><div id="log_view" class="pre" tabindex="0"><span class="red">Synthetic ERROR: configuration check</span><br><span class="orange">Synthetic WARNING: unchanged severity</span></div>
<span id="outside-error" class="red">Unrelated red text</span><div id="syslog"><ul>
<li id="notify_item_issabelpbx_RCONFFAIL" class="notify_critical"><div><div class="syslog_text"><h4><span class="has-tooltip-right"><i class="mr-2 fa fa-exclamation-circle has-text-danger-dark"></i></span><span class="mr-2">Synthetic timestamp</span>Synthetic configuration failure</h4><div class="notification_buttons"><button id="notice-action" type="button">Details</button></div></div><div class="syslog_detail">Synthetic details remain visible</div></div></li>
<li id="unrelated-notice" class="notify_critical"><div><div class="syslog_text"><h4><span class="mr-2">Other timestamp</span>Unrelated notice</h4></div></div></li>
</ul></div></main></body></html>`});
   if(bytes[url.pathname])return route.fulfill({contentType:'text/css',body:bytes[url.pathname]});
   if(url.pathname==='/themes/mytel/css/fonts.css')return route.fulfill({contentType:'text/css',body:'/* No remote fonts needed for color/focus assertions. */'});
   blocked.push(url.pathname);return route.abort();
  });
  const row={width,theme,reversed,pass:false};
  try{
   await page.goto(ORIGIN+'/');row.targets=await page.evaluate(()=>{
    const rgb=v=>v.match(/[\d.]+/g).slice(0,3).map(Number);
    return ['#log_view span.red','#notify_item_issabelpbx_RCONFFAIL h4','#notify_item_issabelpbx_RCONFFAIL h4 > span.mr-2'].map(selector=>{
     const el=document.querySelector(selector),s=getComputedStyle(el);let p=el,bg;
     while(p){const v=getComputedStyle(p).backgroundColor;if(v!=='rgba(0, 0, 0, 0)'&&v!=='transparent'){bg=rgb(v);break;}p=p.parentElement;}
     return {selector,foreground:rgb(s.color),background:bg,visible:!!el.getClientRects().length&&s.visibility!=='hidden'&&s.display!=='none'};
    });});
   for(const target of row.targets){target.contrast=contrast(target.foreground,target.background);assert(target.visible,'Status content must remain visible');}
   assert(row.targets.every(target=>target.contrast>=4.5),'Native status contrast below4.5: '+row.targets.map(t=>t.contrast.toFixed(3)).join(','));
   assert.deepEqual(row.targets[0].background,[15,25,42],'Native dark log well must stay unchanged');assert.deepEqual(row.targets[1].background,[246,146,29],'Severity background must stay unchanged');
   assert.deepEqual(row.targets[1].foreground,row.targets[2].foreground,'Timestamp must inherit readable heading ink');
   const scope=await page.evaluate(()=>({outside:getComputedStyle(document.querySelector('#outside-error')).color,other:getComputedStyle(document.querySelector('#unrelated-notice h4')).color,warning:getComputedStyle(document.querySelector('#log_view .orange')).color,direction:getComputedStyle(document.body).direction,details:!!document.querySelector('.syslog_detail').getClientRects().length}));
   assert.equal(scope.outside,'rgb(255, 0, 0)');assert.equal(scope.other,'rgb(255, 255, 255)');assert.equal(scope.warning,'rgb(255, 165, 0)');assert.equal(scope.direction,'ltr');assert(scope.details);
   await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.id),'log_view');await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.id),'notice-action');
   const focus=await page.locator('#notice-action').evaluate(el=>{const s=getComputedStyle(el);return {width:parseFloat(s.outlineWidth),style:s.outlineStyle,visible:!!el.getClientRects().length};});assert(focus.width>=3&&focus.style!=='none'&&focus.visible,'Keyboard focus must remain visible');assert.deepEqual(blocked,[]);
   await page.locator('#notify_item_issabelpbx_RCONFFAIL').evaluate(el=>{el.style.display='none';});assert.equal(await page.locator('#notify_item_issabelpbx_RCONFFAIL').isVisible(),false,'CSS must respect native dismissal');
   row.pass=true;
  }catch(error){row.error=error.message;process.exitCode=1;}
  report.cases.push(row);await context.close();
 }}finally{await browser.close();report.pass=report.cases.length===8&&report.cases.every(row=>row.pass);fs.writeFileSync(path.join(OUT,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.cases.filter(r=>r.pass).length,cases:report.cases.length,scope:report.scope,evidence:OUT}));}
})().catch(e=>{console.error(e.message);process.exitCode=2;});
