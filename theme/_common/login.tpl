<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
	<meta charset="utf-8">
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
	<meta name="viewport" content="width=device-width, initial-scale=1.0" />
	<meta name="description" content="سامانه مدیریت مرکز تماس" />
	<title>مای‌تل | سامانه مدیریت مرکز تماس</title>
	<link rel="shortcut icon" href="{$WEBPATH}themes/{$THEMENAME}/images/favicon.png" />
	<link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/fonts.css?v=110">
	<link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/tokens.css?v=110">
	<link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/login.css?v=110">
	{$HEADER_LIBS_JQUERY}
</head>
<body class="mt-login-body">

<div class="mt-login-stage">

	<div class="mt-login-brandpane">
		<div class="mt-login-brandpane-inner">
			<img class="mt-login-emblem" src="{$WEBPATH}themes/{$THEMENAME}/images/mytel-emblem.svg" alt="MyTel" />
			<h1 class="mt-login-brandname">مای‌تل</h1>
			<p class="mt-login-tagline">سامانه مدیریت مرکز تماس</p>
			<div class="mt-login-waves" aria-hidden="true">
				<span></span><span></span><span></span><span></span><span></span>
				<span></span><span></span><span></span><span></span><span></span>
			</div>
		</div>
	</div>

	<div class="mt-login-panel">
		<div class="mt-login-card">

			<div class="mt-login-cardhead">
				<img class="mt-login-emblem-sm" src="{$WEBPATH}themes/{$THEMENAME}/images/mytel-emblem.svg" alt="" />
				<h2>{$PAGE_NAME}</h2>
			</div>

{if !empty({$LOGIN_INCORRECT})}
			<div class="mt-login-error"><i class="fa fa-warning"></i> {$LOGIN_INCORRECT}</div>
{/if}

			<form method="post" class="mt-login-form" id="mt-login-form">

				<div class="mt-field">
					<label for="input_user">{$USERNAME}</label>
					<div class="mt-inputwrap">
						<i class="fa fa-user"></i>
						<input type="text" class="mt-input" name="input_user" id="input_user" placeholder="{$USERNAME}" autocomplete="off" autofocus />
					</div>
				</div>

				<div class="mt-field">
					<label for="input_pass">{$PASSWORD}</label>
					<div class="mt-inputwrap">
						<i class="fa fa-key"></i>
						<input type="password" class="mt-input" name="input_pass" id="input_pass" placeholder="{$PASSWORD}" autocomplete="off" />
					</div>
				</div>

				<button type="submit" class="mt-login-btn" name="submit_login">
					{$SUBMIT}
					<i class="fa fa-angle-left"></i>
				</button>

			</form>

			<div class="mt-login-foot">
				<a href="https://mytel.one" target="_blank" rel="noopener" class="mt-foot-link">مای‌تل</a>
				<span class="mt-dot">&bull;</span>
				<span dir="rtl">&copy; ۲۰۰۵–۲۰۲۷</span>
			</div>

		</div>
	</div>

</div>

<script>
(function () {
	var f = document.getElementById('mt-login-form');
	if (!f) return;
	f.addEventListener('submit', function (e) {
		var u = document.getElementById('input_user');
		var p = document.getElementById('input_pass');
		if (!u.value.trim() || !p.value.trim()) { e.preventDefault(); }
		if (!u.value.trim()) { u.classList.add('mt-invalid'); u.focus(); } else { u.classList.remove('mt-invalid'); }
		if (!p.value.trim()) { p.classList.add('mt-invalid'); }
	});
})();
</script>

</body>
</html>
