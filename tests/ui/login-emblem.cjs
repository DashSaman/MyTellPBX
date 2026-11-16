'use strict';
/* Actual login CSS/SVG in an isolated browser fixture; never forwards requests. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const ROOT=path.resolve(__dirname,'../..'),OUT=process.env.MT_TEST_OUTPUT,ORIGIN='https://login-fixture.invalid';
assert(OUT,'Set MT_TEST_OUTPUT to a private evidence directory');fs.mkdirSync(OUT,{recursive:true});
const files={
 '/tokens.css':'theme/css/tokens.css','/login.css':'theme/css/login.css',
 '/images/mytel-emblem.svg':'theme/images/mytel-emblem.svg','/images/mytel-logo.png':'theme/images/mytel-logo.png'
};
const bodies=Object.fromEntries(Object.entries(files).map(([url,file])=>[url,fs.readFileSync(path.join(ROOT,file))]));
const template=fs.readFileSync(path.join(ROOT,'theme/_common/login.tpl'),'utf8');
const header=template.match(/<div class="mt-login-cardhead">[\s\S]*?<\/div>/)?.[0];assert(header,'Actual login header unavailable');
const renderedHeader=header.replace('{$WEBPATH}themes/{$THEMENAME}/images/mytel-emblem.svg','/images/mytel-emblem.svg').replace('{$PAGE_NAME}','صفحه ورود');
assert(renderedHeader.includes('/images/mytel-emblem.svg')&&!renderedHeader.includes('{$'),'Unexpected actual header template');
assert(bodies['/images/mytel-emblem.svg'].toString().includes('path fill="#FFFFFF"'),'Fixture foreground must match the actual white phone');
const report={scope:'isolated actual login header/CSS/SVG fixture',runtimeNetwork:false,hashes:Object.fromEntries(Object.entries(bodies).map(([url,bytes])=>[files[url],crypto.createHash('sha256').update(bytes).digest('hex')])),cases:[]};
const luminance=rgb=>rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.MT_BROWSER_CHANNEL?{channel:process.env.MT_BROWSER_CHANNEL}:{}),args:['--no-proxy-server']});
 try{for(const width of [1440,390])for(const theme of ['light','dark']){
  const context=await browser.newContext({viewport:{width,height:width===390?844:1000},serviceWorkers:'block'}),page=await context.newPage(),blocked=[];
  await context.route('**/*',route=>{
   const u=new URL(route.request().url());if(u.origin!==ORIGIN){blocked.push(u.origin);return route.abort();}
   if(u.pathname==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<!doctype html><html lang="fa" dir="rtl" data-mt-theme="${theme}"><head><meta charset="utf-8"><link rel="stylesheet" href="/tokens.css"><link rel="stylesheet" href="/login.css"></head><body class="mt-login-body"><img id="nav-control" src="/images/mytel-emblem.svg" style="position:fixed;top:12px;left:12px;width:36px;height:36px" alt=""><div class="mt-login-stage"><div class="mt-login-brandpane"></div><div class="mt-login-panel"><div class="mt-login-card">${renderedHeader}</div></div></div></body></html>`});
   if(bodies[u.pathname])return route.fulfill({contentType:u.pathname.endsWith('.css')?'text/css':u.pathname.endsWith('.svg')?'image/svg+xml':'image/png',body:bodies[u.pathname]});
   blocked.push(u.pathname);return route.abort();
  });
  let result={width,theme,pass:false};
  try{
   await page.goto(ORIGIN+'/');await page.locator('.mt-login-emblem-sm').evaluate(async image=>{await image.decode();});
   result.geometry=await page.locator('.mt-login-emblem-sm').evaluate(image=>{
    let color=[255,255,255],chain=[];for(let e=image;e;e=e.parentElement)chain.unshift(e);
    for(const e of chain){const parts=getComputedStyle(e).backgroundColor.match(/[\d.]+/g)?.map(Number)||[0,0,0,0],a=parts.length===4?parts[3]:1;color=color.map((v,i)=>parts[i]*a+v*(1-a));}
    const r=image.getBoundingClientRect(),c=image.closest('.mt-login-card').getBoundingClientRect();
    return {background:color,naturalWidth:image.naturalWidth,width:r.width,height:r.height,withinCard:r.left>=c.left&&r.right<=c.right&&r.top>=c.top&&r.bottom<=c.bottom,navBackground:getComputedStyle(document.querySelector('#nav-control')).backgroundColor,overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth)};
   });
   result.contrast=1.05/(luminance(result.geometry.background)+.05);
   assert(result.contrast>=3,'White phone disappears into the actual login-card background: contrast '+result.contrast.toFixed(2));
   assert(result.geometry.naturalWidth===64&&result.geometry.width===46&&result.geometry.height===46&&result.geometry.withinCard,'Actual emblem geometry changed or clips');
   assert.equal(result.geometry.navBackground,'rgba(0, 0, 0, 0)','Login fix leaked into a navigation emblem');assert.equal(result.geometry.overflow,0);assert.deepEqual(blocked,[]);
   result.pass=true;
  }catch(error){result.error=error.message;process.exitCode=1;}
  await page.screenshot({path:path.join(OUT,theme+'-'+width+'.png')});report.cases.push(result);await context.close();
 }}finally{await browser.close();report.pass=report.cases.length===4&&report.cases.every(row=>row.pass);fs.writeFileSync(path.join(OUT,'report.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({pass:report.pass,passed:report.cases.filter(row=>row.pass).length,cases:report.cases.length,evidence:OUT}));}
})().catch(error=>{console.error(error.message);process.exitCode=2;});
