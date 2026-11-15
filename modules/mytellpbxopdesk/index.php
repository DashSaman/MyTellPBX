<?php
/** MyTellPBX operator workspace launcher; GPL-2.0. */
require_once __DIR__ . '/launcher-access.php';
session_name('issabelSession');
session_start();
$username = isset($_SESSION['issabel_user']) ? $_SESSION['issabel_user'] : null;
// Release the panel's session lock before querying ACL or navigating to Desk.
session_write_close();
$status = mytellDeskLauncherStatus($username, function ($identity) {
    return mytellDeskAclAllows(mytellDeskOpenAcl(), $identity);
});
header('Cache-Control: no-store');
header('Referrer-Policy: same-origin');
if ($status === 303) {
    // Existing Desk sessions continue; first sign-in uses its Panel-account flow.
    // Never impersonate/reset the local administrator or carry a token in a URL.
    header('Location: /MytellDesk/', true, 303);
    exit;
}
http_response_code($status);
$messages = array(
    401 => array('ابتدا وارد پنل شوید', 'برای دسترسی به میز کار اپراتور، با حساب پنل وارد شوید.'),
    403 => array('دسترسی محدود است', 'ورود به میز کار از این صفحه برای مدیران مرکز تلفن مجاز است.'),
    503 => array('بررسی دسترسی ممکن نشد', 'ارتباط با اطلاعات حساب پنل برقرار نشد. کمی بعد دوباره تلاش کنید.'),
);
$message = $messages[$status];
?>
<!doctype html>
<html lang="fa" dir="rtl" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>میز کار اپراتور | مای‌تل</title>
<link rel="stylesheet" href="/themes/mytel/css/fonts.css">
<script>try{if(localStorage.getItem('mt-theme')==='dark')document.documentElement.dataset.theme='dark';}catch(e){}</script>
<style>
:root{color-scheme:light;--bg:#f3f6fb;--surface:#fff;--text:#14263e;--muted:#52647c;--border:#d6e1ef;--accent:#245bc9}
:root[data-theme=dark]{color-scheme:dark;--bg:#0c1625;--surface:#142337;--text:#e6edf7;--muted:#b1c2d9;--border:#344a66;--accent:#8db7ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:var(--bg);color:var(--text);font-family:Vazirmatn,Tahoma,sans-serif}
main{width:min(100%,520px);padding:clamp(24px,5vw,40px);border:1px solid var(--border);border-radius:16px;background:var(--surface)}
h1{font-size:1.35rem;line-height:1.6;margin:0 0 12px}p{font-size:1rem;line-height:1.9;color:var(--muted);margin:0 0 24px}
a{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:8px 18px;border:1px solid var(--accent);border-radius:9px;color:var(--accent);font-weight:700;text-decoration:none}
a:focus-visible{outline:3px solid var(--accent);outline-offset:4px}a:hover{text-decoration:underline}
</style>
</head>
<body><main aria-labelledby="status-title">
<h1 id="status-title"><?= htmlspecialchars($message[0], ENT_QUOTES, 'UTF-8') ?></h1>
<p role="status"><?= htmlspecialchars($message[1], ENT_QUOTES, 'UTF-8') ?></p>
<a href="/">بازگشت به پنل</a>
</main></body></html>
