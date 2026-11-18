<div dir="rtl">

# MytelPBX — مرکز تلفن و میز کار مای‌تل

وب‌سایت: [Mytel.one](https://mytel.one)

نسخهٔ **۷٫۷٫۰ بازبینی ۲** از نصاب بومی Issabel برای نصب روی
**Rocky Linux 8.10 Minimal تازه، x86_64** استفاده می‌کند. پس از تکمیل
راه‌اندازی بومی مرکز تلفن و رمزها، لایهٔ MytelPBX و **MytelDesk 1.1.3**
با بستهٔ قفل‌شده و محیط VAD روی CPU نصب می‌شوند.

دارایی‌های ثابت `v7.7.0-r2`، نصب آنلاین تازه و راه‌اندازی پس از reboot تأیید شده‌اند.
آزمون‌های محدود آزمایشگاه برای تماس و صدای دوطرفه، hold/mute، ضبط بومی، VAD خودکار
و یکسانی بایت‌های پخش و دانلود نیز قبول شده‌اند. پاک‌سازی واقعی آزمون و یک
reboot عادی ISO با حفظ وضعیت و جلوگیری از تکرار نصب تأیید شده‌اند.
[رسید نسخهٔ ۷٫۷٫۰](docs/releases/7.7.0/verification.md) پذیرش در دامنهٔ نصب و
مدیای آزموده‌شده و محدودیت‌های ثبت‌شده را مشخص می‌کند.

## نصب آنلاین با یک خط

برای نسخهٔ منتشرشدهٔ `v7.7.0-r2`، در ترمینال تعاملی سرور تازه و با دسترسی
root اجرا کنید. فایل ابتدا دریافت و سپس با Bash اجرا می‌شود؛ ترمینال برای
پنجره‌های بومی در دسترس می‌ماند:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0-r2/install-mytellpbx.sh && bash install-mytellpbx.sh
```

<div dir="rtl">

نصاب، هش بسته را بررسی می‌کند و ترتیب بومی انتخاب زبان، نصب
**استریسک ۲۰**، بسته‌های اختیاری، نصب و راه‌اندازی
رمزها را اجرا می‌کند. پنجره‌های بومی، رمز MariaDB را همراه تأیید و سپس رمز
مدیر پنل را همراه تأیید می‌پرسند. پس از موفقیت لایهٔ Mytel و doctor پس از پاک‌سازی بومی، مسیر آنلاین طبق
رفتار بومی سرور را خودکار reboot می‌کند. خطای مرحله، ادامه و reboot خودکار را متوقف می‌کند.

لایهٔ افزوده تا ۱۲۰ ثانیه برای CLI استریسک ۲۰ و فعال‌شدن MariaDB، httpd و
Asterisk صبر می‌کند؛ نسخهٔ اشتباه یا پایان مهلت، خطاست و ادامه را متوقف می‌کند.
انتخاب زبان بومی حفظ می‌شود و لایهٔ مای‌تل آن را به فارسی بازنویسی نمی‌کند.

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
- [دامنهٔ تأیید نسخهٔ ۷٫۷٫۰](docs/releases/7.7.0/verification.md)
- [روش آزمون و محدودیت‌ها](docs/TESTING.md)
- [شفافیت اجزای نرم‌افزاری](THIRD_PARTY_NOTICES.md)

نسخهٔ بومی ISO از تصویر اصلی Issabel بازسازی می‌شود. در صفحهٔ بومی
**Software Selection**، فقط MytelPBX با **استریسک ۲۰** ارائه می‌شود.
فرایند بومی اولین راه‌اندازی و انتخاب زبان حفظ می‌شود. این ISO خروجی آزمایشگاه مالک
است و در گیت‌هاب بارگذاری نمی‌شود. نصب سردِ تصویر دقیق R4 در UEFI، راه‌اندازی
بومی و افزونه، چهار سرویس، doctor، حفظ فارسی بومی و TLS/پنل بررسی شده‌اند.
نشانگر خصوصی تکمیل به‌طور طبیعی پس از موفقیت ساخته شده است؛ یک reboot عادی،
حفظ وضعیت و تکرارنشدن راه‌اندازی بومی و افزونه را تأیید کرد.
نتیجهٔ قدیمی R3 و مهاجرت محافظ، شواهد تاریخی جداگانه‌اند.

نام‌های فنی بالادستی، مانند بسته‌ها، سرویس‌ها، مسیرهای `issabel` و شناسه‌های
پایگاه داده برای سازگاری حفظ می‌شوند؛ برند قابل مشاهده MytelPBX / Mytel.one است.
پایهٔ بومی SELinux و firewalld را غیرفعال می‌کند و از PHP 7.4 استفاده می‌کند؛
دسترسی شبکه و گواهی معتبر را برای محیط مقصد آماده کنید.

سلامت سرویس و اجرای مدل CPU، جای آزمون واقعی ثبت SIP، صدای دوطرفه و VAD
روی تماس ضبط‌شده را نمی‌گیرد. رسید نهایی دامنهٔ واقعی بررسی را مشخص می‌کند.

</div>

---

# MytelPBX 7.7.0 revision 2

The online installer runs the pinned native Issabel flow on **fresh Rocky Linux
8.10 Minimal x86_64**. It keeps the native language/package dialogs, installs
**Asterisk 20 only**, and retains the native four-screen password
setup. Mytel branding and checksum-pinned **MytelDesk 1.1.3** with CPU VAD follow
successful native initialization. A bounded 120-second readiness gate waits for
the Asterisk 20 CLI and MariaDB/httpd/Asterisk services; a wrong version or timeout
stops the add-on. Native language choice is retained. The online flow reboots
automatically after native cleanup and the final Desk doctor check succeed.

The one-line command above downloads the script to a file before running Bash,
preserving the interactive terminal. The three frozen `v7.7.0-r2` assets passed
anonymous checksum/manifest readback. Fresh R2 installation/postboot and the bounded
lab core, speech, native recording, automatic CPU VAD and same-call playback/download
checks passed. Independent fixture-cleanup/preservation and the ordinary R4 reboot
checks also passed. The [release record](docs/releases/7.7.0/verification.md) defines
the accepted installation/media scope and its recorded limitations.

MytelDesk is served at `/MytellDesk/`. **Panel account** uses authorized panel
credentials; the independent Desk administrator record is root-only at
`/etc/myteldesk/initial-admin.txt`. Configure extensions, trunks, trusted TLS and
recording policy for the intended use.

The separate owner-lab ISO remasters the original vendor ISO, retaining its
native firstboot/password and language flows. Its native **Software Selection** screen offers
**MytelPBX with Asterisk 20 only**. The ISO binary is
not uploaded to GitHub. A cold UEFI installation of the exact R4 image passed its
native/add-on baseline, services, doctor, native Persian, automatic protected success
marker and TLS/panel checks. One ordinary post-install reboot preserved state and
skipped native initialization/add-on replay;
the earlier R3 installation/guard migration retains its historical scope.
Upstream technical package/service/database identifiers
remain intact. See the [English installation guide](docs/INSTALL.en.md) for both paths,
network policy and current acceptance limits. Older release records cover their
own versions only.
