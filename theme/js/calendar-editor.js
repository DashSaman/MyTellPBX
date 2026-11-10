/* Adapter for the installed FullCalendar 1.6 / calendar REST contract. */
(function (window, document, $) {
    'use strict';
    if (!$) return;
    var fields=[], saving=false, generation=0;
    var core=function(){return window.MTCalendarCore;};
    function el(tag,cls,text){var n=document.createElement(tag);n.className=cls||'';if(text!==undefined)n.textContent=text;return n;}
    function btn(text){var n=el('button','',text);n.type='button';return n;}
    function message(text) {
        var box=document.getElementById('mt-event-message');
        if(!box) {box=el('p','mt-event-message');box.id='mt-event-message';box.setAttribute('role','alert');document.getElementById('calendar_eventdialog').prepend(box);}
        box.textContent=text||'';
    }
    function error(result) {
        message(result && (result.status===401 || result.status===403) ? 'نشست شما معتبر نیست؛ دوباره وارد سامانه شوید.' : 'عملیات انجام نشد. اتصال و اطلاعات رویداد را بررسی کنید و دوباره تلاش کنید.');
    }
    function busy(value) {
        saving=value;
        var dialog=$('#calendar_eventdialog');
        dialog.attr('aria-busy',String(value));
        dialog.closest('.ui-dialog').find('.ui-dialog-buttonpane button').prop('disabled',value);
        if(value)message('در حال ذخیره رویداد…');
    }
    function update(field) {
        var value=core().fromJalali(field.date.value,field.time.value);
        field.original.value=value||'';
        field.date.setAttribute('aria-invalid',String(!value));
        field.time.setAttribute('aria-invalid',String(!value));
        field.hint.textContent=value ? 'میلادی: '+value.slice(0,10) : 'تاریخ شمسی و ساعت معتبر وارد کنید.';
        return !!value;
    }
    function closePicker(field) {
        if(field.picker)field.picker.remove();field.picker=null;field.toggle.setAttribute('aria-expanded','false');
    }
    function picker(field) {
        if(field.picker){closePicker(field);return;}
        fields.forEach(closePicker);
        var current=core().toJalali(field.original.value||core().now());
        var y=current.jy,m=current.jm;
        var box=el('div','mt-event-picker');field.picker=box;
        box.setAttribute('role','group');box.setAttribute('aria-label','انتخاب تاریخ شمسی');
        field.host.append(box);field.toggle.setAttribute('aria-expanded','true');
        function draw(){
            box.replaceChildren();
            var nav=el('div','mt-picker-nav'),prev=btn('ماه قبل'),next=btn('ماه بعد'),title=el('strong','',window.MTJalali.JMONTHS[m-1]+' '+window.MTJalali.faNum(y));
            nav.append(prev,title,next);box.append(nav);
            var grid=el('div','mt-picker-grid');
            window.MTJalali.JDAYS.forEach(function(day){var d=el('span','',day.slice(0,1));d.title=day;grid.append(d);});
            var first=window.MTJalali.toGregorian(y,m,1),range=core().monthRange(y,m);
            for(var i=0;i<(first.getDay()+1)%7;i++)grid.append(el('span'));
            for(var day=1;day<=range.length;day++)(function(d){
                var b=btn(window.MTJalali.faNum(d));b.dataset.day=d;
                b.setAttribute('aria-label',window.MTJalali.faNum(d)+' '+window.MTJalali.JMONTHS[m-1]+' '+window.MTJalali.faNum(y));
                if(current.jy===y&&current.jm===m&&current.jd===d)b.setAttribute('aria-current','date');
                b.addEventListener('click',function(){field.date.value=y+'/'+String(m).padStart(2,'0')+'/'+String(d).padStart(2,'0');update(field);closePicker(field);field.date.focus();});
                b.addEventListener('keydown',function(e){
                    var delta={ArrowRight:-1,ArrowLeft:1,ArrowDown:7,ArrowUp:-7}[e.key];
                    if(delta){var target=grid.querySelector('[data-day="'+(d+delta)+'"]');if(target){e.preventDefault();target.focus();}}
                });grid.append(b);
            })(day);
            box.append(grid);
            function move(delta){m+=delta;if(m===0){m=12;y--;}if(m===13){m=1;y++;}draw();box.querySelector('button').focus();}
            prev.onclick=function(){move(-1);};next.onclick=function(){move(1);};
        }
        box.addEventListener('keydown',function(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closePicker(field);field.toggle.focus();}});
        draw();box.querySelector('[aria-current="date"], [data-day]').focus();
    }
    function mount() {
        var dialog=document.getElementById('calendar_eventdialog');if(!dialog)return;
        dialog.closest('.ui-dialog').classList.add('mt-calendar-dialog');
        if(fields.length)return;
        ['date','to'].forEach(function(name,index){
            var input=dialog.querySelector('input[name="'+name+'"]');if(!input)return;
            var plugin=$(input).data('datetimepicker');if(plugin&&typeof plugin.remove==='function')plugin.remove();
            var old=input.closest('.input-append')||input;old.hidden=true;old.style.display='none';
            var host=el('div','mt-event-date');
            var label=el('label','',index?'پایان (شمسی)':'شروع (شمسی)');
            var date=el('input');date.type='text';date.dir='ltr';date.id='mt-event-'+name;date.placeholder='۱۴۰۵/۰۱/۰۱';date.autocomplete='off';date.inputMode='numeric';label.htmlFor=date.id;
            var time=el('input');time.type='text';time.dir='ltr';time.id='mt-event-'+name+'-time';time.placeholder='09:30';time.inputMode='numeric';time.setAttribute('aria-label',index?'ساعت پایان، ۲۴ ساعته':'ساعت شروع، ۲۴ ساعته');
            var toggle=btn('انتخاب تاریخ');toggle.setAttribute('aria-expanded','false');
            var row=el('div','mt-event-date-row'),hint=el('small','mt-date-hint');hint.id=date.id+'-hint';date.setAttribute('aria-describedby',hint.id);
            row.append(date,time,toggle);host.append(label,row,hint);old.parentNode.append(host);
            var field={original:input,host:host,date:date,time:time,toggle:toggle,hint:hint,picker:null};fields.push(field);
            date.oninput=time.oninput=function(){update(field);};toggle.onclick=function(){picker(field);};
        });
        var zone=document.querySelector('[name="server_timezone"]');
        var note=el('p','mt-calendar-zone','ساعت رویدادها بر اساس منطقه زمانی سامانه'+(zone?': '+zone.value:''));dialog.prepend(note);
        $('#calendar_eventdialog').on('dialogclose.mtcalendar',function(){generation++;fields.forEach(closePicker);});
    }
    function sync() {
        mount();message('');fields.forEach(function(field){
            closePicker(field);var value=core().toJalali(field.original.value);
            field.date.value=value?value.date:'';field.time.value=value?value.time:'';update(field);
        });
    }
    function validate() {
        mount();var invalid=fields.filter(function(f){return !update(f);});
        if(invalid.length){message('تاریخ یا ساعت معتبر نیست. نمونه: ۱۴۰۵/۰۱/۰۱ و 09:30');invalid[0].date.focus();return false;}
        if(fields[0].original.value>=fields[1].original.value){message('پایان رویداد باید بعد از شروع آن باشد.');fields[1].date.focus();return false;}
        return true;
    }
    function color(value) {
        value=/^#[0-9a-f]{6}$/i.test(value||'')?value:'#245cc5';
        $('#colorSelector .colorpicker-box').css('backgroundColor',value);
    }
    function safeURL(url){return /^\/rest\.php\/calendar\/CalendarEvent(?:\/\d+)?$/.test(url);}
    function save(url,data){
        if(saving||!safeURL(url))return null;
        data.clear_notifications=$('#CheckBoxNoti').is(':checked')?'0':'1';
        busy(true);
        var result=$.Deferred();
        $.ajax({url:url,type:'POST',data:data,timeout:30000}).done(function(body,status,xhr){
            busy(false);
            if(xhr.status===(/\/\d+$/.test(url)?204:201))result.resolve(body);
            else result.reject({status:401});
        }).fail(function(xhr){busy(false);result.reject(xhr);});
        return result.promise().fail(error);
    }
    function open(url){
        if(!safeURL(url)||saving)return;
        var token=++generation;
        window.clearEventDialog();
        var dialog=$('#calendar_eventdialog');
        dialog.dialog({title:'ویرایش رویداد',buttons:[{text:'بستن',click:function(){dialog.dialog('close');}}]}).dialog('open');
        message('در حال دریافت رویداد…');
        $.ajax({url:url,dataType:'json',timeout:20000}).done(function(data){
            if(token!==generation)return;
            if(!data||!core().serialize(data.starttime)||!core().serialize(data.endtime)){error();return;}
            window.fillEventDialog(data);message('');
            dialog.dialog('option','buttons',[
                {text:'ذخیره تغییرات',click:function(){var d=window.saveEventDialog(url);if(d)d.done(function(){dialog.dialog('close');$('#calendar_main').fullCalendar('refetchEvents');});}},
                {text:'حذف رویداد',click:function(){
                    if(saving||!window.confirm('این رویداد حذف شود؟'))return;
                    busy(true);$.ajax({url:url,type:'DELETE',dataType:'json',timeout:30000}).done(function(data){busy(false);if(data&&typeof data.message==='string'){dialog.dialog('close');$('#calendar_main').fullCalendar('refetchEvents');}else error();}).fail(error).always(function(){busy(false);});
                }},
                {text:'انصراف',click:function(){dialog.dialog('close');}}
            ]);
        }).fail(function(r){if(token===generation)error(r);});
    }
    window.MTCalendarNative={sync:sync,validate:validate,color:color,save:save,open:open,error:error};
    $(function(){if(document.getElementById('calendar_eventdialog')){
        $('#calendar_eventdialog').dialog('option',{width:Math.min(680,window.innerWidth-24),height:'auto',maxHeight:window.innerHeight-40,draggable:false,resizable:false,beforeClose:function(){return !saving;}});
        $('#calendar_eventdialog').on('dialogopen.mtcalendar',sync);
        $(window).on('resize.mtcalendar',function(){$('#calendar_eventdialog').dialog('option','width',Math.min(680,window.innerWidth-24));});
    }});
})(window,document,window.jQuery);
