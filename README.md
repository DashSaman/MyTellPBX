# MyTel Theme — پوستهٔ فارسی راست‌چین برای ایزابل ۵

پوستهٔ کامل رابط مدیریتی با هویت بصری برند مای‌تل برای سرور ایزابل ۵ روی
نشانی نمونهٔ سامانه: `https://pbx.example.com` — این نشانی را با نام میزبان سرور Issabel خود جایگزین کنید. تمام لایه‌های نمایش (پرتال، صفحهٔ ورود، ماژول‌های قدیمی،
داشبورد، نمودارها و رابط IssabelPBX) با یک نظام طراحی واحد بازطراحی شده‌اند و
هیچ نشانی قابل‌دیدنی از ایزابل باقی نمی‌ماند.

## پیش‌نیازهای نصب (پوستهٔ رویه‌ای)

این بسته یک لایهٔ رویه‌ای (overlay) روی پوستهٔ اصلی ایزابل است، نه یک
پوستهٔ مستقل. فایل‌های پایه‌ای که قالب در آن‌ها ارجاع می‌دهد — از جمله
اسکریپت‌های `neon-*`، `bootstrap.js`، `jquery.validate` و
`iframe-show-loader.js` — باید از نصب اصلی ایزابل (شاخهٔ پیش‌فرض پوسته)
در شاخهٔ مقصد موجود باشند. کتابخانهٔ `echarts` برخلاف این‌ها همراه خود
بسته ارائه می‌شود (باندل‌شده در `theme/vendor/echarts/`) و نیازی به منبع
بیرونی ندارد. پیش از کپی، وجود فایل‌های وارثتی را در مسیر مقصد بررسی
کنید؛ فهرست کامل ارجاع‌ها در فایل `theme/_common/index.tpl` قابل استخراج است.

## ویژگی‌ها

- **چیدمان راست‌چین فارسی** با نوار منوی عمودی نیلی در سمت راست، سربرگ روشن و
  پانویس سبک.
- **هویت برند مای‌تل**: نیلی `#2E3194` (کنش‌های اصلی)، نارنجی `#FF8A00`
  (تأکید)، سرمه‌ای `#0B1526` (سطوح تیره)، فونت **وزیرمتن** کاملاً محلی با پنج
  وزن.
- **صفحهٔ ورود نو**: دوستونه (پنل برند + کارت فرم) با موج‌های پویا.
- **داشبورد بازطراحی‌شده**: کارت‌های اپلت با سربرگ یکدست، نشانگر بارگذاری برند،
  بازرنگ‌آمیزی برند برای نمودارهای فِلات و سنجنده‌ها، حذف اپلت اخبار بیرونی.
- **برندزدایی کامل**: عنوان صفحات، لوگو، فوآیکون، پانویس و همهٔ رشته‌های
  «IssabelPBX» در رابط admin به «MyTel PBX» تبدیل می‌شوند (لایهٔ متنِ مرورگر؛
  بدون تغییر شناسه‌های عملکردی).
- **فارسی‌سازی**: کلیدهای `fa.lang` گسترش یافته (برند voiz قدیمی پاک شده)،
  برچسب‌های وضعیت CDR خواناتر شده‌اند.
- **بدون وابستگی بیرونی**: هیچ فونت یا منبعی از اینترنت بار نمی‌شود.

## ساختار

```
theme/
├── _common/            قالب‌های اس‌مارتی (index, _menu, login, popup, _list, ...)
├── css/
│   ├── fonts.css       وزیرمتن محلی
│   ├── glyphicons.css  فونت آیکون گلیفیکون (دکمه‌های DataTables)
│   ├── tokens.css      توکن‌های طراحی (تک‌منبع رنگ/شعاع/سایه/تایپ)
│   ├── base.css        پوستهٔ پنل (نوار، سربرگ، نان‌ریزه، پانویس، کشوها)
│   ├── components.css  بازآرایی کامل مارک‌آپ قدیمی (بوت‌استرپ۳/neo-*، دیتاتیبل‌ها)
│   ├── applet.css      کارت‌های داشبورد
│   └── login.css       صفحهٔ ورود
├── js/theme.js         رفتارهای پوسته (جستجوی منو، منوی خروجی، بازرنگ نمودار، ...)
├── fonts/vazirmatn/    فایل‌های woff2
└── images/admin/       دارایی‌های برند admin (نشان، فوآیکون، skin.css، brand.js)
```

## استقرار (روش عمومی، بدون ابزار خصوصی)

این بستهٔ عمومی ابزار استقرار همراه ندارد. نصب دستی روی نصب Issabel ۵
پشتیبانی‌شده، با نقشهٔ مقصد زیر انجام می‌شود. پیش از هر کپی، از شاخه‌های
مقصد نسخهٔ پشتیبان شخصی بگیرید (مثلاً `cp -a` با پسوند تاریخ) و پس از
نصب، کش `templates_c` را پاک و مرورگر را تازه‌سازی کنید.

نقشهٔ مقصد (مبدأ در بسته ← مقصد روی سرور):

