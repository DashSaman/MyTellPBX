/* Actual native controls and calendar, read-only. Candidate CSS is browser-local.
 * MT_BASE_URL, MT_PANEL_PASSWORD (or MT_PANEL_SESSION) are caller-only secrets.
 * No form setting, Apply or call-control operation is forwarded. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright-core');
const origin=new URL(process.env.MT_BASE_URL).origin;
const output=path.resolve(process.env.MT_EVIDENCE_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'mytell-polish-')));
const candidate=process.env.MT_CANDIDATE_ROOT&&path.resolve(process.env.MT_CANDIDATE_ROOT);
fs.mkdirSync(output,{recursive:true});
const result={mode:candidate?'browser-local CSS preview':'installed baseline',checks:[],blocked:[],candidateAssets:[]};
const save=()=>fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
let browser;
async function check(name,width,theme,fn){try{await fn();result.checks.push({name,width,theme,pass:true});console.log('PASS '+name+' '+width+' '+theme);}catch(e){result.checks.push({name,width,theme,pass:false,error:e.message});console.log('FAIL '+name+' '+width+' '+theme+': '+e.message);}save();}
async function guard(context,auth=false){
 let loginLeft=auth;
 await context.routeWebSocket('**/*',socket=>socket.close());
 await context.route('**/*',async route=>{
  const q=route.request(),u=new URL(q.url());if(u.origin!==origin)return route.abort('blockedbyclient');
  if(!['GET','HEAD','OPTIONS'].includes(q.method())){
   if(loginLeft&&q.method()==='POST'&&['/','/index.php'].includes(u.pathname)&&String(q.postData()).includes('input_pass=')){loginLeft=false;return route.continue();}
   result.blocked.push({method:q.method(),path:u.pathname});return route.fulfill({status:405,body:'Read-only presentation check'});
  }
  for(const k of ['action','command','op','do','cmd','func'])if(u.searchParams.has(k)&&!/^(?:get|read|show|list|load|fetch|status|view|display|retrieve|json)/i.test(u.searchParams.get(k)||''))return route.fulfill({status:405,body:'Read-only presentation check'});
  if(candidate){
   const map={'/themes/mytel/css/theme-dark.css':'theme/css/theme-dark.css','/themes/mytel/css/workspace.css':'theme/css/workspace.css','/admin/assets/mytel/workspace.css':'admin-theme/workspace.css'};
   if(map[u.pathname]){result.candidateAssets.push(map[u.pathname]);return route.fulfill({status:200,contentType:'text/css',body:fs.readFileSync(path.join(candidate,map[u.pathname]))});}
  }
  return route.continue();
 });
}
function calendarInk(){
 const label=document.querySelector('.mt-jtoday-label'),button=document.querySelector('.mt-jtoday .mt-jday-open');
 if(!label||!button)throw Error('Current-day calendar control missing');
 function rgb(s){return (s.match(/[\d.]+/g)||[]).slice(0,3).map(Number);}
 function lum(c){return c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
 const visible=getComputedStyle(label).display!=='none',bg=rgb(getComputedStyle(button).backgroundColor),b=lum(bg),number=button.querySelector('.mt-jday-number')||button;
 const contrast=el=>{const a=lum(rgb(getComputedStyle(el).color));return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
 return {visibleLabel:visible,ratio:Math.min(contrast(number),visible?contrast(label):Infinity),numberRatio:contrast(number),labelRatio:visible?contrast(label):null,background:bg};
}
function textContrasts(selector){
 const rgb=s=>(s.match(/[\d.]+/g)||[]).map(Number),lum=c=>c.slice(0,3).map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 return [...document.querySelectorAll(selector)].filter(el=>el.getClientRects().length&&getComputedStyle(el).display!=='none').map(el=>{
  let bg=null;for(let p=el;p;p=p.parentElement){const v=rgb(getComputedStyle(p).backgroundColor);if(v.length===3||v[3]===1){bg=v;break;}}
  if(!bg)throw Error('Opaque rendered background not found');const a=lum(rgb(getComputedStyle(el).color)),b=lum(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
 });
}
(async()=>{
 browser=await chromium.launch({channel:process.env.MT_BROWSER_CHANNEL||'chrome',headless:true});
 const login=await browser.newContext({ignoreHTTPSErrors:process.env.MT_SELF_SIGNED==='1',serviceWorkers:'block'});await guard(login,true);
 if(process.env.MT_PANEL_SESSION)await login.addCookies([{name:'issabelSession',value:process.env.MT_PANEL_SESSION,url:origin}]);
 const page=await login.newPage();await page.goto(origin,{waitUntil:'domcontentloaded'});
 if(await page.locator('[name=input_user]').count()){
  assert(process.env.MT_PANEL_PASSWORD,'Provide a panel session or caller-only password');
  await page.locator('[name=input_user]').fill(process.env.MT_PANEL_USER||'admin');await page.locator('[name=input_pass]').fill(process.env.MT_PANEL_PASSWORD);
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.locator('[name=submit_login]').click()]);
 }
 await page.locator('#main-menu').waitFor();await page.goto(origin+'/index.php?menu=pbxadmin',{waitUntil:'domcontentloaded'});
 const state=await login.storageState();await login.close();
 for(const width of [1440,390])for(const theme of ['light','dark']){
  const context=await browser.newContext({storageState:state,ignoreHTTPSErrors:process.env.MT_SELF_SIGNED==='1',serviceWorkers:'block',reducedMotion:'reduce',viewport:{width,height:1000}});await guard(context);
  await context.addInitScript(t=>localStorage.setItem('mt-theme',t),theme);const p=await context.newPage();
  await p.goto(origin+'/index.php?menu=calendar',{waitUntil:'domcontentloaded'});await p.locator('.mt-jtoday .mt-jday-open').waitFor({state:'attached'});await p.evaluate(()=>document.fonts.ready);
  await check('today date/label remain legible on their selected fill',width,theme,async()=>{const color=await p.evaluate(calendarInk);assert(color.ratio>=4.5,'Today foreground contrast '+color.ratio.toFixed(2)+' below4.5');});
  await check('today hover retains text contrast',width,theme,async()=>{await p.locator('.mt-jtoday .mt-jday-open').hover();const color=await p.evaluate(calendarInk);assert(color.ratio>=4.5,'Hovered Today contrast '+color.ratio.toFixed(2)+' below4.5');});
  await p.screenshot({path:path.join(output,'calendar-'+width+'-'+theme+'.png'),fullPage:false,animations:'disabled',mask:[p.locator('.user-info,input[type=text],input[type=password]')],maskColor:'#7a8899'});
  await p.goto(origin+'/admin/config.php?display=advancedsettings',{waitUntil:'domcontentloaded'});await p.locator('#pagesearch').waitFor();await p.evaluate(()=>document.fonts.ready);
  await check('native search text starts beyond the search glyph',width,theme,async()=>{
   const m=await p.locator('#pagesearch').evaluate(input=>{const icon=input.parentElement.querySelector('.icon i,.icon svg')||input.parentElement.querySelector('.icon'),r=input.getBoundingClientRect(),b=icon.getBoundingClientRect(),s=getComputedStyle(input);return {textStart:r.left+parseFloat(s.borderLeftWidth)+parseFloat(s.paddingLeft),glyphRight:b.right,iconWidth:b.width};});
   assert(m.iconWidth>0,'Native search glyph missing');assert(m.textStart>=m.glyphRight+6,'Search text begins at '+m.textStart.toFixed(1)+' but glyph ends at '+m.glyphRight.toFixed(1));
  });
  await check('native form direction and checked-choice distinction survive',width,theme,async()=>{
   const m=await p.evaluate(()=>{const group=document.querySelector('.radiotoggle'),selected=group&&group.querySelector('input:checked + label'),plain=group&&[...group.querySelectorAll('label')].find(x=>x!==selected);return {direction:getComputedStyle(document.body).direction,selected:!!selected,selectedFill:selected&&getComputedStyle(selected).backgroundColor,plainFill:plain&&getComputedStyle(plain).backgroundColor,marker:selected&&getComputedStyle(selected,'::before').content};});
   assert.equal(m.direction,'ltr');assert(m.selected,'Checked native choice absent');assert.notEqual(m.selectedFill,m.plainFill);assert(m.marker.includes('✓'),'Selected-choice checkmark missing');
  });
  await check('native search keyboard focus stays visible and contained',width,theme,async()=>{await p.locator('#pagesearch').focus();const m=await p.locator('#pagesearch').evaluate(x=>{const s=getComputedStyle(x);return {focus:document.activeElement===x,style:s.outlineStyle,width:parseFloat(s.outlineWidth),overflow:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)-innerWidth};});assert(m.focus);assert.notEqual(m.style,'none');assert(m.width>=2);assert(m.overflow<=3);});
  await p.screenshot({path:path.join(output,'search-'+width+'-'+theme+'.png'),fullPage:false,animations:'disabled',mask:[p.locator('input[type=password],input[name*=secret],input[name*=token],input[type=text]:not(#pagesearch)')],maskColor:'#7a8899'});
  await p.goto(origin+'/admin/config.php?display=managersettings',{waitUntil:'domcontentloaded'});
  await p.locator('.radiotoggle > input:checked + label').first().waitFor();
  await check('AMI checked choices keep legible foreground without changing their values',width,theme,async()=>{const ratios=await p.evaluate(textContrasts,'.radiotoggle > input:checked + label');assert(ratios.length>=3,'AMI checked choices absent');assert(Math.min(...ratios)>=4.5,'AMI selected-label contrast '+Math.min(...ratios).toFixed(2)+' below4.5');});
  await p.goto(origin+'/index.php?menu=control_panel',{waitUntil:'domcontentloaded'});await p.locator('#controlPanelApplication .statusbar span').first().waitFor();
  await check('operator connection-status text remains legible in the blocked-socket error state',width,theme,async()=>{const ratios=await p.evaluate(textContrasts,'#controlPanelApplication .statusbar span');assert(ratios.length>0);assert(Math.min(...ratios)>=4.5,'Operator status contrast '+Math.min(...ratios).toFixed(2)+' below4.5');});
  await context.close();
 }
 if(candidate){assert(result.candidateAssets.includes('theme/css/theme-dark.css'));assert(result.candidateAssets.includes('theme/css/workspace.css'));assert(result.candidateAssets.includes('admin-theme/workspace.css'));}
 await browser.close();result.completed=new Date().toISOString();save();if(result.checks.some(x=>!x.pass))process.exitCode=1;
})().catch(async e=>{result.fatal=e.message;save();console.error(e.message);if(browser)await browser.close();process.exitCode=1;});
