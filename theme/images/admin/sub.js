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
        "General Settings": "تنظیمات عمومی",
        "Additional Settings": "تنظیمات تکمیلی",
        "Options": "گزینه‌ها",
        "Description": "توضیحات",
        "Language": "زبان پیام‌ها",
        "Call Recording": "ضبط تماس",
        "Music On Hold": "موسیقی انتظار",
        "Music on Hold": "موسیقی انتظار",
        "Music on Hold Class": "دستهٔ انتظار",
        "Music On Hold Class": "دستهٔ انتظار",
        "Alert Info": "نوع زنگ",
        "CID name prefix": "پیشوند نام",
        "Time Group": "بازه‌های زمانی",
        "Set Destination": "مقصد تماس",
        "Clear Destination & Submit": "پاک‌کردن مقصد",
        "CID Lookup Source": "شناسایی تماس‌گیرنده",
        "Source": "منبع اطلاعات",
        "Privacy": "حریم خصوصی",
        "Privacy Manager": "دریافت شماره",
        "Max attempts": "سقف تلاش",
        "Min Length": "حداقل رقم",
        "Destination after playback": "مقصد بعدی",
        "DID Number": "شمارهٔ ورودی",
        "CallerID Number": "شمارهٔ تماس‌گیرنده",
        "CID Priority Route": "اولویت تماس‌گیرنده",
        "Signal RINGING": "اعلام زنگ",
        "Pause Before Answer": "تأخیر پاسخ",
        "Route Name": "نام مسیر",
        "Route CID": "شمارهٔ خروجی",
        "Route Password": "رمز مسیر",
        "Route Type": "نوع مسیر",
        "Route Position": "اولویت مسیر",
        "PIN Set": "مجموعهٔ رمزها",
        "Trunk Sequence for Matched Routes": "ترتیب ترانک‌ها",
        "NAT Settings": "ارتباط بیرونی",
        "NAT": "ترجمهٔ نشانی",
        "IP Configuration": "وضعیت نشانی",
        "External IP": "نشانی بیرونی",
        "Dynamic Host": "دامنهٔ متغیر",
        "Local Networks": "شبکه‌های داخلی",
        "Audio Codecs": "قالب‌های صدا",
        "Codecs": "قالب‌های رسانه",
        "Non-Standard g726": "سازگاری صدا",
        "T38 Pass-Through": "عبور نمابر",
        "Video Codecs": "قالب‌های تصویر",
        "Video Support": "تماس تصویری",
        "Max Bit Rate": "سقف انتقال",
        "MEDIA & RTP Settings": "انتقال رسانه",
        "Reinvite Behavior": "مسیر رسانه",
        "RTP Timers": "مهلت رسانه",
        "RTP Port Ranges": "درگاه‌های رسانه",
        "Notification & MWI": "اعلان وضعیت",
        "MWI Polling Freq": "بررسی پیام‌ها",
        "Notify Ringing": "اعلان زنگ",
        "Notify Hold": "اعلان انتظار",
        "Registration Settings": "ثبت ارتباط",
        "Registrations": "ارتباط‌های ثبت‌شده",
        "Registration Times": "زمان‌بندی ثبت",
        "Jitter Buffer Settings": "هموارسازی صدا",
        "Jitter Buffer": "هموارسازی صدا",
        "Force Jitter Buffer": "هموارسازی اجباری",
        "Implementation": "روش هموارسازی",
        "Jitter Buffer Logging": "گزارش هموارسازی",
        "Jitter Buffer Size": "ظرفیت هموارسازی",
        "Advanced General Settings": "تنظیمات پیشرفته",
        "Default Context": "مسیر پیش‌فرض",
        "Bind Address": "نشانی دریافت",
        "Bind Port": "درگاه دریافت",
        "TLS Bind Port": "درگاه امن",
        "Allow SIP Guests": "پذیرش مهمان",
        "Allow Anonymous Inbound SIP Calls": "پذیرش ناشناس",
        "SRV Lookup": "یافتن سرویس",
        "Call Events": "رویدادهای تماس",
        "Enable Websocket": "اتصال مرورگر",
        "Other SIP Settings": "تنظیمات تکمیلی",
        "General Queue Options": "تنظیمات صف",
        "Queue Number": "شمارهٔ صف",
        "Queue Name": "نام صف",
        "Queue Password": "رمز عضویت",
        "Generate Device Hints": "نمایش عضویت",
        "Call Confirm": "تأیید پذیرش",
        "Call Confirm Announce": "پیام تأیید",
        "CID Name Prefix": "پیشوند نام",
        "Wait Time Prefix": "نمایش انتظار",
        "Restrict Dynamic Agents": "محدودیت عضویت",
        "Agent Restrictions": "محدودیت اپراتورها",
        "Ring Strategy": "توزیع تماس",
        "Autofill": "توزیع هم‌زمان",
        "Skip Busy Agents": "ردکردن مشغول‌ها",
        "Queue Weight": "اولویت صف",
        "Join Announcement": "پیام ورود",
        "Recording Mode": "شیوهٔ ضبط",
        "Caller Volume Adjustment": "صدای تماس‌گیرنده",
        "Agent Volume Adjustment": "صدای اپراتور",
        "Mark calls answered elsewhere": "پاسخ جایگزین",
        "Queue Members": "اعضای صف",
        "Static Agents": "اپراتورهای ثابت",
        "Extension Quick Pick": "انتخاب داخلی",
        "Dynamic Members": "اعضای پویا",
        "Timing & Agent Options": "زمان‌بندی اپراتورها",
        "Max Wait Time": "سقف انتظار",
        "Max Wait Time Mode": "شیوهٔ خروج",
        "Agent Timeout": "مهلت اپراتور",
        "Agent Timeout Restart": "تجدید مهلت",
        "Retry": "فاصلهٔ تلاش",
        "Wrap-Up-Time": "فرصت جمع‌بندی",
        "Member Delay": "مکث اتصال",
        "Agent Announcement": "پیام اپراتور",
        "Report Hold Time": "اعلام انتظار",
        "Auto Pause": "توقف خودکار",
        "Auto Pause on Busy": "توقف مشغول‌ها",
        "Auto Pause on Unavailable": "توقف دسترس‌ناپذیرها",
        "Auto Pause Delay": "مهلت توقف",
        "Capacity Options": "ظرفیت صف",
        "Max Callers": "سقف تماس‌گیرندگان",
        "Join Empty": "پذیرش بی‌اپراتور",
        "Leave Empty": "خروج بی‌اپراتور",
        "Penalty Members Limit": "آستانهٔ اولویت",
        "Caller Position Announcements": "اعلام نوبت",
        "Frequency": "فاصلهٔ اعلان",
        "Announce Position": "اعلام جایگاه",
        "Announce Hold Time": "اعلام انتظار",
        "Periodic Announcements": "پیام‌های دوره‌ای",
        "IVR Break Out Menu": "منوی خروج",
        "Repeat Frequency": "فاصلهٔ تکرار",
        "Events, Stats and Advanced": "پایش صف",
        "Event When Called": "رویداد زنگ",
        "Member Status Event": "رویداد وضعیت",
        "Service Level": "معیار پاسخ",
        "Agent Regex Filter": "الگوی عضویت",
        "Fail Over Destination": "مقصد جایگزین",
        "Queue Continue Destination": "ادامهٔ تماس",
        "Reset Queue Stats": "بازنشانی آمار",
        "Add IVR": "افزودن منو",
        "IVR General Options": "مشخصات منو",
        "IVR Name": "نام منو",
        "IVR Description": "توضیح منو",
        "IVR Options (DTMF)": "رفتار منو",
        "Announcement": "پیام راهنما",
        "Direct Dial": "تماس داخلی",
        "Timeout": "مهلت انتخاب",
        "Invalid Retries": "فرصت اصلاح",
        "Invalid Retry Recording": "پیام اشتباه",
        "Append Announcement on Invalid": "تکرار راهنما",
        "Return on Invalid": "بازگشت منو",
        "Invalid Destination": "مقصد اشتباه",
        "Timeout Retries": "فرصت مجدد",
        "Timeout Retry Recording": "یادآوری انتخاب",
        "Append Announcement on Timeout": "تکرار راهنما",
        "Return on Timeout": "بازگشت منو",
        "Timeout Recording": "پیام بی‌انتخابی",
        "Timeout Destination": "مقصد بی‌انتخابی",
        "Return to IVR after VM": "بازگشت منو",
        "IVR Entries": "کلیدهای منو",
        "Invalid Recording": "پیام نهایی",
        "Time Condition name": "نام زمان‌بندی",
        "Destination if time matches": "مقصد زمان‌بندی",
        "Recording": "پیام صوتی",
        "Repeat": "تکرار پیام",
        "Allow Skip": "ردکردن پیام",
        "Return to IVR": "بازگشت منو",
        "Don't Answer Channel": "بدون پاسخ",
        "Text to Speech": "خواندن متن",
        "Text": "متن پیام",
        "Conference Number": "شمارهٔ نشست",
        "Conference Name": "نام نشست",
        "User PIN": "رمز شرکت‌کننده",
        "Admin PIN": "رمز مدیر",
        "Conference Options": "تنظیمات نشست",
        "Join Message": "پیام ورود",
        "Leader Wait": "انتظار مدیر",
        "Talker Optimization": "بهینه‌سازی صدا",
        "Talker Detection": "تشخیص گوینده",
        "Quiet Mode": "اعلان خاموش",
        "User Count": "اعلام تعداد",
        "User join/leave": "اعلان حضور",
        "Allow Menu": "منوی کنترل",
        "Record Conference": "ضبط نشست",
        "Maximum Participants": "ظرفیت نشست",
        "Mute on Join": "ورود بی‌صدا",
        "Add an Extension": "افزودن داخلی",
        "Device": "نوع دستگاه",
        "Add": "افزودن",
    };

    /* "?" tip per label: shown for fields that have no stock bubble.
       Descriptive one-sentence Persian (round 19, GPT-reviewed). */
    var TIPS = {
        "General Settings": "تنظیمات اصلی این بخش را برای نحوهٔ کار تماس‌ها مشخص می‌کنید.",
        "Additional Settings": "گزینه‌های تکمیلی این بخش را متناسب با نیاز مرکز تلفن تنظیم می‌کنید.",
        "Options": "رفتار این بخش را با انتخاب گزینه‌های موجود تنظیم می‌کنید.",
        "Description": "توضیحی کوتاه بنویسید تا کاربرد این مورد بعداً مشخص باشد.",
        "Language": "زبان پیام‌های صوتی سامانه را برای این تماس‌ها تعیین می‌کنید.",
        "Call Recording": "مشخص می‌کنید تماس‌های این بخش با چه شرایطی ضبط شوند.",
        "Music On Hold": "موسیقی پخش‌شده برای تماس‌گیرنده هنگام انتظار را در این بخش انتخاب می‌کنید.",
        "Music on Hold": "موسیقی پخش‌شده برای تماس‌گیرنده هنگام انتظار را در این بخش انتخاب می‌کنید.",
        "Music on Hold Class": "دستهٔ موسیقی انتظار را برای تماس‌های این بخش انتخاب می‌کنید.",
        "Music On Hold Class": "دستهٔ موسیقی انتظار را برای تماس‌های این بخش انتخاب می‌کنید.",
        "Alert Info": "اطلاعاتی به تلفن مقصد می‌فرستد تا زنگ متفاوتی پخش کند.",
        "CID name prefix": "این متن پیش از نام تماس‌گیرنده روی تلفن مقصد نمایش داده می‌شود.",
        "Time Group": "مجموعهٔ روزها و ساعت‌های موردنظر را برای بررسی زمان تماس انتخاب می‌کنید.",
        "Set Destination": "مشخص می‌کنید تماس پس از این مرحله به کجا فرستاده شود.",
        "Clear Destination & Submit": "مقصد انتخاب‌شده را پاک می‌کند و تغییرات این بخش را ثبت می‌کند.",
        "CID Lookup Source": "منبع جست‌وجوی نام تماس‌گیرنده را بر اساس شمارهٔ او انتخاب می‌کنید.",
        "Source": "منبعی را انتخاب می‌کنید که اطلاعات موردنیاز از آن دریافت شود.",
        "Privacy": "نحوهٔ برخورد با تماس‌های فاقد شمارهٔ قابل‌شناسایی را در این بخش تعیین می‌کنید.",
        "Privacy Manager": "از تماس‌گیرندهٔ بدون شماره می‌خواهد پیش از ادامه، شمارهٔ خود را وارد کند.",
        "Max attempts": "حداکثر دفعات مجاز برای واردکردن شماره توسط تماس‌گیرنده را تعیین می‌کنید.",
        "Min Length": "حداقل تعداد رقم لازم برای پذیرش شمارهٔ واردشده را تعیین می‌کنید.",
        "Destination after playback": "مشخص می‌کنید تماس پس از پخش پیام به کجا فرستاده شود.",
        "DID Number": "شماره‌ای را وارد کنید که تماس‌های ورودی آن مشمول این مسیر شوند.",
        "CallerID Number": "شمارهٔ تماس‌گیرنده را برای محدودکردن این مسیر به تماس‌های او وارد کنید.",
        "CID Priority Route": "مسیر مختص شمارهٔ تماس‌گیرنده را بر مسیر عمومی شمارهٔ ورودی مقدم می‌کند.",
        "Signal RINGING": "پیش از پاسخ، وضعیت زنگ‌خوردن را به سمت تماس‌گیرنده اعلام می‌کند.",
        "Pause Before Answer": "مدت مکث پیش از پاسخ‌دادن سامانه به تماس ورودی را تعیین می‌کنید.",
        "Route Name": "نامی انتخاب کنید که کاربرد این مسیر خروجی را مشخص کند.",
        "Route CID": "شمارهٔ معرفی‌شده به مقصد را برای تماس‌های این مسیر تعیین می‌کنید.",
        "Route Password": "تماس‌گیرنده باید پیش از استفاده از این مسیر، رمز تعیین‌شده را وارد کند.",
        "Route Type": "مشخص می‌کنید این مسیر برای تماس‌های عادی، اضطراری یا داخلی استفاده شود.",
        "Route Position": "جایگاه این مسیر را در ترتیب بررسی مسیرهای خروجی تعیین می‌کنید.",
        "PIN Set": "مجموعهٔ رمزهای مجاز برای استفاده از این مسیر را انتخاب می‌کنید.",
        "Trunk Sequence for Matched Routes": "ترانک‌ها برای تماس‌های منطبق با این مسیر به ترتیب انتخاب‌شده امتحان می‌شوند.",
        "NAT Settings": "تنظیمات ارتباط تلفنی از پشت مترجم نشانی شبکه را اینجا مشخص می‌کنید.",
        "NAT": "نحوهٔ سازگاری ارتباط SIP با ترجمهٔ نشانی شبکه را تعیین می‌کنید.",
        "IP Configuration": "مشخص می‌کنید نشانی اینترنتی مرکز تلفن ثابت است یا تغییر می‌کند.",
        "External IP": "نشانی ثابت قابل‌دسترسی مرکز تلفن از بیرون شبکه را وارد کنید.",
        "Dynamic Host": "نام دامنه‌ای را وارد کنید که نشانی اینترنتی متغیر شما را دنبال می‌کند.",
        "Local Networks": "محدوده‌های شبکهٔ داخلی را مشخص کنید تا ارتباط آن‌ها محلی شناخته شود.",
        "Audio Codecs": "قالب‌های مجاز انتقال صدا و ترتیب ترجیح آن‌ها را انتخاب می‌کنید.",
        "Codecs": "قالب‌های مجاز انتقال رسانه و ترتیب ترجیح آن‌ها را تعیین می‌کنید.",
        "Non-Standard g726": "شیوهٔ بسته‌بندی این قالب صدا را برای سازگاری با تجهیزات قدیمی تغییر می‌دهد.",
        "T38 Pass-Through": "عبور نمابر با T38 را میان دو طرف تماس امکان‌پذیر می‌کند.",
        "Video Codecs": "قالب‌های مجاز انتقال تصویر و ترتیب ترجیح آن‌ها را انتخاب می‌کنید.",
        "Video Support": "امکان انتقال تصویر را در تماس‌های سازگار با این قابلیت فعال می‌کند.",
        "Max Bit Rate": "حداکثر نرخ انتقال دادهٔ تصویری را برای تماس‌های این بخش تعیین می‌کنید.",
        "MEDIA & RTP Settings": "تنظیمات انتقال صدا و تصویر بین طرف‌های تماس را مشخص می‌کنید.",
        "Reinvite Behavior": "مشخص می‌کنید رسانه مستقیم بین طرفین منتقل شود یا از مرکز تلفن بگذرد.",
        "RTP Timers": "مهلت قطع تماس بدون رسانه و فاصلهٔ ارسال بسته‌های نگهدارنده را تعیین می‌کنید.",
        "RTP Port Ranges": "بازهٔ درگاه‌های شبکه را برای انتقال صدا و تصویر تعیین می‌کنید.",
        "Notification & MWI": "تنظیمات اعلان وضعیت تماس و وجود پیام صوتی را مشخص می‌کنید.",
        "MWI Polling Freq": "فاصلهٔ بررسی صندوق صوتی برای به‌روزرسانی نشانگر پیام تلفن را تعیین می‌کنید.",
        "Notify Ringing": "وضعیت زنگ‌خوردن داخلی را به تلفن‌های مشترک اعلان وضعیت اطلاع می‌دهد.",
        "Notify Hold": "وضعیت نگه‌داشتن تماس را به تلفن‌های مشترک اعلان وضعیت اطلاع می‌دهد.",
        "Registration Settings": "تنظیمات ثبت و تمدید ارتباط SIP با تجهیزات مقابل را مشخص می‌کنید.",
        "Registrations": "ارتباط‌های SIP ثبت‌شده با تجهیزات مقابل را در این بخش مدیریت می‌کنید.",
        "Registration Times": "زمان اعتبار و تمدید ثبت ارتباط تجهیزات SIP را تعیین می‌کنید.",
        "Jitter Buffer Settings": "تنظیمات جبران نوسان زمان رسیدن بسته‌های صوتی را مشخص می‌کنید.",
        "Jitter Buffer": "با نگهداری کوتاه بسته‌های صوتی، نوسان زمان رسیدن آن‌ها را جبران می‌کند.",
        "Force Jitter Buffer": "استفاده از هموارسازی صدا را حتی در شرایط معمولاً غیرضروری اجباری می‌کند.",
        "Implementation": "روش ثابت یا تطبیقی جبران نوسان بسته‌های صوتی را انتخاب می‌کنید.",
        "Jitter Buffer Logging": "جزئیات عملکرد هموارسازی صدا را برای بررسی مشکلات ارتباط ثبت می‌کند.",
        "Jitter Buffer Size": "حداکثر ظرفیت زمانی نگهداری بسته‌های صوتی برای هموارسازی را تعیین می‌کنید.",
        "Advanced General Settings": "گزینه‌های تخصصی رفتار عمومی ارتباطات تلفنی را در این بخش تنظیم می‌کنید.",
        "Default Context": "بخش پیش‌فرض پردازش تماس‌های SIP را در برنامهٔ مسیریابی تعیین می‌کنید.",
        "Bind Address": "نشانی شبکه‌ای را تعیین می‌کنید که سرویس SIP روی آن درخواست دریافت کند.",
        "Bind Port": "شمارهٔ درگاه دریافت درخواست‌های SIP را در مرکز تلفن تعیین می‌کنید.",
        "TLS Bind Port": "شمارهٔ درگاه دریافت ارتباط‌های رمزگذاری‌شده با TLS را تعیین می‌کنید.",
        "Allow SIP Guests": "اجازه می‌دهد درخواست‌های SIP از تجهیزات فاقد حساب شناخته‌شده پذیرفته شوند.",
        "Allow Anonymous Inbound SIP Calls": "اجازه می‌دهد تماس‌های ورودی SIP بدون شناسایی حساب به مسیر ورودی برسند.",
        "SRV Lookup": "نشانی و درگاه سرویس SIP مقصد را از رکوردهای SRV پیدا می‌کند.",
        "Call Events": "رویدادهای تماس را برای دریافت توسط ابزارهای مدیریتی تولید می‌کند.",
        "Enable Websocket": "دریافت ارتباط SIP از برنامه‌های تحت مرورگر را فعال می‌کند.",
        "Other SIP Settings": "گزینه‌های اضافی SIP را که در فرم نیستند اینجا وارد می‌کنید.",
        "General Queue Options": "تنظیمات اصلی صف و نحوهٔ توزیع تماس‌ها را مشخص می‌کنید.",
        "Queue Number": "شماره‌ای تعیین کنید که با گرفتن آن، تماس وارد صف شود.",
        "Queue Name": "نامی انتخاب کنید که کاربرد این صف را مشخص کند.",
        "Queue Password": "اپراتور برای ورود به صف باید رمز تعیین‌شده را وارد کند.",
        "Generate Device Hints": "امکان نمایش وضعیت عضویت اپراتورها در صف روی کلیدهای تلفن را فراهم می‌کند.",
        "Call Confirm": "اپراتور باید با فشردن کلید، پذیرش تماس صف را تأیید کند.",
        "Call Confirm Announce": "پیام درخواست تأیید پذیرش تماس را برای اپراتور پخش می‌کند.",
        "CID Name Prefix": "این متن پیش از نام تماس‌گیرنده روی تلفن مقصد نمایش داده می‌شود.",
        "Wait Time Prefix": "مدت انتظار در صف را پیش از نام تماس‌گیرنده نمایش می‌دهد.",
        "Restrict Dynamic Agents": "ورود به صف را به اپراتورهای ثبت‌شده در فهرست اعضای پویا محدود می‌کند.",
        "Agent Restrictions": "نحوهٔ تماس با اپراتورها و رعایت انتقال تماس داخلی‌ها را تعیین می‌کنید.",
        "Ring Strategy": "روش انتخاب اپراتور و ترتیب زنگ‌خوردن تلفن‌های صف را تعیین می‌کنید.",
        "Autofill": "چند تماس منتظر را هم‌زمان به اپراتورهای آزاد صف می‌فرستد.",
        "Skip Busy Agents": "هنگام توزیع تماس، اپراتورهایی را که مشغول مکالمه هستند کنار می‌گذارد.",
        "Queue Weight": "اولویت این صف را برای دریافت خدمات اپراتورهای مشترک تعیین می‌کنید.",
        "Join Announcement": "پیش از ورود تماس‌گیرنده به صف، پیام انتخاب‌شده را پخش می‌کند.",
        "Recording Mode": "قالب فایل صوتی ضبط تماس‌های این صف را انتخاب می‌کنید.",
        "Caller Volume Adjustment": "بلندی صدای تماس‌گیرنده را برای شنیده‌شدن توسط اپراتور تنظیم می‌کنید.",
        "Agent Volume Adjustment": "بلندی صدای اپراتور را برای شنیده‌شدن توسط تماس‌گیرنده تنظیم می‌کنید.",
        "Mark calls answered elsewhere": "تماس پذیرفته‌شده توسط اپراتور دیگر را روی تلفن‌ها پاسخ‌داده‌شده علامت می‌زند.",
        "Queue Members": "اپراتورهای ثابت و دارای امکان ورود اختیاری به صف را مشخص می‌کنید.",
        "Static Agents": "اپراتورهایی را مشخص می‌کنید که همواره عضو این صف باشند.",
        "Extension Quick Pick": "داخلی موردنظر را سریع از فهرست انتخاب و به اعضای صف اضافه می‌کنید.",
        "Dynamic Members": "اپراتورهایی را مشخص می‌کنید که بتوانند به صف وارد یا از آن خارج شوند.",
        "Timing & Agent Options": "زمان‌های انتظار و رفتار صف در ارتباط با اپراتورها را تنظیم می‌کنید.",
        "Max Wait Time": "حداکثر مدت ماندن تماس‌گیرنده در صف پیش از انتقال را تعیین می‌کنید.",
        "Max Wait Time Mode": "خروج در پایان مهلت را فوری یا پس از پایان زنگ اپراتور تعیین می‌کنید.",
        "Agent Timeout": "مدت زنگ‌خوردن تلفن اپراتور برای پذیرش هر تماس صف را تعیین می‌کنید.",
        "Agent Timeout Restart": "با دریافت وضعیت اشغال یا ازدحام، شمارش مهلت پاسخ اپراتور را از نو آغاز می‌کند.",
        "Retry": "فاصلهٔ زمانی پیش از تلاش دوباره برای تماس با اپراتورها را تعیین می‌کنید.",
        "Wrap-Up-Time": "پس از مکالمه، مدتی برای جمع‌بندی اپراتور پیش از تماس بعدی در نظر می‌گیرد.",
        "Member Delay": "پس از پاسخ اپراتور، اتصال او به تماس‌گیرنده را کمی به تأخیر می‌اندازد.",
        "Agent Announcement": "پیش از اتصال تماس‌گیرنده، پیام انتخاب‌شده را برای اپراتور پخش می‌کند.",
        "Report Hold Time": "پیش از اتصال، مدت انتظار تماس‌گیرنده در صف را به اپراتور اعلام می‌کند.",
        "Auto Pause": "اپراتور بی‌پاسخ را موقتاً از دریافت تماس‌های صف کنار می‌گذارد.",
        "Auto Pause on Busy": "دریافت وضعیت اشغال از تلفن اپراتور را مشمول توقف خودکار می‌کند.",
        "Auto Pause on Unavailable": "خطای دسترسی به تلفن اپراتور را مشمول توقف خودکار می‌کند.",
        "Auto Pause Delay": "حداقل فاصله از آخرین پاسخ اپراتور برای اعمال توقف خودکار را تعیین می‌کنید.",
        "Capacity Options": "ظرفیت پذیرش تماس و شرایط ورود یا خروج از صف را تنظیم می‌کنید.",
        "Max Callers": "حداکثر تعداد تماس‌گیرندگان منتظر در این صف را تعیین می‌کنید.",
        "Join Empty": "شرایط ورود تماس‌گیرنده به صف فاقد اپراتور قابل‌پاسخ را تعیین می‌کنید.",
        "Leave Empty": "شرایط خروج تماس‌گیرنده از صف فاقد اپراتور قابل‌پاسخ را تعیین می‌کنید.",
        "Penalty Members Limit": "اگر تعداد اعضا از این حد بیشتر نباشد، محدودیت اولویت اپراتورها نادیده گرفته می‌شود.",
        "Caller Position Announcements": "تنظیمات اعلام جایگاه تماس‌گیرنده و برآورد مدت انتظار را مشخص می‌کنید.",
        "Frequency": "فاصلهٔ زمانی اعلام نوبت و برآورد انتظار به تماس‌گیرنده را تعیین می‌کنید.",
        "Announce Position": "جایگاه تماس‌گیرنده در صف را هنگام پخش اعلان به او می‌گوید.",
        "Announce Hold Time": "مدت انتظار تخمینی تا پاسخ اپراتور را به تماس‌گیرنده اعلام می‌کند.",
        "Periodic Announcements": "پیام‌هایی را تنظیم می‌کنید که طی انتظار تماس‌گیرنده به‌صورت دوره‌ای پخش شوند.",
        "IVR Break Out Menu": "منوی صوتی انتخاب‌شده امکان خروج تماس‌گیرنده از صف با فشردن کلید را فراهم می‌کند.",
        "Repeat Frequency": "فاصلهٔ زمانی پخش دوبارهٔ پیام دوره‌ای برای تماس‌گیرنده را تعیین می‌کنید.",
        "Events, Stats and Advanced": "تنظیمات رویدادها، آمار عملکرد و گزینه‌های پیشرفتهٔ صف را مشخص می‌کنید.",
        "Event When Called": "هنگام تماس صف با اپراتور، رویداد مدیریتی مربوط را تولید می‌کند.",
        "Member Status Event": "تغییر وضعیت اعضای صف را با تولید رویداد مدیریتی اعلام می‌کند.",
        "Service Level": "مهلت پاسخ مطلوب را برای محاسبهٔ شاخص سطح خدمت صف تعیین می‌کنید.",
        "Agent Regex Filter": "فقط اپراتورهای پویا با شناسهٔ منطبق بر این الگو می‌توانند وارد صف شوند.",
        "Fail Over Destination": "مقصد تماس‌هایی را تعیین می‌کنید که صف نتوانسته به اپراتور متصل کند.",
        "Queue Continue Destination": "پس از قطع تماس توسط اپراتور، تماس‌گیرنده به این مقصد فرستاده می‌شود.",
        "Reset Queue Stats": "آمار جمع‌شدهٔ این صف را برای شروع دورهٔ تازه پاک می‌کند.",
        "Add IVR": "فرم ساخت منوی صوتی تازه را برای تعریف راهنما و مقصدها باز می‌کند.",
        "IVR General Options": "نام و توضیح منوی صوتی را در این بخش وارد می‌کنید.",
        "IVR Name": "نامی انتخاب کنید که کاربرد این منوی صوتی را مشخص کند.",
        "IVR Description": "توضیحی کوتاه دربارهٔ کاربرد این منوی صوتی وارد کنید.",
        "IVR Options (DTMF)": "پیام راهنما و رفتار منوی صوتی هنگام دریافت کلید را تنظیم می‌کنید.",
        "Announcement": "پیام انتخاب‌شده هنگام ورود تماس‌گیرنده به منوی صوتی پخش می‌شود.",
        "Direct Dial": "اجازه می‌دهد تماس‌گیرنده در منوی صوتی، شمارهٔ داخلی را مستقیماً بگیرد.",
        "Timeout": "مدت انتظار منوی صوتی برای دریافت کلید از تماس‌گیرنده را تعیین می‌کنید.",
        "Invalid Retries": "تعداد فرصت‌های دوباره پس از واردکردن انتخاب نامعتبر را تعیین می‌کنید.",
        "Invalid Retry Recording": "پس از انتخاب نامعتبر، پیش از فرصت دوباره این پیام پخش می‌شود.",
        "Append Announcement on Invalid": "پس از پیام اشتباه، راهنمای اصلی منوی صوتی دوباره پخش می‌شود.",
        "Return on Invalid": "پس از اتمام فرصت‌های اصلاح، تماس در صورت وجود به منوی قبلی برمی‌گردد.",
        "Invalid Destination": "پس از پایان فرصت‌های اصلاح و پخش پیام نهایی، تماس به این مقصد می‌رود.",
        "Timeout Retries": "تعداد فرصت‌های دوباره در صورت دریافت‌نکردن کلید از تماس‌گیرنده را تعیین می‌کنید.",
        "Timeout Retry Recording": "پس از پایان مهلت انتخاب، پیش از فرصت دوباره این پیام پخش می‌شود.",
        "Append Announcement on Timeout": "پس از پیام یادآوری، راهنمای اصلی منوی صوتی دوباره پخش می‌شود.",
        "Return on Timeout": "پس از اتمام فرصت‌های انتخاب، تماس در صورت وجود به منوی قبلی برمی‌گردد.",
        "Timeout Recording": "پس از پایان فرصت‌های انتخاب، این پیام پیش از انتقال نهایی پخش می‌شود.",
        "Timeout Destination": "اگر تماس‌گیرنده در فرصت‌های مجاز کلیدی نزند، تماس به این مقصد می‌رود.",
        "Return to IVR after VM": "پس از خروج تماس‌گیرنده از صندوق صوتی داخلی، او به همین منو برمی‌گردد.",
        "IVR Entries": "کلیدهای قابل‌انتخاب تماس‌گیرنده و مقصد مربوط به هرکدام را مشخص می‌کنید.",
        "Invalid Recording": "پس از پایان فرصت‌های اصلاح، این پیام پیش از انتقال نهایی پخش می‌شود.",
        "Time Condition name": "نامی انتخاب کنید که کاربرد این شرط زمانی را مشخص کند.",
        "Destination if time matches": "اگر زمان تماس با بازهٔ انتخاب‌شده منطبق باشد، تماس به این مقصد می‌رود.",
        "Recording": "فایل صوتی موردنظر را برای پخش در این مرحله انتخاب می‌کنید.",
        "Repeat": "تعداد دفعات تکرار پیام صوتی برای تماس‌گیرنده را تعیین می‌کنید.",
        "Allow Skip": "اجازه می‌دهد تماس‌گیرنده با فشردن کلید، پخش پیام را رد کند.",
        "Return to IVR": "پس از پخش پیام، تماس در صورت وجود به منوی صوتی قبلی برمی‌گردد.",
        "Don't Answer Channel": "پیام را بدون اعلام پاسخ‌دادن به تماس در این مرحله پخش می‌کند.",
        "Text to Speech": "متن نوشته‌شده را به گفتار تبدیل و برای تماس‌گیرنده پخش می‌کند.",
        "Text": "متنی بنویسید که سامانه آن را برای تماس‌گیرنده بخواند.",
        "Conference Number": "شماره‌ای تعیین کنید که با گرفتن آن، تماس وارد نشست تلفنی شود.",
        "Conference Name": "نامی انتخاب کنید که کاربرد این نشست تلفنی را مشخص کند.",
        "User PIN": "شرکت‌کننده برای ورود به نشست باید این رمز را وارد کند.",
        "Admin PIN": "ورود با این رمز، اختیارات مدیریتی نشست را در اختیار تماس‌گیرنده می‌گذارد.",
        "Conference Options": "رفتار شرکت‌کنندگان و امکانات این نشست تلفنی را تنظیم می‌کنید.",
        "Join Message": "پیام انتخاب‌شده پیش از ورود تماس‌گیرنده به نشست تلفنی پخش می‌شود.",
        "Leader Wait": "شرکت‌کنندگان تا ورود مدیر، برای آغاز مکالمه در انتظار می‌مانند.",
        "Talker Optimization": "پردازش صدای شرکت‌کنندگان ساکت را کاهش می‌دهد تا منابع کمتری مصرف شود.",
        "Talker Detection": "وضعیت صحبت‌کردن شرکت‌کنندگان را تشخیص می‌دهد و رویداد مربوط تولید می‌کند.",
        "Quiet Mode": "پیام‌های خودکار ورود و خروج شرکت‌کنندگان در نشست را پخش نمی‌کند.",
        "User Count": "تعداد شرکت‌کنندگان حاضر را هنگام ورود به تماس‌گیرنده اعلام می‌کند.",
        "User join/leave": "ورود و خروج شرکت‌کنندگان را با پخش پیام در نشست اعلام می‌کند.",
        "Allow Menu": "اجازه می‌دهد شرکت‌کننده با فشردن ستاره به منوی کنترل نشست دسترسی پیدا کند.",
        "Record Conference": "صدای مکالمهٔ شرکت‌کنندگان این نشست تلفنی را ضبط می‌کند.",
        "Maximum Participants": "حداکثر تعداد شرکت‌کنندگان مجاز برای حضور هم‌زمان در نشست را تعیین می‌کنید.",
        "Mute on Join": "صدای شرکت‌کننده را هنگام ورود به نشست برای دیگران غیرفعال می‌کند.",
        "Add an Extension": "فرم ساخت داخلی تازه را برای اتصال تلفن یا نرم‌افزار تماس باز می‌کند.",
        "Device": "نوع دستگاه یا فناوری ارتباطی داخلی تازه را انتخاب می‌کنید.",
        "Add": "فرم ایجاد مورد تازه را در همین بخش باز می‌کند.",
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

    /* give a label cell a "?" bubble when stock shipped none: we build
       the exact stock DOM shape (span.infohelp > span) so all stock
       hover styling applies unchanged */
    function addTip(el, tip) {
        if (!el || !tip || el.querySelector(":scope > .infohelp")) return;
        var doc = el.ownerDocument;
        var pill = doc.createElement("span");
        pill.className = "infohelp";
        pill.appendChild(doc.createTextNode("?"));   /* the visible marker */
        var txt = doc.createElement("span");
        txt.setAttribute("dir", "rtl");
        txt.dataset.mtHelp = "1";   /* passHelps skips it: already Persian */
        txt.textContent = tip;
        pill.appendChild(txt);
        el.appendChild(pill);
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

    /* synthesized "?" bubbles for mapped labels that lack a stock one */
    function passTips() {
        var tds = document.querySelectorAll("form td:first-child, .content form td:first-child");
        for (var i = 0; i < tds.length; i++) {
            var td = tds[i];
            if (!td.querySelector(":scope > .mt-sub")) continue;
            if (td.querySelector(":scope > .infohelp")) continue;
            var clone = td.cloneNode(true);
            var ih = clone.querySelectorAll(".infohelp, .mt-sub, input, select, button");
            for (var j = 0; j < ih.length; j++) { ih[j].remove(); }
            var t = clean(clone.textContent);
            if (t && TIPS[t]) addTip(td, TIPS[t]);
        }
    }

    /* dynamic option tables (IVR DTMF rows): narrow every digit input,
       tooltip it, and drop one Persian usage hint above the table */
    function passDtmf() {
        var inputs = document.querySelectorAll('input[placeholder="digits pressed"], input[placeholder="کلید"]');
        for (var i = 0; i < inputs.length; i++) {
            var input = inputs[i];
            input.title = "کلید موردنظر تماس‌گیرنده (0 تا 9 یا * و #)";
            input.placeholder = "کلید";
        }
        var first = inputs[0];
        if (!first) return;
        var tbl = first.closest("table");
        if (!tbl || tbl.parentNode.querySelector(":scope > .mt-note")) return;
        var doc = first.ownerDocument;
        var note = doc.createElement("div");
        note.className = "mt-note";
        note.setAttribute("dir", "rtl");
        note.textContent = "هر ردیف یک کلید منوست: رقم کلید (مثلاً 1) را بنویسید و مقصد پس از فشردن آن را انتخاب کنید.";
        tbl.parentNode.insertBefore(note, tbl);
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
        try { passTips(); } catch (e) {}
        try { passRnav(); } catch (e) {}
        try { passHelps(); } catch (e) {}
        try { passButtons(); } catch (e) {}
        try { passDtmf(); } catch (e) {}
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
