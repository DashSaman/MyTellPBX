<div dir="rtl">

# MytelPBX — مرکز تلفن و میز کار مای‌تل

وب‌سایت: [Mytel.one](https://mytel.one)

نسخهٔ **۷٫۷٫۰ بازبینی ۷** از نصاب بومی Issabel برای نصب روی
**Rocky Linux 8.10 Minimal تازه، x86_64** استفاده می‌کند. پس از تکمیل
راه‌اندازی بومی مرکز تلفن و رمزها، لایهٔ MytelPBX و **MytelDesk 1.1.4**
با بستهٔ قفل‌شده و محیط VAD روی CPU نصب می‌شوند.

بازبینی ۳ ثبت جزئیات قطع تماس در CEL و پیام پاک‌سازی پنل را اصلاح می‌کند.
در دو تماس داخلی آزمایشگاهی، میز کار قطع‌کنندهٔ تماس را هم برای تماس‌گیرنده
و هم برای طرف مقابل درست نشان داد. نصب تمیز آنلاین و آفلاین تا پاسخ HTTPS پنل
تأیید شدند. جزئیات در [گزارش بازبینی ۳](docs/releases/7.7.0/revision-3.md) آمده است.

## نصب آنلاین با یک خط

برای نسخهٔ `v7.7.0-r7`، در ترمینال تعاملی سرور تازه و با دسترسی
root اجرا کنید. فایل ابتدا دریافت و سپس با Bash اجرا می‌شود؛ ترمینال برای
پنجره‌های بومی در دسترس می‌ماند:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0-r7/install-mytellpbx.sh && bash install-mytellpbx.sh
```

<div dir="rtl">

نصاب انگلیسی اول رمز `root` پایگاه داده و رمز `admin` پنل را با تأیید هر دو
می‌گیرد. همان‌جا می‌توان نوع SIP را انتخاب کرد. Enter گزینهٔ پیش‌فرض PJSIP را
می‌پذیرد. سپس **استریسک ۲۰** و Community Realtime Block List خودکار نصب و
پیشرفت بسته‌ها در همان ترمینال نمایش داده می‌شود. افزونه‌های اختیاری لایسنس‌دار
از فهرست نصب آنلاین حذف شده‌اند. پس از پاک‌سازی و بررسی نهایی، سرور خودکار
راه‌اندازی مجدد می‌شود. خطای مرحله ادامهٔ نصب و راه‌اندازی مجدد را متوقف می‌کند.

لایهٔ افزوده تا ۱۲۰ ثانیه برای CLI استریسک ۲۰ و فعال‌شدن MariaDB، httpd و
Asterisk صبر می‌کند؛ نسخهٔ اشتباه یا پایان مهلت، خطاست و ادامه را متوقف می‌کند.
پنل وب از اولین ورود فارسی است و گزینهٔ تغییر زبان ندارد.

این مسیر برای نصب تازه است. نصب موجود یا نیمه‌تمام به بررسی و بازیابی محدود
نیاز دارد؛ اجرای دوبارهٔ نصاب پایه، روش ارتقای یک PBX عملیاتی نیست.

## اجزای محصول

- پنل فارسی راست‌چین با فونت وزیرمتن، حالت روشن و تاریک و چیدمان واکنش‌گرا
- کنسول فنی PBX به‌صورت LTR، با برند MytelPBX و بازخورد ذخیره/اعمال پیکربندی
- تقویم شمسی و میز کار در `/MytellDesk/`
- نسخهٔ مشخص MytelDesk و وابستگی‌های VAD روی CPU، همراه بررسی هش و doctor
- حفظ سیاست موجود ضبط و نگهداری فایل‌ها؛ داخلی‌ها، ترانک‌ها و ضبط موردنیاز جداگانه تنظیم می‌شوند

گزینهٔ **حساب پنل** در میز کار از حساب مجاز پنل استفاده می‌کند. مدیر محلی
مستقل میز کار، اطلاعات اولیهٔ جداگانه‌ای در `/etc/myteldesk/initial-admin.txt`
دارد که فقط root می‌تواند بخواند.

## راهنما و وضعیت بررسی

- [نصب فارسی](docs/INSTALL.fa.md) · [Installation guide](docs/INSTALL.en.md)
- [میز کار و VAD](docs/MYTELDESK_INSTALL_FA.md)
- [تغییرات و آزمون‌های بازبینی ۳](docs/releases/7.7.0/revision-3.md)
- [شواهد و محدودیت‌های بازبینی ۲](docs/releases/7.7.0/verification.md)
- [شفافیت اجزای نرم‌افزاری](THIRD_PARTY_NOTICES.md)

نسخهٔ بومی ISO از تصویر اصلی Issabel بازسازی می‌شود. در صفحهٔ بومی
**Software Selection**، فقط MytelPBX با **استریسک ۲۰** ارائه می‌شود.
کنسول اولین راه‌اندازی رمزها و نوع SIP را می‌گیرد و تنظیمات فارسی را خودکار اعمال می‌کند. این ISO خروجی آزمایشگاه مالک
است و روی سرور آزمایشگاه می‌ماند. نصب سرد تصویر نهایی R6 روی دیسک خالی و پاسخ
پنل در [گزارش بازبینی ۳](docs/releases/7.7.0/revision-3.md) ثبت شده‌اند.

نام‌های فنی بالادستی، مانند بسته‌ها، سرویس‌ها، مسیرهای `issabel` و شناسه‌های
پایگاه داده برای سازگاری حفظ می‌شوند؛ برند قابل مشاهده MytelPBX / Mytel.one است.
پایهٔ بومی SELinux و firewalld را غیرفعال می‌کند و از PHP 7.4 استفاده می‌کند؛
دسترسی شبکه و گواهی معتبر را برای محیط مقصد آماده کنید.

سلامت سرویس و اجرای مدل CPU، جای آزمون واقعی ثبت SIP، صدای دوطرفه و VAD
روی تماس ضبط‌شده را نمی‌گیرد. رسید نهایی دامنهٔ واقعی بررسی را مشخص می‌کند.

</div>

---

# MytelPBX 7.7.0 revision 7

The online installer runs the pinned native Issabel flow on **fresh Rocky Linux
8.10 Minimal x86_64**. Its English terminal prompts once for each password and
confirmation, then asks which driver should use the primary SIP port. PJSIP is
the default. It reports package progress as it installs **Asterisk 20** and the
Community Realtime Block List. Mytel branding and checksum-pinned **MytelDesk 1.1.4** with CPU VAD follow
successful native initialization. A bounded 120-second readiness gate waits for
the Asterisk 20 CLI and MariaDB/httpd/Asterisk services; a wrong version or timeout
stops the add-on. The web panel opens in Persian and has no language selector.
The online flow reboots
automatically after native cleanup and the final Desk doctor check succeed.

The one-line command above downloads the script to a file before running Bash,
preserving the interactive terminal. Revision 3 records CEL hangup details and
fixes the native cleanup notification. The [revision 3 record](docs/releases/7.7.0/revision-3.md)
describes the two live internal hangup tests, the verified cleanup, and installation status.

MytelDesk is served at `/MytellDesk/`. **Panel account** uses authorized panel
credentials; the independent Desk administrator record is root-only at
`/etc/myteldesk/initial-admin.txt`. Configure extensions, trunks, trusted TLS and
recording policy for the intended use.

The separate owner-lab ISO uses the native PBX initializer with guided password and SIP setup in the terminal.
Its native **Software Selection** screen offers
**MytelPBX with Asterisk 20 only**. The ISO binary remains on the owner's lab
server. Cold installation and reboot results for the earlier R4 image are in the
[revision 2 record](docs/releases/7.7.0/verification.md).
Upstream technical package/service/database identifiers
remain intact. See the [English installation guide](docs/INSTALL.en.md) for both paths,
network policy and current acceptance limits. Older release records cover their
own versions only.
