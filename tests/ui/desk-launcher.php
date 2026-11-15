<?php
// Own disposable SQLite fixture only; no panel ACL/session or application data.
require $argv[1];
$tests = array(); $calls = 0;
$allow = function ($username) use (&$calls) { $calls++; return $username === 'admin'; };
$tests['anonymous is denied without an ACL lookup'] = mytellDeskLauncherStatus(null, $allow) === 401 && $calls === 0;
$tests['malformed session identity is denied'] = mytellDeskLauncherStatus(array('admin'), $allow) === 401 && $calls === 0;
$tests['administrator gets the fixed local redirect'] = mytellDeskLauncherStatus('admin', $allow) === 303 && $calls === 1;
$tests['nonadministrator cannot launch as admin'] = mytellDeskLauncherStatus('operator', $allow) === 403;
$tests['truthy nonboolean lookup does not grant access'] = mytellDeskLauncherStatus('admin', function () { return 'yes'; }) === 403;
$tests['ACL lookup failure is explicit and fail closed'] = mytellDeskLauncherStatus('admin', function () { throw new RuntimeException('fixture'); }) === 503;
$path = tempnam(sys_get_temp_dir(), 'mytell-desk-acl-');
try {
    $db = new PDO('sqlite:' . $path);
    $db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $db->exec('CREATE TABLE acl_user (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE acl_membership (id_user INTEGER,id_group INTEGER)');
    $statement = $db->prepare('INSERT INTO acl_user(id,name) VALUES (?,?)');
    $statement->execute(array(1, 'admin')); $statement->execute(array(2, "odd'user")); $statement->execute(array(3, 'operator'));
    $db->exec('INSERT INTO acl_membership VALUES (1,1),(2,1),(3,2)'); $db = null;
    $before = hash_file('sha256', $path);
    $read = mytellDeskOpenAcl($path);
    $tests['native administrator group membership is recognized'] = mytellDeskAclAllows($read, 'admin');
    $tests['quoted usernames are parameters, not SQL'] = mytellDeskAclAllows($read, "odd'user");
    $tests['other ACL groups are not administrator'] = !mytellDeskAclAllows($read, 'operator');
    $tests['SQL-looking identity cannot bypass membership'] = !mytellDeskAclAllows($read, "' OR 1=1 --");
    $blocked = false;
    try { $read->exec("INSERT INTO acl_user(name) VALUES ('must not persist')"); }
    catch (Exception $error) { $blocked = true; }
    $read = null;
    $tests['ACL connection cannot write and original bytes remain unchanged'] = $blocked && hash_file('sha256', $path) === $before;
    $missing = false;
    try { mytellDeskOpenAcl($path . '.absent'); }
    catch (Exception $error) { $missing = true; }
    $tests['missing ACL is not created as an empty database'] = $missing && !file_exists($path . '.absent');
} finally { if (is_file($path)) unlink($path); }
$source = file_get_contents(dirname($argv[1]) . '/index.php');
$tests['launcher never reads a shared administrator secret'] = strpos($source, 'opdesk-bridge.pw') === false && strpos($source, 'OPDESK_BRIDGE_PW') === false;
$tests['launcher never posts an implicit shared administrator login'] = strpos($source, 'curl_init') === false && strpos($source, 'access_token') === false;
foreach ($tests as $name => $pass) echo ($pass ? 'PASS ' : 'FAIL ') . $name . "\n";
exit(in_array(false, $tests, true) ? 1 : 0);
