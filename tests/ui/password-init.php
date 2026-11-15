<?php
// Actual transport wrapper + owned fake vendor, no native tool/database/service.
$source = file_get_contents($argv[1]);
$temporary = sys_get_temp_dir() . '/mytell-password-wrapper-' . getmypid(); mkdir($temporary, 0700);
$vendor = $temporary . '/vendor.php'; $wrapper = $temporary . '/wrapper.php';
$fake = <<<'PHP'
#!/usr/bin/php
<?php
echo json_encode(array('argv'=>$argv,'server_argv'=>$_SERVER['argv'],'argc'=>$argc,
    'cmdline'=>file_get_contents('/proc/self/cmdline')));
exit(getenv('FIXTURE_EXIT') ? (int)getenv('FIXTURE_EXIT') : 0);
PHP;
file_put_contents($vendor, $fake);
$count = 0;
$modified = str_replace("'/usr/bin/issabel-admin-passwords'", var_export($vendor, true), $source, $count);
if ($count !== 1) { fwrite(STDERR, "Fixed vendor target anchor missing\n"); exit(1); }
file_put_contents($wrapper, $modified);
$tests = array();
function fixture_run($wrapper, $input, $extra = array()) {
    $pipes = array(); $environment = array_merge($_ENV, $extra);
    $process = proc_open(array(PHP_BINARY, $wrapper), array(0=>array('pipe','r'),1=>array('pipe','w'),2=>array('pipe','w')), $pipes, null, $environment);
    fwrite($pipes[0], $input); fclose($pipes[0]); $output=stream_get_contents($pipes[1]); fclose($pipes[1]);
    $error=stream_get_contents($pipes[2]); fclose($pipes[2]); $status=proc_close($process);
    return array($status,$output,$error);
}
try {
    $input = "FixtureDb_123!\nFixture Admin.456=\n";
    $result = fixture_run($wrapper, $input); $data=json_decode($result[1], true);
    $tests['vendor accepts equivalent global arguments'] = $result[0] === 0 && is_array($data)
        && $data['argv'] === array($vendor,'--cli','init','FixtureDb_123!','Fixture Admin.456=');
    $tests['server argv and argc match vendor expectations'] = is_array($data) && $data['server_argv'] === $data['argv'] && $data['argc'] === 5;
    $tests['outer process arguments contain neither secret'] = is_array($data) && strpos($data['cmdline'], 'FixtureDb_123!') === false && strpos($data['cmdline'], 'Fixture Admin.456=') === false;
    $failed = fixture_run($wrapper, $input, array('FIXTURE_EXIT'=>'7'));
    $tests['vendor failure exit propagates unchanged'] = $failed[0] === 7;
    foreach (array("only-one-line\n", "\npassword\n", "one\ntwo\nextra\n", "one'bad\ntwo\n") as $invalid) {
        $result = fixture_run($wrapper, $invalid);
        $tests['invalid stdin rejected ' . count($tests)] = $result[0] !== 0 && strpos($result[1], 'cmdline') === false && strpos($result[2], $invalid) === false;
    }
} finally { unlink($vendor); unlink($wrapper); rmdir($temporary); }
foreach ($tests as $name=>$pass) echo ($pass?'PASS ':'FAIL ') . $name . "\n";
exit(in_array(false, $tests, true) ? 1 : 0);
