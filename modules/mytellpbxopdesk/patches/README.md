# OpDesk فارسی‌سازی — وصله‌های MyTellPBX

این پوشه وصله‌های فارسی‌سازی میز کار اپراتور OpDesk را نگه می‌دارد.
سورس OpDesk جدا و با شناسهٔ قفل‌شده (`52b95e47`) روی سرور در `/opt/opdesk`
قرار دارد (تصمیم D2: جداسازی بسته‌بندی و پروانه). این وصله‌ها فقط
تغییرات پروژهٔ مای‌تل را بازتولید می‌کنند.

## ترتیب اعمال روی نصب تازهٔ OpDesk

```bash
cd /opt/opdesk/frontend/src/i18n/locales/fa
cp translation.json translation.json.orig
# فایل fa-translation.json همین پوشه را جایگزین کنید:
cp <this-dir>/fa-translation.json translation.json

python3 <this-dir>/patch-fa-enable.py    # fa پیش‌فرض + فهرست زبان‌ها
python3 <this-dir>/patch-fa-notif.py     # اعلان‌های وب‌ساکت فارسی

cd /opt/opdesk/frontend
npx vite build --base=/opdesk/           # نکته: پیشوند /opdesk/ الزامی است
```

## محتوای وصله‌ها

| فایل | کار |
|------|-----|
| `fa-translation.json` | ترجمهٔ کامل فارسی (۲۱۰۵ کلید؛ همهٔ کلیدهای انگلیسی + کلیدهای افزودهٔ رابط) |
| `patch-fa-enable.py` | افزودن `fa` به زبان‌های پشتیبانی‌شده و پیش‌فرض‌کردن آن |
| `patch-fa-notif.py` | فارسی‌کردن دو اعلان هاردکد وب‌ساکت |

## نکته‌های استقرار

- ساخت رابط حتماً با `--base=/opdesk/` انجام شود؛ بدون آن مسیر
  داره‌ها مطلق می‌شود و صفحه خالی می‌ماند.
- پس از ساخت، سرویس پس‌زمینه نیازی به ری‌استارت ندارد (dist مستقیم
  سرو می‌شود)؛ فقط کش مرورگر (Ctrl+Shift+R).
- پراکسی وب‌ساکت سِس در آپاچی: `ProxyPass /sip-ws ws://127.0.0.1:8088/ws`
- اگر نام‌های کاربری فارسی در پایگاه‌داده با کاراکترهای به‌هم‌ریخته
  ذخیره شدند (دوکدگذاری یو‌تی‌ف-۸)، با
  `CONVERT(CAST(CONVERT(name USING latin1) AS BINARY) USING utf8mb4)` درست می‌شوند.
