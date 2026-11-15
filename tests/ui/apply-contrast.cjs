'use strict';
/* Actual admin CSS cascade only; no PBX URL, credentials, save or reload. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),ROOT=path.resolve(__dirname,'../..'),OUT=process.env.MT_TEST_OUTPUT;
assert(OUT,'Set MT_TEST_OUTPUT to private evidence');fs.mkdirSync(OUT,{recursive:true});
const ORIGIN='https://apply-style-fixture.invalid',sources={
 '/workspace.css':'admin-theme/workspace.css','/dark.css':'admin-theme/mt-admin-dark.css',
 '/themes/mytel/css/tokens.css':'theme/css/tokens.css'
};
const bytes=Object.fromEntries(Object.entries(sources).map(([url,file])=>[url,fs.readFileSync(path.join(ROOT,file))]));
const lum=color=>color.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05);
const report={scope:'actual admin CSS cascade fixture',forwardedNetwork:false,reloadRequests:0,hashes:Object.fromEntries(Object.entries(bytes).map(([url,body])=>[sources[url],crypto.createHash('sha256').update(body).digest('hex')])),cases:[]};
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.MT_BROWSER_CHANNEL?{channel:process.env.MT_BROWSER_CHANNEL}:{}),args:['--no-proxy-server']});
 try{for(const width of [1440,390])for(const theme of ['light','dark'])for(const reversed of [false,true]){
  const context=await browser.newContext({viewport:{width,height:300},serviceWorkers:'block'}),page=await context.newPage();const blocked=[];
  await context.route('**/*',route=>{
   const u=new URL(route.request().url());if(u.origin!==ORIGIN){blocked.push(u.origin);return route.abort();}
   if(u.pathname==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html lang="en" dir="ltr" data-mt-theme="${theme}"><head><meta charset="utf-8">${(reversed?['dark','workspace']:['workspace','dark']).map(file=>'<link rel="stylesheet" href="/'+file+'.css">').join('')}</head><body><nav class="navbar is-dark"><a id="button_reload" href="#" role="button">Apply Config</a></nav><form><label>NAT <input type="radio" name="nat" value="yes" checked> yes</label></form></body></html>`});
   if(bytes[u.pathname])return route.fulfill({contentType:'text/css',body:bytes[u.pathname]});
   if(u.pathname==='/themes/mytel/css/fonts.css')return route.fulfill({contentType:'text/css',body:'/* Fonts do not affect this color-only fixture. */'});
   blocked.push(u.pathname);return route.abort();
  });
  const row={width,theme,reversed,pass:false};
  try{
   await page.goto(ORIGIN+'/');row.computed=await page.locator('#button_reload').evaluate(element=>{const s=getComputedStyle(element),rgb=value=>value.match(/[\d.]+/g).slice(0,3).map(Number);return {foreground:rgb(s.color),background:rgb(s.backgroundColor),direction:getComputedStyle(document.body).direction};});
   row.contrast=contrast(row.computed.foreground,row.computed.background);
   assert(row.contrast>=4.5,'Apply Config text contrast '+row.contrast.toFixed(2)+' is below4.5');assert.equal(row.computed.direction,'ltr');assert.deepEqual(blocked,[]);
   await page.locator('#button_reload').evaluate(element=>{element.style.display='none';});assert.equal(await page.locator('#button_reload').isVisible(),false,'Native hide must still work');
   row.pass=true;
  }catch(error){row.error=error.message;process.exitCode=1;}
  report.cases.push(row);await context.close();
 }}finally{await browser.close();report.pass=report.cases.length===8&&report.cases.every(row=>row.pass);fs.writeFileSync(path.join(OUT,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.cases.filter(row=>row.pass).length,cases:report.cases.length,evidence:OUT}));}
})().catch(error=>{console.error(error.message);process.exitCode=2;});
