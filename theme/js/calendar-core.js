/* Calendar dates represent wall time in the configured PBX timezone.
 * ISO offsets from the legacy API are metadata, not a browser conversion. */
(function (window) {
    'use strict';
    var pad = function (n) { return String(n).padStart(2, '0'); };
    function digits(value) {
        return String(value || '').trim().replace(/[۰-۹٠-٩]/g, function (c) {
            var n = '۰۱۲۳۴۵۶۷۸۹'.indexOf(c);
            return n < 0 ? '٠١٢٣٤٥٦٧٨٩'.indexOf(c) : n;
        });
    }
    function parts(value) {
        if (value instanceof Date) {
            if (!Number.isFinite(value.getTime())) return null;
            return {y:value.getFullYear(), m:value.getMonth()+1, d:value.getDate(), h:value.getHours(), min:value.getMinutes(), s:value.getSeconds()};
        }
        var m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/.exec(digits(value));
        if (!m) return null;
        var p = {y:+m[1], m:+m[2], d:+m[3], h:+(m[4]||0), min:+(m[5]||0), s:+(m[6]||0)};
        var check = new Date(Date.UTC(p.y,p.m-1,p.d));
        if (p.y < 1800 || p.y > 2256 || check.getUTCFullYear()!==p.y || check.getUTCMonth()+1!==p.m || check.getUTCDate()!==p.d || p.h>23 || p.min>59 || p.s>59) return null;
        return p;
    }
    function key(value) {
        var p=parts(value); return p ? p.y+'-'+pad(p.m)+'-'+pad(p.d) : null;
    }
    function serialize(value) {
        var p=parts(value); return p ? key(value)+' '+pad(p.h)+':'+pad(p.min)+':'+pad(p.s) : null;
    }
    function toJalali(value) {
        var p=parts(value); if (!p) return null;
        var j=window.MTJalali.toJalali(new Date(p.y,p.m-1,p.d,12));
        return {date:j.jy+'/'+pad(j.jm)+'/'+pad(j.jd),time:pad(p.h)+':'+pad(p.min),jy:j.jy,jm:j.jm,jd:j.jd};
    }
    function fromJalali(date,time) {
        var j=/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(digits(date));
        var t=/^(\d{1,2}):(\d{2})$/.exec(digits(time));
        if (!j || !t || +j[1]<1179 || +j[1]>1634 || +j[2]<1 || +j[2]>12 || +j[3]<1 || +j[3]>31 || +t[1]>23 || +t[2]>59) return null;
        var g=window.MTJalali.toGregorian(+j[1],+j[2],+j[3]);
        var round=window.MTJalali.toJalali(g);
        if (round.jy!==+j[1] || round.jm!==+j[2] || round.jd!==+j[3]) return null;
        return key(g)+' '+pad(+t[1])+':'+pad(+t[2]);
    }
    function monthRange(jy,jm) {
        var mt=window.MTJalali;
        var first=mt.toGregorian(jy,jm,1);
        var next=mt.toGregorian(jm===12?jy+1:jy,jm===12?1:jm+1,1);
        var length=Math.round((Date.UTC(next.getFullYear(),next.getMonth(),next.getDate())-Date.UTC(first.getFullYear(),first.getMonth(),first.getDate()))/86400000);
        var lead=(first.getDay()+1)%7, count=Math.ceil((lead+length)/7)*7;
        return {start:key(new Date(first.getFullYear(),first.getMonth(),1*first.getDate()-lead,12)),end:key(new Date(first.getFullYear(),first.getMonth(),first.getDate()-lead+count,12)),length:length,count:count};
    }
    function nowText() {
        var meta=document.querySelector('[name="server_timezone"]');
        var zone=meta && meta.value;
        if (zone) {
            try {
                var map={};
                new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).forEach(function(p){map[p.type]=p.value;});
                return map.year+'-'+map.month+'-'+map.day+' '+map.hour+':'+map.minute+':'+map.second;
            } catch (error) { /* Old browsers retain a usable local clock. */ }
        }
        return serialize(new Date());
    }
    function now() { var p=parts(nowText());return new Date(p.y,p.m-1,p.d,12); }
    function addMinutes(value, minutes) {
        var p=parts(value);if(!p)return null;
        var d=new Date(Date.UTC(p.y,p.m-1,p.d,p.h,p.min+minutes,p.s));
        return d.getUTCFullYear()+'-'+pad(d.getUTCMonth()+1)+'-'+pad(d.getUTCDate())+' '+pad(d.getUTCHours())+':'+pad(d.getUTCMinutes());
    }
    window.MTCalendarCore={digits:digits,parts:parts,key:key,serialize:serialize,toJalali:toJalali,fromJalali:fromJalali,monthRange:monthRange,now:now,nowText:nowText,addMinutes:addMinutes};
})(window);
