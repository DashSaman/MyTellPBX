'use strict';
/* Synthetic, detached form only. No production URL, credentials or module autosave code. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'../..');
const PANEL=process.env.MT_PANEL||path.join(ROOT,'theme');
const OUT=process.env.MT_TEST_OUTPUT,owners=process.env.MT_OWNER_ASSETS;
if(!OUT||!owners)throw new Error('Set MT_TEST_OUTPUT and MT_OWNER_ASSETS to private fixture directories');
fs.mkdirSync(OUT,{recursive:true});
const rows=[['status_ipbx_frontend','checkbox'],['status_anonymous_sip','checkbox'],['ipbx_password','password'],['ipbx_confirm_passwrod','password']];
const html='<!doctype html><html><head><meta charset="UTF-8"></head><body class="mt-body"><main style="padding:24px;max-width:1000px;margin:auto"><form><table><tr><td><button type="submit">Save fixture</button></td></tr></table><table class="tabForm">'+rows.map(([name,type])=>'<tr><td>Fixture</td><td><input id="'+name+'" name="'+name+'" type="'+type+'"></td></tr>').join('')+'</table></form></main></body></html>';
const results=[];
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 for(const theme of ['light','dark'])for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();const attempts=[];
  await context.route('**/*',r=>{if(r.request().isNavigationRequest()&&r.request().url()==='http://fixture.invalid/index.php?menu=sec_advanced_settings')return r.fulfill({contentType:'text/html; charset=utf-8',body:html});attempts.push(r.request().url());return r.abort();});
  await page.goto('http://fixture.invalid/index.php?menu=sec_advanced_settings');
  await page.evaluate(t=>document.documentElement.dataset.mtTheme=t,theme);
  for(const rel of ['css/tokens.css','css/base.css','css/components.css','css/mt-secadv.css','css/theme-dark.css'])await page.addStyleTag({path:path.join(PANEL,rel)});
  await page.addStyleTag({path:path.join(owners,'modules/sec_advanced_settings/themes/default/css/jquery.ibutton.css')});
  await page.addStyleTag({path:path.join(PANEL,'css/workspace.css')});
  await page.addScriptTag({path:path.join(owners,'libs/js/jquery/jquery-1.11.2.min.js')});
  await page.addScriptTag({path:path.join(owners,'modules/sec_advanced_settings/themes/default/js/jquery.ibutton.js')});
  await page.evaluate(()=>{window.changes=0;window.formWrites=0;jQuery.ajax=function(){window.formWrites++;throw new Error('Network prohibited in detached fixture');};jQuery('input[type=checkbox]').iButton({labelOn:'On',labelOff:'Off',change:function(){window.changes++;}});document.querySelector('form').addEventListener('submit',e=>{e.preventDefault();window.formWrites++;});});
  await page.addScriptTag({path:path.join(PANEL,'js/mt-secadv.js')});
  const input=page.locator('#status_ipbx_frontend'),box=page.locator('.ibutton-container').first();
  const inspect=()=>box.evaluate(e=>{const css=n=>{const c=getComputedStyle(n);return {color:c.color,bg:c.backgroundColor,bgImage:c.backgroundImage,display:c.display,outline:c.outline};};const b=e.getBoundingClientRect();return {checked:e.querySelector('input').checked,changes:window.changes,formWrites:window.formWrites,width:b.width,height:b.height,container:css(e),off:css(e.querySelector('.ibutton-label-off')),offLabel:css(e.querySelector('.ibutton-label-off label')),on:css(e.querySelector('.ibutton-label-on')),onLabel:css(e.querySelector('.ibutton-label-on label')),track:css(e.querySelector('.mt-secadv__track')),handle:css(e.querySelector('.ibutton-handle'))};});
  const before=await inspect();assert.equal(before.checked,false);assert.equal(before.track.display,'none');assert.equal(before.offLabel.color,'rgb(36, 50, 74)');assert.equal(before.off.bg,'rgb(220, 229, 242)');
  await page.screenshot({path:path.join(OUT,theme+'-'+width+'-off.png')});
  await input.focus();await input.press('Space');await page.waitForTimeout(300);
  const on=await inspect();assert.equal(on.checked,true);assert.equal(on.changes,1);assert.equal(on.onLabel.color,'rgb(255, 255, 255)');assert.equal(on.on.bg,'rgb(36, 92, 197)');assert.equal(on.container.outline.startsWith('rgb'),true);
  await page.screenshot({path:path.join(OUT,theme+'-'+width+'-on-focus.png')});
  await box.click({position:{x:4,y:13}});await page.waitForTimeout(300);
  const off=await inspect();assert.equal(off.checked,false);assert.equal(off.changes,2);
  await page.evaluate(()=>jQuery('#status_ipbx_frontend').data('iButton').disable(true));
  await box.click({position:{x:4,y:13},force:true});const disabled=await inspect();assert.equal(disabled.checked,false);assert.equal(disabled.changes,2);assert.equal(disabled.formWrites,0);
  results.push({theme,width,result:'PASS',before,on,off,disabled,blockedAssetRequests:attempts.length});
  await context.close();
 }
 await browser.close();fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify(results,null,2));console.log('PASS',results.length,'variants: OFF/ON, keyboard focus, single-change pointer behavior, disabled, no writes');
})().catch(e=>{fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify({results,error:e.stack},null,2));console.error(e);process.exit(1);});
