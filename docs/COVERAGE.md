# گزارش پوشش کامل رابط — قالب مای‌تل (دورهٔ دوم، تکمیلی)

تاریخ: ۲۰۲۶-۱۰-۰۴ | سرور: ۱۹۲.۱۶۸.۸.۱۷۱ | مبنا: menu.db + بازدید واقعی مرورگر

## خلاصه عددی

| سنجه | مقدار |
|---|---|
| مسیرهای فهرست‌شده در menu.db | ۷۶ |
| مسیرهای بازدیدشده با مرورگر (اسکرین‌شات) | ۷۰ |
| صفحات PBX Admin (داخل قاب pbxadmin) بازدیدشده مستقیم | ۸ (extensions، trunks+فرم، sipsettings، modules، dashboard، reportها از طریق قاب) |
| صفحات ایمیل بازدیدشده | ۸ (relay، remote_smtp، domains، accounts، list، stats، vacations، antispam) |
| صفحات پذیرفته‌شده در داوری بینایی مستقل | ۱۳ (۷+۶ دور قبل) |
| واپس‌های بصری (صفحه‌ای که به اپلیکیشن دیگری تعلق دارد) | صفر |
| تغییر بک‌اند | صفر (فقط فایل‌های مجاز ارائه/زبان) |
| تغییر ساختار منو | صفر |
| رگرسیون عملکردی | صفر |

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
