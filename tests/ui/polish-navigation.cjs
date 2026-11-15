/* Read-only native mobile geometry and keyboard access. Caller supplies a
 * panel session. Responses may use browser-local candidate assets only. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright-core');
const {installRoutes}=require('./audit.cjs');
const origin=new URL(process.env.MT_BASE_URL).origin,out=path.resolve(process.env.MT_EVIDENCE_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'mytell-nav-')));
fs.mkdirSync(out,{recursive:true});const result={checks:[],blockedWrites:[]};let browser;
const save=()=>fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
async function check(name,width,theme,fn){try{await fn();result.checks.push({name,width,theme,pass:true});console.log('PASS '+name+' '+width+' '+theme);}catch(e){result.checks.push({name,width,theme,pass:false,error:e.message});console.log('FAIL '+name+' '+width+' '+theme+': '+e.message);}save();}
(async()=>{
 assert(process.env.MT_PANEL_SESSION,'Caller-only authenticated panel session required');browser=await chromium.launch({executablePath:process.env.MT_CHROMIUM_PATH||undefined,channel:process.env.MT_CHROMIUM_PATH?undefined:'chrome',headless:true});
 for(const width of (process.env.MT_UI_WIDTHS||'1440,390').split(',').map(Number))for(const theme of ['light','dark']){
  const context=await browser.newContext({ignoreHTTPSErrors:process.env.MT_SELF_SIGNED==='1',serviceWorkers:'block',reducedMotion:'reduce',viewport:{width,height:1000}});
  const events={blocked:[],external:new Set()};await installRoutes(context,events);await context.addCookies([{name:'issabelSession',value:process.env.MT_PANEL_SESSION,url:origin}]);await context.addInitScript(t=>localStorage.setItem('mt-theme',t),theme);
  const p=await context.newPage();await p.goto(origin+'/index.php?menu=pbxadmin',{waitUntil:'domcontentloaded'});await p.goto(origin+'/admin/config.php?display=asteriskinfo',{waitUntil:'domcontentloaded'});await p.locator('.mt-pagedesc-toggle').waitFor();await p.evaluate(()=>document.fonts.ready);
  await check('legacy report content and help stay usable without hidden horizontal clipping',width,theme,async()=>{
   const m=await p.evaluate(()=>{const c=document.querySelector('#page_body > .content'),h=document.querySelector('.mt-pagedesc-toggle'),r=c.getBoundingClientRect(),b=h.getBoundingClientRect(),nav=document.querySelector('#page_body > div.rnav');return {width:r.width,helpLeft:b.left,helpRight:b.right,direction:getComputedStyle(document.body).direction,navPosition:getComputedStyle(nav).position,overflow:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)-innerWidth};});
   assert.equal(m.direction,'ltr');assert(m.width>=(width<=700?width-60:width-350),'Content width collapsed to '+m.width.toFixed(1));assert(m.helpLeft>=0&&m.helpRight<=width,'Help control is clipped');assert(m.overflow<=3);if(width>700)assert.equal(m.navPosition,'fixed','Desktop native navigation position must remain intact');
  });
  if(width<1024)await check('mobile native menu supports keyboard activation and exposes its actual state',width,theme,async()=>{
   const burger=p.locator('.navbar-burger').first();assert(await burger.isVisible());assert(await burger.evaluate(el=>el.tabIndex>=0),'Menu trigger is absent from keyboard order');await burger.focus();await p.keyboard.press('Enter');
   const expanded=await burger.getAttribute('aria-expanded');assert.equal(expanded,'true');const id=await burger.getAttribute('aria-controls');assert(id,'Menu trigger lacks controlled region');assert(await p.locator('#'+id).isVisible());
   await p.keyboard.press('Escape');assert.equal(await burger.getAttribute('aria-expanded'),'false');assert(await burger.evaluate(el=>document.activeElement===el));
  });
  if(width<1024)await check('native menu button semantics include Space without duplicate activation',width,theme,async()=>{
   const burger=p.locator('.navbar-burger').first(),id=await burger.getAttribute('data-target');assert(id);const target=p.locator('#'+id);
   if(await target.evaluate(el=>el.classList.contains('is-active')))await burger.click();
   await burger.focus();await p.keyboard.press('Space');assert(await target.evaluate(el=>el.classList.contains('is-active')),'Space did not open the menu');
   await burger.click();assert.equal(await target.evaluate(el=>el.classList.contains('is-active')),false);
  });
  if(width>=1024)await check('desktop menu options remain reachable when their group receives keyboard focus',width,theme,async()=>{
   const groups=p.locator('.navbar-start > .navbar-item.has-dropdown');assert(await groups.count()>0);
   for(let i=0;i<await groups.count();i++){
    const group=groups.nth(i),link=group.locator(':scope > .navbar-link');await link.focus();const menu=group.locator(':scope > .navbar-dropdown');
    const focus=await link.evaluate(el=>({active:document.activeElement===el,tabIndex:el.tabIndex,attribute:el.getAttribute('tabindex'),tag:el.tagName,disabled:el.getAttribute('aria-disabled'),onfocus:el.getAttribute('onfocus'),inert:!!el.closest('[inert]'),display:getComputedStyle(el).display,width:el.getBoundingClientRect().width,activeTag:document.activeElement.tagName,activeId:document.activeElement.id}));
    assert(focus.active,'Native menu group is absent from keyboard focus: '+JSON.stringify(focus));
    assert(await menu.isVisible(),'Keyboard focus did not reveal a native menu');
    const r=await menu.boundingBox();assert(r.x>=0&&r.x+r.width<=width,'Native menu is clipped by viewport at '+r.x.toFixed(1)+' width '+r.width.toFixed(1));
    await p.keyboard.press('Tab');
    const child=await menu.evaluate(el=>{const active=document.activeElement,s=getComputedStyle(active);return {inside:el.contains(active),link:active.matches('a[href]'),outline:s.outlineStyle,width:parseFloat(s.outlineWidth)};});
    assert(child.inside&&child.link,'Tab did not reach a native menu option');assert.notEqual(child.outline,'none');assert(child.width>=2);
    assert(Math.abs((await menu.boundingBox()).x-r.x)<1,'Repeated focus compounded the menu translation');
   }
  });
  if(width>=1024)await check('pointer-open native menus stay entirely inside the viewport',width,theme,async()=>{
   const groups=p.locator('.navbar-start > .navbar-item.has-dropdown');assert(await groups.count()>0);
   for(let i=0;i<await groups.count();i++){const group=groups.nth(i);await group.locator(':scope > .navbar-link').hover();const menu=group.locator(':scope > .navbar-dropdown');assert(await menu.isVisible());const r=await menu.boundingBox();assert(r.x>=0&&r.x+r.width<=width,'Pointer menu is clipped at '+r.x.toFixed(1)+' width '+r.width.toFixed(1));}
  });
  if(width>=1024)await check('menu fitting preserves native vertical transforms and resets only its own offset on resize',width,theme,async()=>{
   const group=p.locator('.navbar-start > .navbar-item.has-dropdown').last(),menu=group.locator(':scope > .navbar-dropdown'),heading=group.locator(':scope > .navbar-link');
   await menu.evaluate(el=>{el.style.setProperty('transform','translateY(3px)','important');el.setAttribute('data-mt-preserve-fixture','');});
   await p.addStyleTag({content:'.navbar-dropdown[data-mt-preserve-fixture]{translate:0px 2px;}'});
   await heading.hover();await heading.focus();
   const before=await menu.boundingBox();
   const native=()=>menu.evaluate(el=>({vertical:new DOMMatrixReadOnly(getComputedStyle(el).transform).m42,inlineTransform:el.style.transform,priority:el.style.getPropertyPriority('transform'),translateY:parseFloat(getComputedStyle(el).translate.split(/\s+/)[1]),fitted:el.classList.contains('mt-native-menu-fit'),offset:el.style.getPropertyValue('--mt-menu-shift')}));
   let m=await native();assert.equal(m.vertical,3,'Fitting changed the desktop vertical transform');assert.equal(m.translateY,2,'Fitting changed the native translate Y');assert(before.x>=0&&before.x+before.width<=width);
   await p.setViewportSize({width:1023,height:1000});await p.waitForTimeout(60);m=await native();result.transformProbes=result.transformProbes||[];result.transformProbes.push({width,theme,mobile:m});assert.equal(m.inlineTransform,'translateY(3px)','Clearing the fit changed the native inline transform');assert.equal(m.priority,'important');assert.equal(m.translateY,2);assert.equal(m.fitted,false);assert.equal(m.offset,'');
   await p.setViewportSize({width,height:1000});await heading.hover();await heading.focus();
   const after=await menu.boundingBox();assert(Math.abs(after.x-before.x)<1,'Resize compounded the native menu offset');m=await native();assert.equal(m.vertical,3,'Resize changed the native transform');assert.equal(m.translateY,2);
  });
  await p.screenshot({path:path.join(out,'report-'+width+'-'+theme+'.png'),fullPage:false,animations:'disabled',mask:[p.locator('input[type=text],input[type=password],textarea')],maskColor:'#7a8899'});
  await p.goto(origin+'/admin/config.php?display=vmblast',{waitUntil:'domcontentloaded'});await p.locator('.chosen-container-multi .chosen-search-input').waitFor();
  await check('multi-select search field fits its visible native container',width,theme,async()=>{const m=await p.locator('.chosen-container-multi .chosen-search-input').evaluate(el=>{const r=el.getBoundingClientRect(),b=el.closest('.chosen-choices').getBoundingClientRect();return {left:r.left,right:r.right,parentLeft:b.left,parentRight:b.right};});assert(m.left>=m.parentLeft-1&&m.right<=m.parentRight+1,'Multi-select search extends beyond its container by '+(m.right-m.parentRight).toFixed(1)+'px');});
  result.blockedWrites.push(...events.blocked);await context.close();
 }
 await browser.close();result.completed=new Date().toISOString();save();if(result.checks.some(c=>!c.pass))process.exitCode=1;
})().catch(async e=>{result.fatal=e.message;save();console.error(e.message);if(browser)await browser.close();process.exitCode=1;});
