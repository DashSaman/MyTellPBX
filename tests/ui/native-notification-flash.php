<?php
// Pass the installed native helper and component files from a disposable fixture.
require $argv[1];
require $argv[2];

function check_flash($condition, $message) {
    if (!$condition) {
        file_put_contents('php://stderr', $message . PHP_EOL);
        exit(1);
    }
}

$flash = [
    'msg' => base64_encode('Fixture extension deleted'),
    'msgtype' => 'warning',
    'msgtstamp' => time(),
    'msgtimer' => 6000,
    'unrelated' => 'keep',
];
$_SESSION = $flash;
$_SERVER['HTTP_X_UP_MODE'] = 'root';
check_flash(js_display_confirmation_toasts() === '', 'A fragment must defer the flash to a full render');
check_flash($_SESSION === $flash, 'A fragment must retain the pending flash');

unset($_SERVER['HTTP_X_UP_MODE']);
$component = new component('fixture');
check_flash($component->generateconfigpage('') === '', 'An empty component must have no form markup');
check_flash($_SESSION === $flash, 'The native component must retain the flash when it discards its markup');
$component->_guielems_top = [];
$rendered = $component->generateconfigpage('');
check_flash(
    strpos($rendered, 'sweet_toast(\'warning\',"Fixture extension deleted",6000)') !== false,
    'A full render must emit the native notice with the original text, severity and timeout'
);
check_flash($_SESSION === ['unrelated' => 'keep'], 'The first render must consume only confirmation keys');
check_flash(js_display_confirmation_toasts() === '', 'A subsequent render must not replay the notice');

$flash['msgtstamp'] = time() - 60;
$_SESSION = $flash;
check_flash(js_display_confirmation_toasts() === '', 'An expired confirmation must not be displayed');
check_flash($_SESSION === ['unrelated' => 'keep'], 'A full render must discard the expired confirmation');

echo "Native session flash is consumed exactly once.\n";
