/* Synthetic events only. Every REST write is intercepted locally. */
'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const base=process.env.MT_TEST_URL, candidate=process.env.MT_CANDIDATE;
const output=process.env.MT_TEST_OUTPUT||process.cwd();
const results=[];
const fixture={id:999999,title:'بررسی جلسه هماهنگی',start:'2026-11-15T10:00:00+01:00',end:'2026-11-15T11:00:00+01:00',allDay:false,color:'#3366CC',url:'/rest.php/calendar/CalendarEvent/999999'};
const detail={...fixture,subject:fixture.title,description:'رویداد آزمایشی مرورگر',starttime:fixture.start,endtime:fixture.end,asterisk_call:false,recording:'',call_to:'',reminder_timer:10,emails_notification:[]};
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 for(const zone of ['Asia/Tehran','America/Los_Angeles']){
  const context=await browser.newContext({ignoreHTTPSErrors:true,timezoneId:zone,viewport:{width:1440,height:1000}});
  const page=await context.newPage();page.setDefaultTimeout(6000);
  const errors=[],writes=[],ranges=[],pendingWrites=[],pendingFeeds=[];let feedMode='normal',saveMode='normal',activeFixture=fixture;
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.locator('[name=input_user]').fill(process.env.MT_TEST_USER||'admin');
  await page.locator('[name=input_pass]').fill(process.env.MT_TEST_PASSWORD);
  await Promise.all([page.waitForNavigation({waitUntil:'domcontentloaded'}),page.locator('[name=submit_login]').click()]);
  await context.routeWebSocket('**/*',socket=>socket.close());
  await page.route('**/*',async route=>{
   const req=route.request(),u=new URL(req.url());if(u.origin!==base)return route.abort();
   if(u.pathname.startsWith('/rest.php/calendar/CalendarEvent')){
    if(req.method()!=='GET'){writes.push({method:req.method(),path:u.pathname,data:req.postData()});if(saveMode==='delay'){pendingWrites.push(route);return;}if(saveMode==='html')return route.fulfill({status:200,contentType:'text/html',body:'<html>Login</html>'});return route.fulfill({status:204,body:''});}
    if(u.pathname.endsWith('/999999'))return route.fulfill({json:detail});
    const start=u.searchParams.get('startdate')||new Date(Number(u.searchParams.get('start'))*1000).toISOString().slice(0,10);
    const end=u.searchParams.get('enddate')||new Date(Number(u.searchParams.get('end'))*1000).toISOString().slice(0,10);ranges.push({start,end});
    if(feedMode==='delay'){pendingFeeds.push(route);return;}
    if(feedMode==='error')return route.fulfill({status:500,body:'fixture failure'});
    if(feedMode==='html')return route.fulfill({contentType:'text/html',body:'<html>Login</html>'});
    const rows=feedMode==='empty'?[]:start<=activeFixture.start.slice(0,10)&&end>activeFixture.start.slice(0,10)?[activeFixture]:[];
    return route.fulfill({json:rows});
   }
   if(!['GET','HEAD'].includes(req.method())||u.searchParams.has('action'))return route.fulfill({status:405,body:'Blocked test mutation'});
   if(candidate){
    if(u.pathname.startsWith('/themes/mytel/')){
     const file=path.join(candidate,'panel',u.pathname.slice('/themes/mytel/'.length));if(fs.existsSync(file))return route.fulfill({path:file});
    }
    if(u.pathname==='/modules/calendar/themes/default/js/javascript.js')return route.fulfill({path:path.join(candidate,'legacy',u.pathname.slice(1))});
    if(u.pathname==='/index.php'&&u.searchParams.get('menu')==='calendar'){
     const response=await route.fetch();let html=await response.text();
     html=html.replace('</head>','<link rel="stylesheet" href="/themes/mytel/css/workspace.css?v=752"><link rel="stylesheet" href="/themes/mytel/css/mt-calendar.css?v=752"></head>');
     html=html.replace(/(<script[^>]+src="[^"]*\/js\/mt-calendar.js[^>]*>)/,'<script src="/themes/mytel/js/calendar-core.js?v=752"></script><script src="/themes/mytel/js/calendar-editor.js?v=752"></script>$1');
     html=html.replace('<input type="hidden" name="server_year"','<input type="hidden" name="server_timezone" value="Europe/Berlin"><input type="hidden" name="server_year"');
     html=html.replace('<table class="tabForm"','<table class="mt-calendar-layout"');
     html=html.replace('</body>','<script src="/themes/mytel/js/workspace.js?v=752"></script></body>');
     return route.fulfill({response,body:html});
    }
   }
   return route.continue();
  });
  const run=async(name,fn)=>{try{await fn();results.push({zone,name,result:'PASS'});}catch(e){results.push({zone,name,result:'FAIL',error:e.message.slice(0,500)});}};
  await page.goto(base+'/index.php?menu=calendar',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.MTCalendar&&document.querySelector('.mt-jmonth-title')?.textContent);
  await run('Complete Aban range includes event beyond native Gregorian feed',async()=>{
   await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('gotoDate',new Date(2026,9,23,12)));
   await page.locator('.mt-jevent:visible').waitFor();
   assert.ok(ranges.some(r=>r.start==='2026-10-17'&&r.end==='2026-11-28'));
   assert.match(await page.locator('.mt-jmonth-title').innerText(),/آبان/);
   assert.equal(await page.locator('.mt-jevent:visible').count(),1);
   assert.match(await page.locator('.mt-jweekday').first().getAttribute('title'),/شنبه/);
  });
  await run('Event opens directly with preserved civil time and color',async()=>{
   await page.locator('.mt-jevent:visible').click();await page.locator('#mt-event-date').waitFor();
   await page.waitForFunction(()=>document.querySelector('#mt-event-date').value==='1405/08/24');
   assert.equal(await page.locator('#mt-event-date-time').inputValue(),'10:00');
   assert.equal(await page.locator('#colorSelector .colorpicker-box').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(51, 102, 204)');
  });
  await run('Invalid Jalali date never submits a stale canonical value',async()=>{
   const before=writes.length;await page.locator('#mt-event-date').fill('1404/12/30');
   await page.locator('.ui-dialog-buttonpane button').first().click();
   assert.equal(writes.length,before);assert.equal(await page.locator('#mt-event-date').getAttribute('aria-invalid'),'true');
  });
  await run('Persian entry saves the same event, color and server wall time',async()=>{
   await page.locator('#mt-event-date').fill('۱۴۰۵/۰۸/۲۴');await page.locator('#mt-event-date-time').fill('۱۰:۰۰');
   await page.locator('.ui-dialog-buttonpane button').first().click();await page.waitForTimeout(100);
   const posted=writes.at(-1),data=new URLSearchParams(posted.data);
   assert.equal(posted.path,fixture.url);assert.equal(data.get('startdate'),'2026-11-15 10:00:00');assert.equal(data.get('color'),'#3366cc');assert.equal(data.get('clear_notifications'),'1');
  });
  await run('Browser DST gap does not normalize the editor time',async()=>{
   await page.locator('.mt-jevent:visible').click();await page.locator('#mt-event-date').waitFor();
   await page.waitForFunction(()=>document.querySelector('#mt-event-date').value==='1405/08/24');
   await page.evaluate(d=>fillEventDialog({...d,starttime:'2027-03-14T02:30:00+01:00',endtime:'2027-03-14T03:30:00+01:00'}),detail);
   assert.equal(await page.locator('#mt-event-date-time').inputValue(),'02:30');
   assert.equal(await page.locator('[name=date]').inputValue(),'2027-03-14 02:30');
  });
  await run('Login HTML after Save is not reported as successful',async()=>{
   saveMode='html';await page.locator('.ui-dialog-buttonpane button').first().click();await page.waitForTimeout(150);
   assert.equal(await page.locator('#calendar_eventdialog').isVisible(),true);assert.match(await page.locator('#mt-event-message').innerText(),/نشست/);
   saveMode='normal';await page.evaluate(()=>jQuery('#calendar_eventdialog').dialog('close'));
  });
  await run('Pending save cannot close the editor or submit twice',async()=>{
   await page.locator('.mt-jevent:visible').click();await page.waitForFunction(()=>document.querySelector('#mt-event-date')?.value==='1405/08/24');
   saveMode='delay';const before=writes.length;await page.locator('.ui-dialog-buttonpane button').first().click();await page.waitForTimeout(100);
   await page.evaluate(()=>{jQuery('#calendar_eventdialog').dialog('close');saveEventDialog('/rest.php/calendar/CalendarEvent/999999');});
   assert.equal(await page.locator('#calendar_eventdialog').isVisible(),true);assert.equal(writes.length,before+1);
   saveMode='normal';await Promise.all(pendingWrites.splice(0).map(r=>r.fulfill({status:204,body:''})));await page.locator('#calendar_eventdialog').waitFor({state:'hidden'});
  });
  await run('New events have positive duration; equal end is rejected',async()=>{
   await page.locator('#calendar_newevent').click();await page.locator('#mt-event-date').waitFor();
   assert.ok(await page.evaluate(()=>document.querySelector('[name=date]').value<document.querySelector('[name=to]').value));
   await page.locator('#mt-event-to').fill(await page.locator('#mt-event-date').inputValue());await page.locator('#mt-event-to-time').fill(await page.locator('#mt-event-date-time').inputValue());
   const before=writes.length;await page.locator('.ui-dialog-buttonpane button').first().click();assert.equal(writes.length,before);assert.match(await page.locator('#mt-event-message').innerText(),/پایان/);
   await page.evaluate(()=>jQuery('#calendar_eventdialog').dialog('close'));
  });
  await run('New event default preserves server clock inside browser DST gap',async()=>{
   const value=await page.evaluate(()=>{
    const OriginalDate=window.Date;
    try{window.Date=class extends OriginalDate{constructor(...args){super(...(args.length?args:['2027-03-14T01:30:00Z']));}};
     document.getElementById('calendar_newevent').click();return document.querySelector('#calendar_eventdialog [name=date]').value;
    }finally{window.Date=OriginalDate;}
   });
   assert.equal(value,'2027-03-14 02:30');await page.evaluate(()=>jQuery('#calendar_eventdialog').dialog('close'));
  });
  await run('Week is Saturday-first and uses Jalali title',async()=>{
   await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('changeView','agendaWeek'));await page.waitForTimeout(200);
   assert.equal(await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('getView').start.getDay()),6);
   assert.match(await page.locator('.fc-header-title').innerText(),/آبان/);
   assert.equal(await page.locator('.fc-button-agendaWeek').getAttribute('aria-pressed'),'true');
   assert.equal(await page.locator('.fc-button-month').getAttribute('aria-pressed'),'false');
  });
  await run('Week agenda preserves server time inside a browser DST gap',async()=>{
   activeFixture={...fixture,start:'2027-03-14T02:30:00+01:00',end:'2027-03-14T03:30:00+01:00'};
   await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('gotoDate',new Date(2027,2,14,12)));
   await page.waitForFunction(()=>document.querySelector('.mt-jagenda .mt-agenda-time')?.textContent==='۰۲:۳۰');
   assert.equal(await page.locator('.mt-jagenda .mt-agenda-time').innerText(),'۰۲:۳۰');
   if(zone==='Asia/Tehran')await page.screenshot({path:path.join(output,'calendar-week.png'),fullPage:true});
   activeFixture=fixture;
  });
  await run('Day-specific New fills the selected day without a server write',async()=>{
   await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('changeView','agendaDay'));await page.locator('.mt-jagenda .mt-agenda-create').waitFor();
   const before=writes.length;await page.locator('.mt-jagenda .mt-agenda-create').click();await page.locator('#mt-event-date').waitFor();
   assert.equal((await page.locator('#calendar_eventdialog [name=date]').inputValue()).slice(0,10),'2027-03-14');
   assert.ok(await page.evaluate(()=>document.querySelector('#calendar_eventdialog [name=date]').value<document.querySelector('#calendar_eventdialog [name=to]').value));
   assert.equal(writes.length,before);await page.evaluate(()=>jQuery('#calendar_eventdialog').dialog('close'));
  });
  await run('Month navigation retains events on returning from week/day',async()=>{
   await page.evaluate(()=>{jQuery('#calendar_main').fullCalendar('changeView','month');jQuery('#calendar_main').fullCalendar('gotoDate',new Date(2026,9,23,12));});
   await page.locator('.mt-jevent:visible').waitFor();
   await page.locator('[data-action=next]').click();await page.waitForTimeout(150);
   await page.locator('[data-action=prev]').click();await page.locator('.mt-jevent:visible').waitFor();
  });
  await run('Feed error is explicit and retry restores events',async()=>{
   feedMode='error';await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('refetchEvents'));
   await page.locator('[data-action=retry]').waitFor();assert.equal(await page.locator('.mt-jevent:visible').count(),0);
   feedMode='normal';await page.locator('[data-action=retry]').click();await page.locator('.mt-jevent:visible').waitFor();
  });
  await run('Expired-session HTML is not an empty calendar',async()=>{
   feedMode='html';await page.evaluate(()=>jQuery('#calendar_main').fullCalendar('refetchEvents'));await page.locator('[data-action=retry]').waitFor();
   feedMode='normal';await page.locator('[data-action=retry]').click();await page.locator('.mt-jevent:visible').waitFor();
  });
  await run('Obsolete month response cannot replace the current month',async()=>{
   feedMode='delay';await page.locator('[data-action=next]').click();await page.waitForTimeout(120);
   feedMode='normal';await page.locator('[data-action=prev]').click();await page.locator('.mt-jevent:visible').waitFor();
   await Promise.all(pendingFeeds.splice(0).map(r=>r.fulfill({json:[]}).catch(()=>{})));await page.waitForTimeout(100);
   assert.match(await page.locator('.mt-jmonth-title').innerText(),/آبان/);assert.equal(await page.locator('.mt-jevent:visible').count(),1);
  });
  await run('Sidebar and week Today use the same server civil day',async()=>{
   await page.evaluate(()=>{window.savedCalendarNow=MTCalendarCore.now;MTCalendarCore.now=()=>new Date(2027,0,1,23,10);});
   await page.locator('.mt-calside-today').click();assert.equal(await page.evaluate(()=>MTCalendarCore.key(jQuery('#calendar_main').fullCalendar('getDate'))),'2027-01-01');
   await page.evaluate(()=>{jQuery('#calendar_main').fullCalendar('changeView','agendaWeek');jQuery('#calendar_main').fullCalendar('gotoDate',new Date(2025,0,1));});
   await page.locator('.fc-button-today').click();assert.equal(await page.evaluate(()=>MTCalendarCore.key(jQuery('#calendar_main').fullCalendar('getDate'))),'2027-01-01');
   await page.evaluate(()=>{MTCalendarCore.now=savedCalendarNow;jQuery('#calendar_main').fullCalendar('changeView','month');jQuery('#calendar_main').fullCalendar('gotoDate',new Date(2026,9,23,12));});await page.locator('.mt-jevent:visible').waitFor();
  });
  for(const theme of ['light','dark'])for(const width of [1440,390])await run(theme+' '+width+' month and editor fit viewport',async()=>{
   await page.setViewportSize({width,height:width===390?844:1000});await page.evaluate(t=>{document.documentElement.setAttribute('data-mt-theme',t);localStorage.setItem('mt-theme',t);},theme);
   await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(150);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(zone==='Asia/Tehran'&&theme==='light'&&width===390)fs.writeFileSync(path.join(output,'geometry.json'),JSON.stringify(await page.evaluate(()=>({form:document.getElementById('formCalendar').outerHTML.slice(0,2500),today:[...document.querySelectorAll('.mt-jtoday .mt-jday-number')].map(x=>({color:getComputedStyle(x).color,parent:getComputedStyle(x.parentNode).backgroundColor}))})),null,2));
   if(zone==='Asia/Tehran'){fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,`calendar-${theme}-${width}.png`),fullPage:true});}
   await page.locator('#calendar_newevent').click();await page.locator('#mt-event-date').waitFor();
   const box=await page.locator('.mt-calendar-dialog').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1);assert.ok(box.y>=0&&box.y+box.height<=(width===390?844:1000)+1);
   await page.locator('.mt-event-date button').first().click();await page.locator('.mt-event-picker [data-day]').first().waitFor();
   const saveBox=await page.locator('.ui-dialog-buttonpane button').first().boundingBox();assert.ok(saveBox.y>=0&&saveBox.y+saveBox.height<=(width===390?844:1000));
   if(zone==='Asia/Tehran')await page.screenshot({path:path.join(output,`calendar-editor-${theme}-${width}.png`),fullPage:true});
   await page.evaluate(()=>jQuery('#calendar_eventdialog').dialog('close'));
  });
  await run('No uncaught JavaScript exceptions',async()=>assert.deepEqual(errors,[]));
  await context.close();
 }
 await browser.close();console.log(JSON.stringify(results,null,2));if(results.some(r=>r.result==='FAIL'))process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1);});
