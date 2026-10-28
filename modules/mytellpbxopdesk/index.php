<?php
/**
 * MyTellPBX OpDesk Bridge — پل احراز هویت بومی پنل ایزابل
 *
 * @license GPL-2.0 (MyTellPBX project)
 */
session_start();

$loggedIn = !empty($_SESSION['issabel_user']);
$token = '';
$error = '';

if ($loggedIn) {
    $envFile = '/etc/mytellpbx/opdesk.env';
    $bridgePw = '';
    if (is_readable($envFile)) {
        foreach (file($envFile, FILE_IGNORE_NEW_LINES) as $line) {
            if (preg_match('/^OPDESK_BRIDGE_PW=(.+)$/', $line, $m)) {
                $bridgePw = trim($m[1]);
                break;
            }
        }
    }
    if ($bridgePw !== '') {
        $ch = curl_init('http://127.0.0.1:8765/api/auth/login');
        $payload = json_encode(array('login' => 'admin', 'password' => $bridgePw));
        if ($payload !== false) {
            curl_setopt_array($ch, array(
                CURLOPT_POST => true,
                CURLOPT_POSTFIELDS => $payload,
                CURLOPT_HTTPHEADER => array('Content-Type: application/json'),
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT => 5,
            ));
            $resp = curl_exec($ch);
            $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);
            if ($code === 200 && is_string($resp) && $resp !== '') {
                $d = json_decode($resp, true);
                if (is_array($d) && !empty($d['access_token'])
                    && is_string($d['access_token'])
                    && preg_match('/^[A-Za-z0-9._-]+$/', $d['access_token'])) {
                    $token = $d['access_token'];
                }
            }
        }
    }
    if ($token === '') {
        $error = 'اتصال به میز کار اپراتور برقرار نشد؛ لطفاً سرویس را بررسی کنید.';
    }
}
?>
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>میز کار اپراتور | MyTellPBX</title>
<style>
body{font-family:Vazirmatn,Tahoma,sans-serif;background:#0B1526;color:#fff;
     display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#1a2332;padding:40px 60px;border-radius:16px;text-align:center}
h2{margin:0 0 12px;font-size:20px}
p{color:#8b95a5;font-size:14px;margin:6px 0}
a{color:#FF8A00;text-decoration:none;font-weight:700}
.spinner{display:inline-block;width:32px;height:32px;border:3px solid #2E3194;
         border-top-color:#FF8A00;border-radius:50%;animation:sp 1s linear infinite;margin:16px 0}
@keyframes sp{to{transform:rotate(360deg)}}
</style>
</head>
<body>
<div class="card">
<?php if (!$loggedIn): ?>
  <h2>🔑 لطفاً وارد پنل شوید</h2>
  <p>برای دسترسی به میز کار اپراتور ابتدا باید وارد پنل شوید.</p>
  <p><a href="/">ورود به پنل</a></p>
<?php elseif ($token !== ''): ?>
  <h2>🎧 در حال ورود به میز کار اپراتور…</h2>
  <div class="spinner"></div>
  <p>در حال انتقال امن…</p>
  <script>
  var t = <?= json_encode($token, JSON_HEX_APOS | JSON_HEX_QUOT) ?>;
  var u = '/opdesk/#t=' + encodeURIComponent(t);
  setTimeout(function(){ window.location.replace(u); }, 500);
  </script>
<?php else: ?>
  <h2>⚠️ <?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></h2>
  <p>سرویس میز کار اپراتور (mytellpbx-opdesk) باید فعال باشد.</p>
  <p><a href="/">بازگشت به پنل</a></p>
<?php endif; ?>
</div>
</body>
</html>
