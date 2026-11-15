<div dir="rtl">

# MyTellPBX — سامانهٔ کامل مرکز تماس با برند مای‌تل

نصب مرحله‌ای مرکز تماس روی **راکی لینوکس ۸٫۱۰**: موتور تلفنی استریسک ۲۰،
چارچوب ماژول‌ها (داخلی، صف، ضبط تماس، گزارش‌ها، فکس، …) و لایهٔ کامل
قالب و برند مای‌تل — پنل فارسی راست‌چین با حالت روشن و تاریک، برند کامل
کنسول مدیریتی و زبان فارسی. نسخهٔ **۷٫۶٫۱** میز کار MytelDesk را همراه با
نصب خودکار تحلیل گفتار VAD نیز راه‌اندازی می‌کند.

## نصب با یک خط

روی سرور تازهٔ راکی ۸٫۱۰ با دسترسی ریشه:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh https://github.com/DashSaman/MyTellPBX/releases/download/v7.6.1/install-mytellpbx.sh && bash install-mytellpbx.sh
```

<div dir="rtl">

پس از پایان نصب، نشانی پنل و مسیر فایل رمزها (`/root/mytelpbx-credentials.txt`)
نمایش داده می‌شود. راهنمای کامل فارسی: [docs/INSTALL.fa.md](docs/INSTALL.fa.md)

**این نصاب برای سیستم خام است.** آن را برای به‌روزرسانی سیستم‌عامل یا جایگزینی
نصب فعلی مرکز تلفن اجرا نکنید. ادامهٔ نصب فقط با همان نسخه و هش محتوای شناخته‌شده
انجام می‌شود؛ وضعیت قدیمی یا ناشناخته متوقف می‌شود و رمزها بازنشانی نمی‌شوند.

پس از نصب، میز کار در `/MytellDesk/` قرار دارد. گزینهٔ **حساب پنل** از همان
حساب مجاز پنل استفاده می‌کند. مدیر محلی مستقل میز کار رمز تصادفی جداگانه دارد:
`/etc/myteldesk/initial-admin.txt`، فقط برای root. رمز این حساب با رمز پنل مشترک نیست.

## قابلیت‌ها

- نصب مرحله‌ای تکرارپذیر؛ ادامهٔ همان نسخه پس از قطعی با حفظ رمزها
- فقط دو ورودی مخفی برای رمز پنل و پایگاه‌داده؛ Enter برای تولید تصادفی و حفظ رمزها در ادامهٔ نصب
- قالب پنل: فارسی راست‌چین، فونت وزیرمتن، حالت روشن/تاریک، داشبورد اتاق کنترل
- کنسول مدیریتی: پوستهٔ کامل + برند + زیرنویس «گزارش پیشرفته» + دی‌برند کامل
- رفع مشکل «اعمال پیکربندی» (Apply Config)
- کنسول فنی LTR، انتخاب‌های واضح، جست‌وجوی خوانا، تقویم شمسی و ناوبری واکنش‌گرا
- اصلاح گزارش خروجیِ آسترنیک نصب‌شده بر پایهٔ ترانک، مستقل از پیش‌شمارهٔ شماره‌گیری
- نصب نسخهٔ دقیق و بررسی‌شدهٔ [MytelDesk](https://github.com/DashSaman/MytelDesk)، با Python مستقل، مدل همراه و وابستگی‌های دارای هش برای VAD روی CPU
- بررسی واقعی مدل با `myteldesk doctor`؛ نصب موتور، سیاست ضبط تماس را خودکار فعال یا تغییر نمی‌دهد
- فایروال روشن می‌ماند؛ فقط پورت‌های لازم باز می‌شوند
- مستندات کامل دو زبانه + شفافیت کامل نرم‌افزارهای پایه (THIRD_PARTY_NOTICES.md)

## مستندات

- راهنمای نصب فارسی: [docs/INSTALL.fa.md](docs/INSTALL.fa.md)
- Installation guide (English): [docs/INSTALL.en.md](docs/INSTALL.en.md)
- سند تست: [docs/TESTING.md](docs/TESTING.md)
- یادداشت انتشار نسخه: [RELEASE_NOTES_V7_6_0_FA.md](RELEASE_NOTES_V7_6_0_FA.md)
- گزارش آزمون‌های نسخهٔ ۷٫۶٫۰: [docs/releases/7.6.0/verification.md](docs/releases/7.6.0/verification.md)
- تشخیص خروجی آسترنیک و دامنهٔ نصب: [docs/ASTERNIC_DIRECTION_FA.md](docs/ASTERNIC_DIRECTION_FA.md)

## هشدارهای امنیتی مهم

سلبینوکس غیرفعال می‌شود و پی‌اچ‌پی ۷٫۴ (الزام چارچوب) پایان پشتیبانی
بالادستی دارد — جزئیات و توصیه‌ها در راهنمای نصب.

</div>

---

# MyTellPBX (English)

A complete MyTel-branded contact-center platform for **Rocky Linux 8.10**,
installed with one command: the Asterisk 20 telephony engine and framework
modules, plus the full Persian RTL MyTel theme layer — light/dark panel,
branded admin console, Persian language and complete debranding of the
upstream UI.

## What's inside

- `install-mytellpbx.sh` — the staged, resumable one-line installer with
  two hidden password inputs, optional generation and runtime self-checks
- `theme/` — the Persian RTL panel theme (source of truth)
- `admin-theme/` — admin-console skin, dark layer and debrand patchers
- `installer/` — package lists, repository template and golden payload
- `installer/install-myteldesk.py` — checksum-pinned Desk/CPU VAD integration;
  the separate product installer owns its service, credentials and rollback
- `scripts/` — bundle builder and lab helpers
- `docs/` — bilingual install guides and the verification record

## Install

See the quick start above, or the full guide:
[docs/INSTALL.en.md](docs/INSTALL.en.md).

The full PBX installer targets a **fresh Rocky8.10/Asterisk20 system**. It is not
an OS/PBX updater. Resume requires the same release and bundle hash; unknown or
older installation state fails closed. Existing Desk users/secrets are preserved,
and an independently upgraded Desk is never silently downgraded.

MytelDesk is served at `/MytellDesk/`. Its native **Panel account** sign-in uses
authorized panel credentials; no shared administrator password or implicit SSO is
created. The separate local Desk administrator record is root-only at
`/etc/myteldesk/initial-admin.txt`. The [standalone Desk distribution](https://github.com/DashSaman/MytelDesk)
supports existing Issabel/Asterisk16/18/20 installations; that does not broaden the
full PBX installer's fresh-OS platform contract.

Release artifacts retain corresponding source and notices. MytelDesk is a
separately installed GPLv3 product; this repository retains its own license.
See the version-specific verification record for actual tests and limitations;
service health and VAD readiness alone do not prove a SIP/media path.

## Security disclosures

SELinux is disabled (framework requirement) and PHP 7.4 is past upstream
EOL (framework requirement) — read the install guide before exposing the
panel. Third-party components are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
