# گزارش پوشش کامل رابط — قالب مای‌تل (دورهٔ دوم + سوم + چهارم)

تاریخ: ۲۰۲۶-۱۰-۰۴ | سرور: ۱۹۲.۱۶۸.۸.۱۷۱ | مبنا: menu.db + بازدید واقعی مرورگر

## دورهٔ چهارم — PBX Admin عمیق (RTL کامل کنسول)

- کنسول IssabelPBX (قاب pbxadmin و دسترسی مستقیم /admin) اکنون **راست‌چین واقعی** است:
  dir=rtl روی سند، نوار بالایی معکوس، rnav به لبهٔ چپ، دراپ‌داون‌ها سمت راست، جدول‌ها راست‌چین، ورودی‌های فنی LTR، متون آزاد RTL.
- **فارسی‌سازی کنسول** با فرهنگ لغت ~۹۵ کلیدی (brand.js v6): ناوبری (اعمال تنظیمات/مدیریت/برنامه‌ها/ارتباطات/گزارش‌ها/تنظیمات/سایر/جستجو)، پنل‌های داشبورد (وضعیت مرکز تلفن MyTel، اعلان‌ها، آمار)، سنجه‌ها (پردازنده/میانگین بار/حافظه/دیسک‌ها/تماس‌های فعال...)، اعلان‌ها با حفظ شناسهٔ فنی («خطا در دریافت پیکربندی؛ تنظیمات اعمال نشد (retrieve_conf failed)»، «N ماژول برای به‌روزرسانی در دسترس است»)، دکمه‌ها (ذخیره/حذف/انصراف/بازنشانی/افزودن/ویرایش/بازگشت...)، نام ماژول‌های rnav و دراپ‌داون‌ها.
- **ایزوله‌سازی دوجهتهٔ یونیکد** (LRI/PDI) برای رشته‌های مخلوط فارسی-لاتین تا ترتیب واژه‌ها منطقی بماند.
- عنوان‌های راهنما (tooltip) برای اصطلاحات فنی: PJSIP، RTP، NAT، DTMF، DID.
- **خوانایی منوی کناری پرتال** تقویت شد: رنگ زیرمنو روشن‌تر (C3CEE4)، وزن ۵۰۰/۷۰۰، حالت فعال با نارنجی + پس‌زمینه، والدهای پررنگ.
- کنسول/شبکه: صفر خطای جاوااسکریپت، صفر درخواست ناموفق در pbxadmin.
- واکنش‌گرایی: ۱۹۲۰، ۱۳۶۶، ۱۰۲۴ بررسی شد.
- صفحات بازدیدشدهٔ کنسول در این دوره: داشبورد وضعیت، داخلی‌ها، ترانک‌ها، مسیر ورودی، مسیر خروجی، صف‌ها، IVR، گروه‌های زنگ، ضبط‌ها، تنظیمات SIP (با فرم کامل)، مدیریت ماژول‌ها + هر پنج دراپ‌داون ناوبری.

## خلاصه عددی (تجمعی هر چهار دوره)

| سنجه | مقدار |
|---|---|
| مسیرهای پرتال بازدیدشده | ۷۰ |
| صفحات کنسول PBX بازدیدشده (دورهٔ ۴) | ۱۱ + ۵ دراپ‌داون |
| کلیدهای ترجمهٔ fa.lang | ۳۳۶ + ۷ ماژول پچ‌شده |
| کلیدهای فرهنگ کنسول (brand.js) | ~۹۵ |
| واپس‌های بصری | صفر |
| تغییر بک‌اند / منو / رگرسیون / خطای مرورگر | صفر |

## اصطلاحات فنی عمداً انگلیسی مانده (کنسول)

PBX, VoIP, SIP, PJSIP, RTP, SRTP, WebRTC, NAT, TCP/UDP, TLS/SSL, DNS, DHCP, VLAN, VPN, CID, DID, DTMF, API/AMI/ARI/AGI, CPU, RAM, Swap, SMTP/IMAP/POP3/SPF/DKIM/DMARC, Caller ID, IVR, DISA, chan_sip, codec names, Asterisk contexts, CDR, CSV, iCal.

## رشته‌های باقی‌ماندهٔ انگلیسی و دلیل

- مقادیر پویای داده‌ای (نام کاربران/گروه‌ها/ترانک‌ها، اعداد، مسیرها) — داده‌اند.
- برچسب‌های عمیق فرم‌های FreePBX (هزاران رشتهٔ ماژول‌محور مثل Wizard‌های DAHDI) — نقطهٔ ترجمهٔ رسمی ندارند و جایگزینی کلی ریسک عملکرد دارد؛ پوسته/چیدمان/دکمه‌های عمومی همه مای‌تل و فارسی‌اند.
- نام‌های ماژول‌های کم‌کاربرد در دراپ‌داون‌ها که در فرهنگ نیستند (مثل Provisioner) — اصطلاح تخصصی‌اند.


## جدول پوشش (مسیر → وضعیت)

خرنگاشت‌ها: ✓=بازدید و پذیرش؛ ✦=بازدید با یادداشت

