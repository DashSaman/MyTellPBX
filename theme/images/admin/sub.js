/* MyTel subtitle layer for the STOCK IssabelPBX console (v1, 2026-10-05)
   Policy: ADDITIVE ONLY — stock English words, markup and behavior stay
   untouched. This file only:
     1) appends a tiny Persian subtitle (<div class="mt-sub">) under a
        form label cell / section header / page title when its exact text
        is mapped in LABELS;
     2) replaces the hidden "?" bubble text with a mapped concise
        Persian line (stock English kept in data-mt-en);
     3) adds a native title tooltip on mapped action buttons.
   Unmapped elements are never touched; every pass is idempotent. */

(function () {
    'use strict';

    /* ---- form labels / section titles (exact text after cleanup) ---- */
    var LABELS = {
        /* generic, shared by many modules */
        "General Settings": "تنظیمات عمومی",
        "Additional Settings": "تنظیمات بیشتر",
        "Options": "گزینه‌ها",
        "Description": "توضیحات",
        "Language": "زبان",
        "Call Recording": "ضبط تماس",
        "Music On Hold": "موسیقی انتظار",
        "Music on Hold": "موسیقی انتظار",
        "Music on Hold Class": "کلاس موسیقی انتظار",
        "Music On Hold Class": "کلاس موسیقی انتظار",
        "Alert Info": "اطلاعات زنگ",
        "CID name prefix": "پیشوند نام تماس‌گیرنده",
        "Time Group": "گروه زمانی",
        "Set Destination": "تعیین مقصد",
        "Clear Destination & Submit": "پاک‌کردن مقصد و ذخیره",
        "CID Lookup Source": "منبع شماره‌یابی",
        "Source": "منبع",
        "Privacy": "حریم خصوصی",
        "Privacy Manager": "پرسش شناسهٔ تماس‌گیرنده",
        "Max attempts": "حداکثر تلاش",
        "Min Length": "حداقل طول",
        "Destination after playback": "مقصد پس از پخش",
        /* inbound routes (did) */
        "DID Number": "شمارهٔ ورودی",
        "CallerID Number": "شمارهٔ تماس‌گیرنده",
        "CID Priority Route": "اولویت مسیر با شناسه",
        "Signal RINGING": "ارسال زنگ",
        "Pause Before Answer": "مکث پیش از پاسخ",
        /* outbound routes (routing) */
        "Route Name": "نام مسیر",
        "Route CID": "شناسهٔ مسیر",
        "Route Password": "گذرواژهٔ مسیر",
        "Route Type": "نوع مسیر",
        "Route Position": "جایگاه مسیر",
        "PIN Set": "مجموعهٔ پین",
        "Trunk Sequence for Matched Routes": "ترتیب ترانک‌های مسیر",
        /* sip settings */
        "NAT Settings": "تنظیمات عبور از NAT",
        "NAT": "حالت NAT",
        "IP Configuration": "پیکربندی IP",
        "External IP": "آی‌پی بیرونی",
        "Dynamic Host": "میزبان پویا",
        "Local Networks": "شبکه‌های محلی",
        "Audio Codecs": "کدک‌های صوتی",
        "Codecs": "کدک‌ها",
        "Non-Standard g726": "حالت ویژهٔ G726",
        "T38 Pass-Through": "عبور فکس T38",
        "Video Codecs": "کدک‌های تصویری",
        "Video Support": "پشتیبانی تصویر",
        "Max Bit Rate": "حداکثر نرخ بیت",
        "MEDIA & RTP Settings": "رسانه و RTP",
        "Reinvite Behavior": "رفتار بازمسیری رسانه",
        "RTP Timers": "زمان‌سنج‌های RTP",
        "RTP Port Ranges": "بازهٔ پورت‌های RTP",
        "Notification & MWI": "اعلان و نشانگر پیام",
        "MWI Polling Freq": "تناوب بررسی پیام",
        "Notify Ringing": "اعلان زنگ‌خوردن",
        "Notify Hold": "اعلان انتظار",
        "Registration Settings": "تنظیمات ثبت‌نام",
        "Registrations": "ثبت‌نام‌ها",
        "Registration Times": "زمان‌های ثبت‌نام",
        "Jitter Buffer Settings": "تنظیمات بافر نوسان",
        "Jitter Buffer": "بافر نوسان",
        "Force Jitter Buffer": "بافر اجباری",
        "Implementation": "پیاده‌سازی",
        "Jitter Buffer Logging": "ثبت گزارش بافر",
        "Jitter Buffer Size": "اندازهٔ بافر",
        "Advanced General Settings": "تنظیمات پیشرفتهٔ عمومی",
        "Default Context": "کانتکست پیش‌فرض",
        "Bind Address": "نشانی اتصال",
        "Bind Port": "پورت اتصال",
        "TLS Bind Port": "پورت رمزنگاری TLS",
        "Allow SIP Guests": "پذیرش مهمان سیپ",
        "Allow Anonymous Inbound SIP Calls": "تماس‌های ورودی ناشناس",
        "SRV Lookup": "جست‌وجوی SRV",
        "Call Events": "رویدادهای تماس",
        "Enable Websocket": "فعال‌سازی وب‌سوکت",
        "Other SIP Settings": "سایر تنظیمات سیپ",
        /* queues */
        "General Queue Options": "تنظیمات عمومی صف",
        "Queue Number": "شمارهٔ صف",
        "Queue Name": "نام صف",
        "Queue Password": "گذرواژهٔ صف",
        "Generate Device Hints": "ساخت هینت دستگاه",
        "Call Confirm": "تأیید تماس",
        "Call Confirm Announce": "اعلانِ تأیید تماس",
        "CID Name Prefix": "پیشوند نام تماس‌گیرنده",
        "Wait Time Prefix": "پیشوند زمان انتظار",
        "Restrict Dynamic Agents": "محدودکردن اعضای پویا",
        "Agent Restrictions": "محدودیت اپراتور",
        "Ring Strategy": "راهبرد زنگ",
        "Autofill": "پرکردن خودکار",
        "Skip Busy Agents": "ردکردن اپراتور مشغول",
        "Queue Weight": "وزن صف",
        "Join Announcement": "اعلان ورود به صف",
        "Recording Mode": "حالت ضبط",
        "Caller Volume Adjustment": "تنظیم صدای تماس‌گیرنده",
        "Agent Volume Adjustment": "تنظیم صدای اپراتور",
        "Mark calls answered elsewhere": "پاسخ در جای دیگر",
        "Queue Members": "اعضای صف",
        "Static Agents": "اعضای ثابت",
        "Extension Quick Pick": "انتخاب سریع داخلی",
        "Dynamic Members": "اعضای پویا",
        "Timing & Agent Options": "زمان‌بندی و اپراتور",
        "Max Wait Time": "حداکثر زمان انتظار",
        "Max Wait Time Mode": "حالت حداکثر انتظار",
        "Agent Timeout": "مهلت پاسخ اپراتور",
        "Agent Timeout Restart": "شروع دوبارهٔ مهلت",
        "Retry": "فاصلهٔ تلاش دوباره",
        "Wrap-Up-Time": "زمان استراحت اپراتور",
        "Member Delay": "تأخیر اتصال عضو",
        "Agent Announcement": "اعلان به اپراتور",
        "Report Hold Time": "اعلام زمان انتظار",
        "Auto Pause": "توقف خودکار اپراتور",
        "Auto Pause on Busy": "توقف هنگام اشغال",
        "Auto Pause on Unavailable": "توقف هنگام عدم دسترسی",
        "Auto Pause Delay": "تأخیر توقف خودکار",
        "Capacity Options": "ظرفیت صف",
        "Max Callers": "حداکثر تماس‌گیرنده",
        "Join Empty": "ورود به صف خالی",
        "Leave Empty": "ترک صف خالی",
        "Penalty Members Limit": "سقف جریمهٔ اعضا",
        "Caller Position Announcements": "اعلام نوبت تماس‌گیرنده",
        "Frequency": "تناوب اعلام",
        "Announce Position": "اعلام شمارهٔ نوبت",
        "Announce Hold Time": "اعلام زمان انتظار",
        "Periodic Announcements": "اعلان‌های دوره‌ای",
        "IVR Break Out Menu": "خروج به منوی صوتی",
        "Repeat Frequency": "تناوب تکرار",
        "Events, Stats and Advanced": "رویدادها، آمار و پیشرفته",
        "Event When Called": "رویداد هنگام تماس",
        "Member Status Event": "رویداد وضعیت عضو",
        "Service Level": "سطح سرویس",
        "Agent Regex Filter": "الگوی فیلتر اپراتور",
        "Fail Over Destination": "مقصد پشتیبان",
        "Queue Continue Destination": "مقصد ادامهٔ صف",
        "Reset Queue Stats": "بازنشانی آمار صف",
        /* ivr */
        "Add IVR": "افزودن منوی صوتی",
        "IVR General Options": "تنظیمات عمومی منو",
        "IVR Name": "نام منو",
        "IVR Description": "توضیح منو",
        "IVR Options (DTMF)": "گزینه‌های کلیدی منو",
        "Announcement": "پیام اعلان",
        "Direct Dial": "شماره‌گیری مستقیم",
        "Timeout": "مهلت پاسخ",
        "Invalid Retries": "تلاش‌های ورودی نادرست",
        "Invalid Retry Recording": "پیام ورودی نادرست",
        "Append Announcement on Invalid": "افزودن اعلان هنگام خطا",
        "Return on Invalid": "بازگشت هنگام خطا",
        "Invalid Destination": "مقصد ورودی نادرست",
        "Timeout Retries": "تلاش‌های پس از مهلت",
        "Timeout Retry Recording": "پیام تکرار مهلت",
        "Append Announcement on Timeout": "افزودن اعلان هنگام مهلت",
        "Return on Timeout": "بازگشت هنگام مهلت",
        "Timeout Recording": "پیام پایان مهلت",
        "Timeout Destination": "مقصد پایان مهلت",
        "Return to IVR after VM": "بازگشت به منو پس از پیام",
        "IVR Entries": "ورودی‌های منو",
        "Invalid Recording": "ضبط ورودی نادرست",
        /* time conditions */
        "Time Condition name": "نام شرط زمانی",
        "Destination if time matches": "مقصد در صورت تطبیق زمان",
        /* announcements */
        "Recording": "فایل صوتی",
        "Repeat": "تکرار پخش",
        "Allow Skip": "اجازهٔ ردکردن پیام",
        "Return to IVR": "بازگشت به منو",
        "Don't Answer Channel": "پاسخ‌ندادن کانال",
        "Text to Speech": "تبدیل متن به گفتار",
        "Text": "متن پیام",
        /* conferences */
        "Conference Number": "شمارهٔ کنفرانس",
        "Conference Name": "نام کنفرانس",
        "User PIN": "پین ورود کاربر",
        "Admin PIN": "پین مدیر",
        "Conference Options": "گزینه‌های کنفرانس",
        "Join Message": "پیام ورود",
        "Leader Wait": "انتظار برای مدیر",
        "Talker Optimization": "بهینه‌سازی گوینده",
        "Talker Detection": "تشخیص گوینده",
        "Quiet Mode": "حالت بی‌صدا",
        "User Count": "اعلام شمار شرکت‌کنندگان",
        "User join/leave": "اعلام ورود و خروج",
        "Allow Menu": "منوی شرکت‌کننده",
        "Record Conference": "ضبط کنفرانس",
        "Maximum Participants": "حداکثر شرکت‌کننده",
        "Mute on Join": "بی‌صدا هنگام ورود",
        /* extensions */
        "Add an Extension": "افزودن داخلی",
        "Device": "نوع دستگاه",
        /* record-nav */
        "Add": "افزودن"
    };

    /* ---- "?" bubble texts: keyed by normalized English prefix ---- */
    var HELP = {
        /* NAT / connectivity */
        "asterisk nat setting: yes = always": "تنظیم NAT در آستریس: بله = همیشه در نظر گرفتن NAT؛ خیر = فقط طبق RFC3581؛ هرگز = بدون NAT؛ route = فرض NAT بدون rport.",
        "indicate whether the box has": "مشخص می‌کند سرور IP عمومی دارد یا به تنظیمات NAT نیاز دارد.",
        "external static ip or fqdn": "آی‌پی ثابت بیرونی یا نام دامنه، آن‌گونه که از سمت اینترنت دیده می‌شود.",
        "external fqdn as seen on": "نام دامنهٔ بیرونیِ به‌روزشونده؛ مانند mydomain.dyndns.com.",
        "asterisk: externrefresh. how often": "فاصلهٔ به‌روزرسانی دامنهٔ بیرونی، بر حسب ثانیه.",
        "local network settings (asterisk": "شبکه‌های محلی به شکل ip/mask؛ برای هر زیرشبکه یک ردیف اضافه کنید.",
        /* codecs */
        "check the desired codecs, all": "کدک‌های موردنظر را انتخاب کنید؛ بقیه غیرفعال می‌شوند مگر آنکه جداگانه فعال شوند.",
        "asterisk: g726nonstandard. if the": "برای همتاهای قدیمی، بسته‌بندی AAL2 برای صدای G726-32 به‌کار می‌رود.",
        "asterisk: t38pt_udptl. enables t38": "عبور فکس T.38 را در کانال‌های پشتیبان فعال می‌کند.",
        "check to enable and then": "فعال کنید و کدک‌های مجاز را برگزینید؛ ترتیب انتخاب، اولویت کدک را می‌سازد.",
        "maximum bitrate for video calls": "حداکثر نرخ بیت تماس تصویری، کیلوبیت بر ثانیه.",
        /* reinvite / RTP */
        "asterisk: canreinvite. yes: standard": "بازمسیری رسانه: بله = استاندارد؛ خیر = هرگز؛ nonat = فقط بیرون از NAT؛ update = با UPDATE.",
        "asterisk: rtptimeout. terminate call": "اگر به‌اندازهٔ این ثانیه‌ها بستهٔ صوتی نیاید، تماس قطع می‌شود.",
        "asterisk: rtpstart. the starting": "بازهٔ پورت‌های RTP: پورت شروع و پایان.",
        /* MWI */
        "frequency in seconds to check": "فاصلهٔ بررسی نشانگر پیام جدید و اطلاع به گوشی‌ها، بر حسب ثانیه.",
        "control whether subscriptions already": "ارسال وضعیت «زنگ‌خوردن» به چراغ‌های اشغال (BLF) وقتی خط در حال استفاده است.",
        "control whether subscriptions inuse": "ارسال وضعیت «انتظار» به چراغ‌های اشغال (BLF) هنگام hold.",
        /* registration */
        "asterisk: registertimeout. retry": "هر این‌قدر ثانیه ثبت‌نام دوباره تلاش می‌شود؛ صفر یعنی بی‌پایان (توصیه می‌شود).",
        "asterisk: minexpiry. minimum length": "کمینه، بیشینه و پیش‌فرضِ مدت ثبت‌نام‌ها بر حسب ثانیه.",
        /* jitter buffer */
        "asterisk: jbenable. enables the use": "بافر جبران نوسان تأخیر را در سمت دریافت فعال می‌کند.",
        "asterisk: jbforce. forces the use": "استفاده از بافر نوسان را اجباری می‌کند؛ معمولاً توصیه نمی‌شود.",
        "asterisk: jbimpl. jitterbuffer implementation": "نوع بافر: ثابت یا تطبیقی.",
        "asterisk: jblog. enables jitter": "ثبت جزئیات بافر در گزارش‌ها.",
        "asterisk: jbmaxsize. max length": "بیشینهٔ اندازهٔ بافر بر حسب میلی‌ثانیه و آستانهٔ هم‌زمان‌سازی دوباره.",
        /* general sip */
        "default language for a channel": "زبان پیش‌فرض کانال.",
        "asterisk: context. default context": "کانتکست پیش‌فرض تماس‌های ورودی بدون مشخصات.",
        "asterisk: bindaddr. the ip address": "آی‌پی شنود آستریس؛ 0.0.0.0 یعنی همهٔ کارت‌های شبکه.",
        "asterisk: bindport. local incoming": "پورت UDP شنود سیگنالینگ سیپ.",
        "asterisk: tls bindport. local": "پورت TLS برای سیپ رمزنگاری‌شده.",
        "asterisk: allowguest. when set": "پذیرش مهمان‌های سیپ و فرستادنشان به کانتکست پیش‌فرض؛ برای امنیت خاموش بماند.",
        "allowing inbound anonymous sip": "پذیرش هر تماس سیپ ناشناس؛ ریسک هرزتماس دارد؛ با آگاهی فعال کنید.",
        "enable asterisk srvlookup": "جست‌وجوی رکورد SRV مقصدها فعال می‌شود.",
        "generate manager events when": "هنگام رخدادهایی مثل hold، رویداد مدیریتی تولید می‌کند.",
        "enable websocket connection handling": "پشتیبانی وب‌سوکت از طریق chan_sip؛ برای WebRTC لازم است.",
        "you may set any other sip": "هر تنظیم سیپ دیگرِ مجاز را می‌توانید اینجا اضافه کنید.",
        /* ---- inbound routes (did) ---- */
        "provide a meaningful description": "توضیح روشنی دربارهٔ این مسیر ورودی بنویسید.",
        "define the expected did number": "شمارهٔ ورودی مورد انتظار؛ خالی یعنی تطبیق با همهٔ شماره‌ها.",
        "define the callerid number": "شمارهٔ تماس‌گیرنده برای تطبیق؛ خالی یعنی همه.",
        "this effects cid only routes": "فقط مسیرهای مبتنی بر شناسه: تماسِ همین شناسه حتی بدون شمارهٔ ورودی به این مسیر می‌رود.",
        "alert_info can be used": "برای زنگ متمایز روی گوشی‌های سیپ.",
        "you can optionally prefix the callerid name. ie": "پیشوند اختیاری نام تماس‌گیرنده؛ مثلاً «فروش:» پیش از نام.",
        "set the moh class": "کلاس موسیقی انتظارِ تماس‌های این مسیر.",
        "some devices or providers require": "برخی دستگاه‌ها پیش از پاسخ به زنگ نیاز دارند؛ در صورت مشکل فعال کنید.",
        "an optional delay to wait": "مکث اختیاری پیش از پردازش مسیر، بر حسب ثانیه.",
        "if no callerid has been": "اگر شناسه‌ای نیامده باشد، از تماس‌گیرنده شماره‌اش پرسیده می‌شود.",
        "number of attempts the caller": "تعداد تلاش مجاز برای واردکردن شناسهٔ معتبر.",
        "minimum amount of digits callerid": "حداقل ارقام برای معتبرشمردن شناسه.",
        "sources can be added": "منابع در بخش «منابع شماره‌یابی» ساخته می‌شوند.",
        "allows you to set": "زبان این مسیر ورودی.",
        "controls or overrides the call": "رفتار ضبط تماس‌های این مسیر را کنترل یا بازنویسی می‌کند.",
        /* ---- outbound routes (routing) ---- */
        "name of this route. should": "نامی توصیفی برای این مسیر؛ چه تماس‌هایی با آن تطبیق می‌یابند.",
        "optional route cid to be": "شناسهٔ تماس‌گیرندهٔ این مسیر؛ اگر تنظیم شود جای همه را می‌گیرد.",
        "if checked the extension's outbound": "شناسهٔ خروجی خودِ داخلی نادیده گرفته می‌شود و از همین شناسه استفاده می‌شود.",
        "optional: a route can prompt": "پیش از برقراری تماس از کاربر گذرواژه پرسیده می‌شود.",
        "optional: selecting emergency will": "با «اضطراری»، شناسهٔ اضطراری دستگاه (در صورت وجود) اعمال می‌شود.",
        "you can choose which music": "کلاس موسیقی انتظارِ این مسیر.",
        "if this route should only": "اگر مسیر فقط در زمان‌های مشخص در دسترس باشد، گروه زمانی را انتخاب کنید.",
        "where to insert this route": "جایگاه این مسیر نسبت به مسیرهای دیگر.",
        "optional: select a pin set": "مجموعهٔ پینِ مسیر؛ همراه گذرواژهٔ مسیر استفاده نشود.",
        "a dial pattern is a": "الگوی شماره‌گیری: چه ارقامی این مسیر را برمی‌گزینند.",
        "these options provide a quick": "دکمه‌های سریع افزودن قواعد شماره‌گیری.",
        "the trunk sequence controls": "ترتیب تلاش برای ترانک‌ها وقتی الگو تطبیق یافت.",
        "if all the trunks fail": "اگر همهٔ ترانک‌ها شلوغ شکست خوردند، مقصد جایگزین مانند اعلان.",
        /* ---- queues ---- */
        "use this number to dial": "با این شماره وارد صف می‌شوید یا تماس را به صف منتقل می‌کنید.",
        "give this queue a brief": "نامی کوتاه برای شناسایی صف.",
        "you can require agents": "اپراتورها پیش از ورود به صف این گذرواژه را وارد می‌کنند.",
        "if checked, individual hints": "برای هر دستگاهِ عضو، هینت و دیال‌پلن اختصاصی ساخته می‌شود.",
        "if checked, any queue member": "اعضای شمارهٔ بیرونی بدون تأییدِ مستقیم تماس می‌زنند؛ برای جلوگیری از تماس ناخواسته فعال کنید.",
        "announcement played to the queue": "پیامی که پیش از وصل‌شدن به اپراتور پخش و تأیید می‌طلبد.",
        "you can optionally prefix the callerid name of callers": "پیشوند اختیاری نام تماس‌گیرندهٔ صف.",
        "when set to yes, the cid": "زمان انتظار در صف به نام تماس‌گیرنده افزوده می‌شود.",
        "restrict dynamic queue member": "ورود اعضای پویا فقط به فهرست «اعضای پویا» محدود می‌شود.",
        "when set to 'call as dialed'": "با «تماس مثل شماره‌گیری معمولی»، تماس همان‌گونه که شماره گرفته شده برقرار می‌شود؛ در غیر این‌صورت فقط داخلی زنگ می‌خورد.",
        "ringall: ring all available": "راهبرد زنگ: همه‌باهم، کم‌ترین فعالیت، کم‌ترین تماس، تصادفی، گردشی و…",
        "starting with asterisk 1.4": "چند اپراتور آزاد همزمان زنگ می‌خورند تا اولین پاسخ دهد.",
        "when set to 'yes' agents who": "اپراتورهای مشغول رد می‌شوند.",
        "gives queues a 'weight'": "وزن صف؛ صف پراولویت سریع‌تر پاسخ می‌گیرد.",
        "music (moh) played to the caller": "موسیقی انتظار تماس‌گیرنده تا پاسخ اپراتور.",
        "announcement played to callers prior": "پیام پخش‌شده به تماس‌گیرنده پیش از ورود به صف.",
        "the maximum number of people": "حداکثر تماس‌گیرندگانی که همزمان می‌توانند در صف بمانند.",
        "if checked, callers will not": "تماس‌گیرنده به صفِ بدون اپراتور راه نمی‌یابد.",
        "if checked, callers already in": "اگر همهٔ اپراتورها خارج شوند، تماس‌های صف بلافاصله خارج می‌شوند.",
        "the number of seconds between": "فاصلهٔ زمانی میان اعلام‌های دوره‌ای به تماس‌گیرنده.",
        "if enabled, the caller's position": "شمارهٔ نوبت تماس‌گیرنده به او اعلام می‌شود.",
        "if enabled, the estimated hold": "زمان تقریبی انتظار به تماس‌گیرنده اعلام می‌شود.",
        "if checked, agents will be automatically": "اپراتورِ بی‌پاسخ به‌طور خودکار متوقف می‌شود.",
        "number of seconds a member's": "مدت انتظار پیش از توقف خودکار اپراتور.",
        "the number of seconds to wait": "مدت انتظار پیش از زنگ‌خوردن اپراتور بعدی.",
        "how many seconds to wait before": "مکث پس از پایان تماس اپراتور تا تماس بعدی.",
        "when set to yes, the queue": "زمان انتظار به اپراتور اعلام می‌شود.",
        "if checked, the queue member": "هنگام زنگ‌خوردن عضو، رویداد مدیریتی ارسال می‌شود.",
        "if checked, queue member status": "تغییر وضعیت اعضا به‌صورت رویداد اعلام می‌شود.",
        "the service level is the": "درصد تماس‌هایی که در این ثانیه‌های اول پاسخ می‌گیرند (برای گزارش).",
        "only dynamic agents matching this": "فقط اپراتورهای منطبق با این الگو وارد صف می‌شوند.",
        "destination to send the call": "مقصد تماس وقتی صف پاسخ ندهد.",
        "where to send the caller if": "مقصد تماس‌گیرنده وقتی صف پاسخ ندهد.",
        /* ---- ivr ---- */
        "the name of this ivr": "نام این منوی صوتی.",
        "the description of this ivr": "توضیح این منوی صوتی.",
        "announcement played prior to the": "پیامی که پیش از شروع منو پخش می‌شود.",
        "enabling direct dial will allow": "اجازهٔ شماره‌گیری مستقیم داخلی‌ها حین پخش منو.",
        "the amount of time to wait": "مهلت دریافت رقم از تماس‌گیرنده، بر حسب ثانیه.",
        "number of times to retry": "تعداد تلاش پس از ورودی نادرست.",
        "recording to be played when": "پیام پخش‌شده هنگام ورود نادرست.",
        "where to send the caller after": "مقصد تماس‌گیرنده پس از این مرحله.",
        "recording to be played on": "پیام پخش‌شده پس از پایان مهلت.",
        /* ---- announcements ---- */
        "the announcement played when callers": "پیامی که هنگام ورود به این بخش پخش می‌شود.",
        "number of times to repeat": "تعداد تکرار پیام.",
        "allow the caller to press": "اجازهٔ ردکردن پیام با کلید.",
        /* ---- conferences ---- */
        "the conference number": "شماره‌ای که برای ورود به کنفرانس شماره‌گیری می‌شود.",
        "the conference name": "نام نمایشی کنفرانس.",
        "pin required to access this": "پین لازم برای ورود به کنفرانس.",
        "message played to callers when": "پیام خوش‌آمد پیش از ورود به کنفرانس.",
        "wait until the conference leader": "انتظار برای رسیدن مدیر کنفرانس پیش از شروع.",
        /* ---- trunks / generic ---- */
        "context for the trunk": "کانتکست ترانک در دیال‌پلن.",
        "the outbound caller id number": "شناسهٔ تماس‌گیرندهٔ تماس‌های خروجی این ترانک.",
        "maximum number of simultaneous": "حداکثر تماس همزمان.",
        "number of seconds to ring": "مدت زنگ‌خوردن، بر حسب ثانیه.",
        "allow listening to recorded": "اجازهٔ شنیدن ضبط‌ها.",
        /* generic PBX terms reused on other pages */
        "asterisk: language. default language": "زبان پیش‌فرض کانال."
    };

    /* ---- action buttons: Persian native tooltip only (no layout change) ---- */
    var ACTIONS = {
        "Submit": "ذخیره",
        "Submit Changes": "ذخیرهٔ تغییرات",
        "Save": "ذخیره",
        "Delete": "حذف",
        "Cancel": "انصراف",
        "Reset": "بازنشانی",
        "Edit": "ویرایش",
        "Back": "بازگشت",
        "Search": "جستجو",
        "Refresh": "بازخوانی",
        "Install": "نصب",
        "Download": "دریافت",
        "Upload": "بارگذاری",
        "Close": "بستن",
        "Apply Changes": "اعمال تغییرات",
        "Add": "افزودن"
    };

    var HELP_KEYS = Object.keys(HELP);

    function clean(s) {
        return String(s || "").replace(/\s+/g, " ").replace(/\s*[?:]\s*$/, "").trim();
    }

    function normHelp(s) {
        return String(s || "").replace(/[\u2066-\u2069]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
    }

    /* append (once) a Persian subtitle element under a stock element */
    function addSub(el, fa) {
        if (!el || el.querySelector(":scope > .mt-sub")) return;
        var d = el.ownerDocument.createElement("div");
        d.className = "mt-sub";
        d.setAttribute("dir", "rtl");
        d.textContent = fa;
        el.appendChild(d);
    }

    /* label cells: form td:first-child holds the label (and maybe "?") */
    function passLabels() {
        var tds = document.querySelectorAll("form td:first-child, .content form td:first-child");
        for (var i = 0; i < tds.length; i++) {
            var td = tds[i];
            if (td.querySelector(":scope > .mt-sub")) continue;
            var clone = td.cloneNode(true);
            var ih = clone.querySelectorAll(".infohelp, input, select, button");
            for (var j = 0; j < ih.length; j++) { ih[j].remove(); }
            var t = clean(clone.textContent);
            if (!t) continue;
            var fa = LABELS[t];
            if (fa) addSub(td, fa);
        }
        /* page title band */
        var h2 = document.querySelector("h2#title");
        if (h2) {
            var t2 = clean(h2.textContent);
            if (LABELS[t2]) addSub(h2, LABELS[t2]);
        }
    }

    /* record nav: exact mapped texts only (no generic "Add X" pattern —
       user records like "Add Sales" must never get a false subtitle) */
    function passRnav() {
        var as = document.querySelectorAll("nav.rnav a");
        for (var i = 0; i < as.length; i++) {
            var a = as[i];
            if (a.querySelector(":scope > .mt-sub")) continue;
            var t = clean(a.textContent);
            if (!t || t.length > 34) continue;
            var fa = LABELS[t];
            if (fa) addSub(a, fa);
        }
    }

    /* "?" bubbles: replace text with mapped Persian, keep stock in data.
       Unmatched bubbles stay English and unmarked so later passes retry. */
    function passHelps() {
        var sps = document.querySelectorAll("span.infohelp > span");
        for (var i = 0; i < sps.length; i++) {
            var sp = sps[i];
            if (sp.dataset.mtHelp === "1") continue;
            var n = normHelp(sp.textContent);
            if (!n) continue;
            if (!/[a-z]/.test(n)) { sp.dataset.mtHelp = "1"; continue; }
            var hit = null, ambiguous = false;
            for (var k = 0; k < HELP_KEYS.length; k++) {
                if (n.indexOf(HELP_KEYS[k]) === 0) {
                    if (hit) { ambiguous = true; break; }
                    hit = HELP_KEYS[k];
                }
            }
            if (hit && !ambiguous) {
                if (!sp.dataset.mtEn) sp.dataset.mtEn = sp.textContent;
                sp.setAttribute("dir", "rtl");
                sp.textContent = HELP[hit];
                sp.dataset.mtHelp = "1";
            }
        }
    }

    /* action buttons: tooltip only */
    function passButtons() {
        var els = document.querySelectorAll("form input[type=submit], form button");
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            if (el.dataset.mtBtn === "1") continue;
            var t = clean(el.value || el.textContent);
            if (ACTIONS[t] && !el.title) el.title = ACTIONS[t];
            el.dataset.mtBtn = "1";
        }
    }

    function pass() {
        try { passLabels(); } catch (e) {}
        try { passRnav(); } catch (e) {}
        try { passHelps(); } catch (e) {}
        try { passButtons(); } catch (e) {}
    }

    function boot() {
        pass();
        setTimeout(pass, 400);
        setTimeout(pass, 1500);
        /* late console JS rebuilds rows (chosen picks, dial patterns):
           watch for new nodes; guarded passes make no mutations once
           settled, so the observer quiets down by itself */
        var t = null;
        try {
            var mo = new MutationObserver(function () {
                clearTimeout(t);
                t = setTimeout(pass, 200);
            });
            mo.observe(document.body, { childList: true, subtree: true });
        } catch (e) { /* very old engines: timed passes already ran */ }
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
