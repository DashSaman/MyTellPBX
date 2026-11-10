<?php
// Isolated lock files and callbacks only; never calls do_reload or Asterisk.
require $argv[1];
session_id('mytell-apply-fixture-' . getmypid());
session_start();
$_SESSION['fixture'] = 'retained';
$path = sys_get_temp_dir() . '/mytell-lock-test-' . getmypid();
$tests = array();
class ApplyPermissionFixture {
    private $allowed;
    function __construct($allowed) { $this->allowed = $allowed; }
    function checkSection($section) { return $section === '99' && $this->allowed; }
}
$server = array('HTTPS'=>'on', 'HTTP_HOST'=>'pbx.example', 'HTTP_ORIGIN'=>'https://pbx.example', 'HTTP_X_REQUESTED_WITH'=>'XMLHttpRequest');
$tests['authorized same-origin XHR accepted'] = mytell_apply_authorized(new ApplyPermissionFixture(true), $server);
$tests['missing Apply privilege rejected'] = !mytell_apply_authorized(new ApplyPermissionFixture(false), $server);
$tests['cross-origin Apply rejected'] = !mytell_apply_authorized(new ApplyPermissionFixture(true), array_merge($server, array('HTTP_ORIGIN'=>'https://other.example')));
$tests['simple form Apply rejected'] = !mytell_apply_authorized(new ApplyPermissionFixture(true), array_diff_key($server, array('HTTP_X_REQUESTED_WITH'=>true)));
$tests['missing user rejected'] = !mytell_apply_authorized(null, $server);
try {
    $called = 0;
    $result = mytell_guarded_reload(function () use (&$called, &$tests) {
        $called++;
        $tests['session released during operation'] = session_status() !== PHP_SESSION_ACTIVE;
        $tests['session data retained'] = $_SESSION['fixture'] === 'retained';
        return array('status'=>true);
    }, $path);
    $tests['successful callback runs once'] = $called === 1 && $result['status'] === true;
    $owner = fopen($path, 'c'); flock($owner, LOCK_EX);
    $result = mytell_guarded_reload(function () use (&$called) { $called++; }, $path);
    $tests['overlapping request rejected without execution'] = $called === 1 && $result['http_status'] === 409;
    flock($owner, LOCK_UN); fclose($owner);
    $result = mytell_guarded_reload(function () { throw new RuntimeException('fixture'); }, $path);
    $tests['exception yields uncertain HTTP error'] = $result['http_status'] === 500;
    $result = mytell_guarded_reload(function () { return array('status'=>true); }, $path);
    $tests['lock released after exception'] = $result['status'] === true;
    $result = mytell_guarded_reload(function () use (&$called) { $called++; }, $path . '/missing');
    $tests['unavailable lock fails without execution'] = $result['http_status'] === 503 && $called === 1;
} finally {
    if (file_exists($path)) unlink($path);
    session_start(); session_destroy();
}
foreach ($tests as $name=>$pass) echo ($pass ? 'PASS ' : 'FAIL ') . $name . "\n";
exit(in_array(false, $tests, true) ? 1 : 0);
