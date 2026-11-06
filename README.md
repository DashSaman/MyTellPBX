<div dir="rtl">

# MyTellPBX — سامانهٔ کامل مرکز تماس با برند مای‌تل

نصب یک‌خطی کل مرکز تماس روی **راکیمی لینوکس ۸٫۱۰**: موتور تلفنی استریسک ۲۰،
چارچوب ماژول‌ها (داخلی، صف، ضبط تماس، گزارش‌ها، فکس، …) و لایهٔ کامل
قالب و برند مای‌تل — پنل فارسی راست‌چین با حالت روشن و تاریک، برند کامل
کنسول مدیریتی، زبان فارسی و بدون هیچ نام برند بالادستی در رابط کاربری.

## نصب با یک خط

روی سرور تازهٔ راکی ۸٫۱۰ با دسترسی ریشه:

</div>

```bash
curl -fsSL -o install-mytellpbx.sh \
  https://github.com/DashSaman/MyTellPBX/releases/download/v7.5.1/install-mytellpbx.sh
bash install-mytellpbx.sh
```

<div dir="rtl">

پس از پایان نصب، نشانی پنل و مسیر فایل رمزها (`/root/mytelpbx-credentials.txt`)
نمایش داده می‌شود. راهنمای کامل فارسی: [docs/INSTALL.fa.md](docs/INSTALL.fa.md)

## قابلیت‌ها

- نصب مرحله‌ای تکرارپذیر؛ ادامهٔ خودکار پس از قطعی و بدون دست‌زدن به رمزها
- رمزهای تصادفی یکتا برای پنل و پایگاه‌داده در فایل فقط‌روت
- قالب پنل: فارسی راست‌چین، فونت وزیرمتن، حالت روشن/تاریک، داشبورد اتاق کنترل
- کنسول مدیریتی: پوستهٔ کامل + برند + زیرنویس «گزارش پیشرفته» + دی‌برند کامل
- رفع مشکل «اعمال پیکربندی» (Apply Config)
- فایروال روشن می‌ماند؛ فقط پورت‌های لازم باز می‌شوند
- مستندات کامل دو زبانه + شفافیت کامل نرم‌افزارهای پایه (THIRD_PARTY_NOTICES.md)

## مستندات

- راهنمای نصب فارسی: [docs/INSTALL.fa.md](docs/INSTALL.fa.md)
- Installation guide (English): [docs/INSTALL.en.md](docs/INSTALL.en.md)
- سند تست: [docs/TESTING.md](docs/TESTING.md)
- یادداشت انتشار نسخه: [RELEASE_NOTES_V7_4_0_FA.md](RELEASE_NOTES_V7_4_0_FA.md)

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
  generated credentials and self-checks
- `theme/` — the Persian RTL panel theme (source of truth)
- `admin-theme/` — admin-console skin, dark layer and debrand patchers
- `installer/` — package lists, repository template and golden payload
- `scripts/` — bundle builder and lab helpers
- `docs/` — bilingual install guides and the verification record

## Install

See the quick start above, or the full guide:
[docs/INSTALL.en.md](docs/INSTALL.en.md).

## Security disclosures

SELinux is disabled (framework requirement) and PHP 7.4 is past upstream
EOL (framework requirement) — read the install guide before exposing the
panel. Third-party components are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