| گروه | مسیرها |
|---|---|
| سیستم | index ✓، applet_admin ✓، hardware_detector ✓، betachannel ✓، backup_restore ✓، shutdown ✓ |
| شبکه | network_parameters ✓، dhcp_server ✓، dhcp_clientlist ✓، dhcp_by_mac ✓، ping ✦ (مقدار پیش‌فرض issabel.org پاک می‌شود) |
| کاربران | userlist ✓، grouplist ✓، group_permission ✓ |
| ترجیحات | language ✓، time_config ✓، themes_system ✓، currency ✓ |
| تقویم/دفترچه | calendar ✦ (ابزار تقویم انگلیسی می‌ماند)، address_book ✓ |
| ایمیل | email_relay ✦ (بازطراحی کارت)، remote_smtp ✦ (بازطراحی کارت)، email_domains ✓، email_accounts ✓، antispam ✓، email_list ✓، email_stats ✓، vacations ✓، webmail ✦ (اپ بیرونی framed) |
| فکس | faxlist ✓، faxnew ✓، sendfax ✓، faxqueue ✓، faxmaster ✓، faxclients ✓، faxviewer ✓، email_template ✓ |
| مرکز تلفن | pbxadmin ✓ (قاب)، voicemail ✦ (اسپانیایی‌ها ترجمه شد)، monitoring ✓، endpoints ✓، conference ✓، asterisk_cli ✓، file_editor ✓، festival ✓، recordings ✓، endpoint_configurator ✓، fop2 (اپ بیرونی framed) |
| گزارش‌ها | cdrreport ✓، channelusage ✓، asterisk_log ✓، graphic_report ✓، summary_by_extension ✓، missed_calls ✓، billing_rates ✓، billing_report ✓، billing_setup ✓، dest_distribution ✓ |
| افزونه‌ها/سایر | addons_availables ✓، meet ✓، myex_config ✓، extensions_batch ✓، qr_batch ✓ |
| امنیت | sec_rules ✓، sec_ports ✓، sec_accessaudit ✓، sec_weak_keys ✓، sec_advanced_settings ✓، sec_letsencrypt ✓، sec_fb_admin ✓، sec_fb_banned ✓، sec_whitelist ✓، sec_geoip_key ✓، sec_geoip_map ✓، sec_portknock_if ✓ |
| PBX Admin (قاب) | dashboard ✓، extensions ✓، trunks + فرم PJSIP ✓، sipsettings ✓، modules ✓ + کل صفحات دیگر از طریق مؤلفه‌های مشترک skin v5-v7 |

## فارسی‌سازی — اصطلاحات فنی که عمداً انگلیسی ماندند

SIP، PJSIP، IAX، DAHDI، ENUM، DUNDi، RTP، SRTP، WebRTC، NAT، TLS/SSL، DNS،
DHCP، VPN، VLAN， codec نام‌ها (ulaw، g729، opus، ...)، DTMF، CID/DID، API/AMI/ARI/AGI،
Fail2Ban، GeoIP، Let's Encrypt، iCal، SMTP/IMAP/POP3/SPF/DKIM/DMARC، Asterisk CLI،
PXE، MAC، URL، FreePBX console UI (زیرسیستم فنی انگلیسی)، دکمه‌های CSV/Excel/PDF.

## ترجمه‌های افزوده/اصلاح‌شده در این دوره

۵۸ کلید تازه در fa.lang (مجموع ۳۱۴): Message، Select/Unselect All، Reconstruct
MailBox، Enabled، Available، Custom privileges، Period، Download ical calendar،
Today/Month/Week/Day، Filter applied، ستون‌های CDR و غیره. اصلاح ماژولی:
FAILED=ناموفق، NO ANSWER=بدون پاسخ، ALL=همه تماس‌ها. جایگزینی متنی مرورگر:
Elastix→MyTel، Marcar todos→انتخاب همه (باگ اسپانیایی voicemail)، Issabel
Foundation→MyTel.

## انگلیسی‌های باقی‌مانده و دلیل

- رابط کنسول IssabelPBX (فرم‌ها/برچسب‌های FreePBX): زیرسیستم فنی انگلیسی است؛
  راست‌چین‌کردن کامل آن ریسک شکست功能性 فرم‌های پی‌بی‌ایکس را دارد و نقطهٔ
  ترجمهٔ رسمی ندارد. برند و پوسته کاملاً مای‌تل است.
- مقادیر داده‌ای (نام گروه‌ها، نام اپلت‌ها، ناشر POSSA/voipsupport.it): داده‌اند نه رابط.
- رشته‌های داخل ابزارهای JS بیرونی (FullCalendar بدون بستهٔ زبان فارسی روی سرور).

## تصمیم راست‌چین برای PBX Admin

کنسول فنی داخل قاب pbxadmin عمداً LTR ماند (محتوای انگلیسی، فرم‌های تودرتو،
خیامن/فلوهای Bootstrap-قدیمی). هرچه فارسی‌محور است در پرتال راست‌چین است و
کنسول کاملاً برند/پوستهٔ مای‌تل گرفته (سربرگ‌ها، فرم‌ها، جدول‌ها، دکمه‌ها،
تاگل‌ها، مودال‌ها). مقادیر فنی در فرم‌های فارسی هم LTR ایزوله می‌شوند
(کلاس mt-ltr و mt-tech).
