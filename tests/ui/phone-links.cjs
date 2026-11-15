'use strict';
// Execute the real quick-link controller against local DOM only; no target traffic.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require(process.env.MT_PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'../..'),source=fs.readFileSync(path.join(root,'theme/js/theme.js'),'utf8');
const start=source.indexOf('var isHomePage = function () {'),end=source.indexOf('var homeCardsTimer',start);assert(start>0&&end>start);
const controller=source.slice(start,end)+';window.syncHomeCards=syncHomeCards;syncHomeCards();';
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-proxy-server']});const results=[];
try{const page=await browser.newPage();await page.route('**/*',r=>r.abort());
 for(const canDesk of[true,false])for(const hasPhone of[true,false]){
  await page.setContent('<body '+(canDesk?'data-mt-desk="1" ':'')+(hasPhone?'data-mt-phone="1"':'')+'><div class="neo-module-content"></div></body>');
  await page.evaluate(controller);
  for(let pass=0;pass<3;pass++){
   await page.evaluate(()=>window.syncHomeCards());
   const counts=await page.evaluate(()=>({desk:document.querySelectorAll('#mt-desk-banner').length,phone:document.querySelectorAll('#mt-webphone-card').length,rows:document.querySelectorAll('#mt-home-quicklinks').length}));
   const correct=counts.desk===Number(canDesk)&&counts.phone===Number(hasPhone)&&counts.rows===Number(canDesk||hasPhone);
   results.push({canDesk,hasPhone,pass,counts,correct});
  }
 }
 console.log(JSON.stringify({scope:'offline actual quick-link controller',checks:results.length,failed:results.filter(r=>!r.correct)}));assert(results.every(r=>r.correct),'Unavailable standalone phone is recreated after AJAX');
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
