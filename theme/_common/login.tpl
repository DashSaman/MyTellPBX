<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="MyTellPBX Admin" />
    <title>MyTellPBX - {$PAGE_NAME}</title>

    <link rel="icon" type="image/svg+xml" href="{$WEBPATH}themes/{$THEMENAME}/images/favicon.svg" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/fonts.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/tabler.min.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/icons/tabler-icons.min.css" />
    <link rel="stylesheet" href="{$WEBPATH}themes/{$THEMENAME}/css/shell.css" />

    {$HEADER_LIBS_JQUERY}
</head>
<body class="d-flex flex-column mytell-login-body">

<script type="text/javascript">
var baseurl = '';
</script>

<div class="page">
    <div class="page-center">
        <div class="container container-tight py-4">
            <div class="text-center mb-4">
                <a href="." class="navbar-brand navbar-brand-autodark" style="display:inline-flex;align-items:center;gap:.6rem;">
                    <img src="{$WEBPATH}themes/{$THEMENAME}/images/logo.svg" height="40" alt="MyTellPBX" />
                    <span style="font-size:1.4rem;font-weight:700;">MyTellPBX</span>
                </a>
            </div>
            <div class="card card-md">
                <div class="card-body">
                    <h2 class="h2 text-center mb-4">{$PAGE_NAME}</h2>
{if !empty($LOGIN_INCORRECT)}
                    <div class="alert alert-danger" role="alert">
                        <div class="d-flex">
                            <div><i class="ti ti-alert-triangle icon alert-icon"></i></div>
                            <div>{$LOGIN_INCORRECT}</div>
                        </div>
                    </div>
{/if}
                    <form method="post" action="" autocomplete="off">
                        <div class="mb-3">
                            <label class="form-label" for="input_user">{$USERNAME}</label>
                            <input type="text" class="form-control" name="input_user" id="input_user" placeholder="{$USERNAME}" autocomplete="off" />
                        </div>
                        <div class="mb-3">
                            <label class="form-label" for="input_pass">{$PASSWORD}</label>
                            <input type="password" class="form-control" name="input_pass" id="input_pass" placeholder="{$PASSWORD}" autocomplete="off" />
                        </div>
                        <div class="form-footer">
                            <button type="submit" class="btn btn-primary w-100" name="submit_login">
                                <i class="ti ti-login me-1"></i>
                                {$SUBMIT}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            <div class="text-center text-secondary mt-3">
                <a href="https://github.com/DashSaman/MyTellPBX" style="color: inherit; text-decoration: none;" target='_blank'><strong>MyTellPBX</strong></a>
                {$ISSABEL_LICENSED} <a href="http://www.opensource.org/licenses/gpl-license.php" style="color: inherit; text-decoration: none;" target='_blank'>GPL</a>. 2006 - {$currentyear}.
            </div>
        </div>
    </div>
</div>

</body>
</html>
