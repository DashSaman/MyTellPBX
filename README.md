<div dir="rtl">

# MytelPBX — مرکز تلفن و میز کار مای‌تل

وب‌سایت: [Mytel.one](https://mytel.one)

نسخهٔ **۷٫۶٫۲** برای نصب روی **راکی لینوکس ۸٫۱۰ تازه، x86_64** است.
نصاب، استریسک ۲۰ و چارچوب مرکز تلفن را همراه با قالب فارسی مای‌تل و
**MytelDesk 1.1.2** و محیط تحلیل گفتار VAD روی CPU راه‌اندازی می‌کند.

## نصب با یک خط

در ترمینال تعاملی سرور تازه، با دسترسی root و اینترنت اجرا کنید:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.6.2/install-mytellpbx.sh && bash install-mytellpbx.sh
```

<div dir="rtl">

دو ورودی مخفی برای رمز مدیر پنل و رمز ریشهٔ MariaDB نمایش داده می‌شود.
Enter خالی برای همان رمز مقدار تصادفی می‌سازد. رمز انتخابی باید فقط از
حروف لاتین، رقم، فاصله و `.` `@` `=` `_` `!` `-` تشکیل شود.
پس از موفقیت، نشانی پنل و مسیر `/root/mytelpbx-credentials.txt` نمایش داده می‌شود.

این نصاب برای سیستم تازه است؛ ابزار ارتقای نصب موجود PBX نیست. ادامهٔ نصب
فقط برای همان نسخه، هش بسته و وضعیت شناخته‌شده مجاز است. در خطای مقداردهی
اولیه، وضعیت و گزارش را حفظ کنید؛ فایل‌های مالکیت یا رمزها را برای عبور از
کنترل‌ها حذف نکنید.

## اجزای محصول

- پنل فارسی راست‌چین با فونت وزیرمتن و حالت روشن و تاریک
- کنسول فنی PBX به‌صورت LTR، با برند مای‌تل و بازخورد ذخیره/اعمال پیکربندی
- تقویم شمسی و چیدمان واکنش‌گرا
- نصب نسخهٔ مشخص میز کار با بررسی هش، محیط مستقل اجرا و آزمون مدل CPU
- حفظ رمزهای ذخیره‌شده در ادامهٔ مجاز نصب؛ حفظ سیاست ضبط موجود
- فعال ماندن firewalld و باز شدن پورت‌های موردنیاز نصب

میز کار در `/MytellDesk/` باز می‌شود. گزینهٔ **حساب پنل** از حساب مجاز پنل
استفاده می‌کند. مدیر محلی مستقل میز کار رمز جداگانه‌ای در
`/etc/myteldesk/initial-admin.txt` دارد که فقط root می‌تواند بخواند.

## راهنما و وضعیت بررسی

- [نصب فارسی](docs/INSTALL.fa.md) · [Installation guide](docs/INSTALL.en.md)
- [وضعیت بررسی نسخهٔ ۷٫۶٫۲](docs/releases/7.6.2/verification.md)
- [روش آزمون و محدودیت‌ها](docs/TESTING.md)
- [شفافیت اجزای نرم‌افزاری](THIRD_PARTY_NOTICES.md)

بررسی مدل و سلامت سرویس، جای آزمون واقعی تماس را نمی‌گیرد. برای این انتشار،
تکمیل نصب سرد نهایی و آزمون واقعی SIP/صدای دوطرفه/VAD تماس تأیید نشده‌اند.
نصاب کامل فقط استریسک ۲۰ را ارائه می‌کند؛ اجرای جاری روی ۱۶ و ۱۸ تأیید نشده است.
فایل ISO جزو دارایی‌های انتشار گیت‌هاب نیست.

این نصاب SELinux را غیرفعال می‌کند و از PHP 7.4، که پشتیبانی بالادستی آن پایان
یافته، استفاده می‌کند. جزئیات در راهنمای نصب آمده است.

</div>

---

# MytelPBX 7.6.2

A Mytel-branded PBX installer for a **fresh Rocky Linux 8.10 x86_64 server**.
It installs Asterisk 20, the native PBX framework, the Persian panel/admin theme,
and checksum-pinned **MytelDesk 1.1.2** with its CPU VAD runtime.

Use the pinned one-line command above as root in an interactive terminal.
Two hidden inputs collect the panel administrator and MariaDB root passwords;
Enter generates a unique value. This is a fresh-system installer, not an updater
for an operational PBX. An accepted resume preserves saved credentials and
requires the same release, payload hash and recognized state.

MytelDesk is served at `/MytellDesk/`. **Panel account** sign-in uses authorized
native panel credentials; the independent Desk administrator record is root-only
at `/etc/myteldesk/initial-admin.txt`. SIP/WebRTC extensions and recording policy
still need explicit configuration.

See [the English guide](docs/INSTALL.en.md) and
[the current verification record](docs/releases/7.6.2/verification.md).
The final cold-install and real SIP/two-way-audio/call-VAD paths are **not verified**
for this release; Asterisk 16/18 are not offered by the full installer or certified
by the current checks. The ISO binary is not a GitHub release asset.

Source, licenses and notices remain available. SELinux is disabled by this
installer, and the native framework uses upstream-EOL PHP 7.4; review the guide
before exposing the panel. Older release records describe their own scope only.
