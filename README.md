<div dir="rtl">

# MytelPBX — مرکز تلفن و میز کار مای‌تل

وب‌سایت: [Mytel.one](https://mytel.one)

نسخهٔ **۷٫۷٫۰، نامزد انتشار** از نصاب بومی Issabel برای نصب روی
**Rocky Linux 8.10 Minimal تازه، x86_64** استفاده می‌کند. پس از تکمیل
راه‌اندازی بومی مرکز تلفن و رمزها، لایهٔ MytelPBX و **MytelDesk 1.1.2**
با بستهٔ قفل‌شده و محیط VAD روی CPU نصب می‌شوند.

وضعیت نصب نهایی و انتشار هنوز به [رسید نهایی نسخهٔ ۷٫۷٫۰](docs/releases/7.7.0/verification.md)
وابسته است؛ متن و فرمان زیر، انتشار عمومی یا قبولی آزمون تماس را اعلام نمی‌کنند.

## نصب آنلاین با یک خط

پس از انتشار دارایی نهایی `v7.7.0`، در ترمینال تعاملی سرور تازه و با دسترسی
root اجرا کنید. فایل ابتدا دریافت و سپس با Bash اجرا می‌شود؛ ترمینال برای
پنجره‌های بومی در دسترس می‌ماند:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.7.0/install-mytellpbx.sh && bash install-mytellpbx.sh
```

<div dir="rtl">

نصاب، هش بسته را بررسی می‌کند و همان ترتیب بومی انتخاب زبان، انتخاب
**استریسک ۱۶، ۱۸ یا ۲۰ با پیش‌فرض ۱۸**، بسته‌های اختیاری، نصب و راه‌اندازی
رمزها را اجرا می‌کند. پنجره‌های بومی، رمز MariaDB را همراه تأیید و سپس رمز
مدیر پنل را همراه تأیید می‌پرسند. پس از موفقیت لایهٔ Mytel، مسیر آنلاین طبق
رفتار بومی سرور را خودکار reboot می‌کند. خطای مرحله، ادامه و reboot خودکار را متوقف می‌کند.

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
- [وضعیت نامزد ۷٫۷٫۰](docs/releases/7.7.0/verification.md)
- [روش آزمون و محدودیت‌ها](docs/TESTING.md)
- [شفافیت اجزای نرم‌افزاری](THIRD_PARTY_NOTICES.md)

نسخهٔ بومی ISO از تصویر اصلی Issabel بازسازی می‌شود. در صفحهٔ بومی
**Software Selection**، استریسک **۱۶، ۱۸ یا ۲۰** را انتخاب کنید؛ پیش‌فرض
این مسیر ۲۰ است. فرایند بومی اولین راه‌اندازی حفظ می‌شود. این ISO خروجی آزمایشگاه مالک
است و در گیت‌هاب بارگذاری نمی‌شود. مسیر نصب، ساخت و محدودیت‌های آن در راهنما آمده است.

نام‌های فنی بالادستی، مانند بسته‌ها، سرویس‌ها، مسیرهای `issabel` و شناسه‌های
پایگاه داده برای سازگاری حفظ می‌شوند؛ برند قابل مشاهده MytelPBX / Mytel.one است.
پایهٔ بومی SELinux و firewalld را غیرفعال می‌کند و از PHP 7.4 استفاده می‌کند؛
دسترسی شبکه و گواهی معتبر را برای محیط مقصد آماده کنید.

سلامت سرویس و اجرای مدل CPU، جای آزمون واقعی ثبت SIP، صدای دوطرفه و VAD
روی تماس ضبط‌شده را نمی‌گیرد. عرضهٔ گزینه‌های ۱۶ و ۱۸ نیز به معنی تأیید
اجرای همهٔ سناریوها روی آن‌ها نیست؛ رسید نهایی دامنهٔ واقعی بررسی را مشخص می‌کند.

</div>

---

# MytelPBX 7.7.0 candidate

The online installer runs the pinned native Issabel flow on **fresh Rocky Linux
8.10 Minimal x86_64**. It keeps the native language/package dialogs, Asterisk
**16/18/20 selection with 18 as the default**, and the native four-screen password
setup. Mytel branding and checksum-pinned **MytelDesk 1.1.2** with CPU VAD follow
successful native initialization. The online flow reboots automatically after
successful completion.

The one-line command above downloads the script to a file before running Bash,
preserving the interactive terminal. Its `v7.7.0` URL is the intended release URL;
this candidate remains pending the [final release receipt](docs/releases/7.7.0/verification.md).

MytelDesk is served at `/MytellDesk/`. **Panel account** uses authorized panel
credentials; the independent Desk administrator record is root-only at
`/etc/myteldesk/initial-admin.txt`. Configure extensions, trunks, trusted TLS and
recording policy for the intended use.

The separate owner-lab ISO remasters the original vendor ISO, retaining its
native firstboot/password flow. Its native **Software Selection** screen offers
**Asterisk 16/18/20**, with **20 as the default**. The ISO binary is
not uploaded to GitHub. Upstream technical package/service/database identifiers
remain intact. See the [English installation guide](docs/INSTALL.en.md) for both paths,
network policy and current acceptance limits. Older release records cover their
own versions only.