```
theme/_common/*.tpl        → /var/www/html/themes/mytel/_common/
theme/css/*                → /var/www/html/themes/mytel/css/
theme/js/*.js              → /var/www/html/themes/mytel/js/
theme/vendor/echarts/*     → /var/www/html/themes/mytel/vendor/echarts/
theme/fonts/vazirmatn/*    → /var/www/html/themes/mytel/fonts/vazirmatn/
theme/fonts/glyphicons-halflings-regular.woff
                           → /var/www/html/themes/mytel/fonts/
theme/images/mytel-emblem.svg
                           → /var/www/html/themes/mytel/images/
theme/images/mt-spinner.svg
                           → /var/www/html/themes/mytel/images/
theme/images/favicon.png   → /var/www/html/themes/mytel/images/favicon.png
theme/styles.css           → /var/www/html/themes/mytel/styles.css
theme/themesetup.php       → /var/www/html/themes/mytel/themesetup.php
theme/help.css             → /var/www/html/themes/mytel/help.css
theme/images/admin/*       → /var/www/html/admin/images/  (نشان و فوآیکون)
                             و skin.css → /var/www/html/admin/assets/mytel/skin.css
theme/images/admin/sub.js  → /var/www/html/admin/assets/mytel/sub.js
```

فونت کنسول: فایل `theme/fonts/vazirmatn/Vazirmatn-Regular.woff2` را یک
بار با نام `vazirmatn-regular.woff` به
`/var/www/html/admin/assets/mytel/fonts/` کپی کنید؛ `skin.css` از همان
مسیر نسبی `fonts/vazirmatn-regular.woff` آن را می‌خواند.

ترجمهٔ ماژول‌ها (اختیاری): فایل `fa.lang` بسته، ترجمهٔ گسترده‌یافتهٔ
فارسی ماژول‌هاست. برای اعمال، با پشتیبان از فایل موجود، محتوای آن را
جایگزین `/var/www/html/lang/fa.lang` کنید؛ نادیده‌گرفتن این گام فقط
ترجمهٔ سفارشی ماژول‌ها را غیرفعال می‌گذارد و پوسته کار می‌کند.

فعال‌سازی پرتال: کلیدهای `theme=mytel` و `language=fa` در `settings.db`
(جدول `settings`)؛ فعال‌سازی دارایی کنسول: کلیدهای `BRAND_CSS_CUSTOM`
برای `assets/mytel/skin.css` و `BRAND_ALT_JS` برای `assets/mytel/sub.js`
در پایگاه `asterisk` (جدول `issabelpbx_settings`) — مقدار هر دو با یک
پارامتر کش‌شکنی مانند `?v=6` تمام شود.

برندسازی کنسول (نشان، فوآیکون، پانویس): اگر نصب مقصد تازه است و
می‌خواهید هویت مای‌تل در کنسول هم دیده شود، همین کلیدها را در
`issabelpbx_settings` ثبت کنید (مقادیر، ارجاع به تصاویری که در گام
قبلی به `/var/www/html/admin/images/` کپی شده‌اند):

```
BRAND_TITLE                       = MyTel PBX
BRAND_IMAGE_TANGO_LEFT            = images/mytel-emblem-48.png
BRAND_IMAGE_FAVICON               = images/mytel-favicon.png
BRAND_IMAGE_ISSABELPBX_FOOT       = images/mytel-foot.png
BRAND_IMAGE_ISSABELPBX_LINK_FOOT  = https://mytel.one
BRAND_IMAGE_ISSABELPBX_LINK_LEFT  = https://mytel.one
BRAND_ISSABELPBX_ALT_FOOT         = MyTel
BRAND_ISSABELPBX_ALT_LEFT         = MyTel
```

نصب بدون این کلیدها فقط نشان کنسول را در حالت پیش‌فرض ایزابل نگه
می‌دارد؛ پرتال، تقویم، راهنماها و گزارش‌ها کامل کار می‌کنند. برای
برگشت، همین کلیدها را به مقادیر قبلی خود برگردانید (پشتیبان آن‌ها را
در همان گام نصب ثبت کنید؛ مثلاً `SELECT * FROM issabelpbx_settings
WHERE keyword LIKE 'BRAND%'` پیش از تغییر).

## برگشت به حالت قبل

برگشت، بازیابی همان پشتیبانی است که پیش از نصب گرفتید: کلیدهای
`theme`/`language` و `BRAND_*` را به مقدارهای قبلی برگردانید و شاخه‌های
مقصد را از نسخهٔ پشتیبان خود بازگردانی کنید، سپس کش `templates_c` را
پاک کنید. اسکریپت‌های استقرار و بکاپِ اختصاصیِ محیط توسعه در این
بستهٔ عمومی منتشر نمی‌شوند.

قوانین تغییر: فقط پوشهٔ `themes/mytel`، فایل‌های دارایی کنسول و کلیدهای
`theme`/`language` و `BRAND_*`؛ هیچ فایل پی‌اچ‌پی کسب‌وکار، مسیر
مرکز تلفن، منو یا پایگاه دیگری دست نخورده است.
