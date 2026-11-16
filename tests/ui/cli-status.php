<?php
// Extract only dialog_infobox into two private namespaces. Neither the full
// vendor program nor a real system(), TTY, database or password API is executed.
$original = file_get_contents(__DIR__ . '/../fixtures/issabel-cli-status-function.php');
$candidate = file_get_contents($argv[1]);
function fixture_function($source) {
    $pattern = '/function dialog_infobox\(\$backtitle, \$msgbox, \$height, \$width\)\r?\n\{\r?\n.*?\r?\n\}/s';
    if (preg_match_all($pattern, $source, $matches) !== 1) throw new RuntimeException('Expected one exact function boundary');
    return $matches[0][0];
}
$directory = sys_get_temp_dir() . '/mytell-cli-status-' . bin2hex(random_bytes(8));
if (!mkdir($directory, 0700)) throw new RuntimeException('Fixture directory unavailable');
$paths = array();
try {
    foreach (array('Original'=>$original, 'Candidate'=>$candidate) as $name=>$source) {
        $path = $directory . '/' . $name . '.php'; $paths[] = $path;
        $stub = '<?php namespace CliStatus' . $name . ';'
            . ' function system($command) { $GLOBALS["fixture_calls"][] = $command; return 17; }' . "\n";
        file_put_contents($path, $stub . fixture_function($source) . "\n");
        require $path;
    }
    function fixture_call($namespace, $arguments, $server = array()) {
        $GLOBALS['argv'] = $arguments; $_SERVER['argv'] = $server; $GLOBALS['fixture_calls'] = array();
        $result = call_user_func('\\CliStatus' . $namespace . '\\dialog_infobox',
            'Status', "Owned fixture's message\nsecond line", '7ignored', 11.8);
        return array($result, $GLOBALS['fixture_calls']);
    }
    $tests = array();
    $old = fixture_call('Original', array('program', '--cli', 'init'));
    $tests['original bug actually invokes dialog in CLI mode'] = count($old[1]) === 1;
    foreach (array(array('program', '--cli', 'init'), array('program', 'init', '--cli')) as $arguments) {
        $result = fixture_call('Candidate', $arguments);
        $tests['CLI suppresses status GUI ' . count($tests)] = $result === array(null, array());
    }
    foreach (array(array('program', '--init'), array('program', '--change'),
                   array('program', '--client'), array('program', '--CLI'), array('program')) as $arguments) {
        $before = fixture_call('Original', $arguments);
        $after = fixture_call('Candidate', $arguments, array('program', '--cli'));
        $tests['interactive command stays byte-identical ' . count($tests)] = count($after[1]) === 1 && $after === $before;
    }
    $before = fixture_call('Original', 'not-an-array');
    $after = fixture_call('Candidate', 'not-an-array');
    $tests['unexpected argv type preserves interactive behavior'] = $before === $after && count($after[1]) === 1;
    unset($GLOBALS['argv']); $GLOBALS['fixture_calls'] = array();
    \CliStatusCandidate\dialog_infobox('Status', 'Missing argv', 7, 11);
    $tests['missing argv does not suppress interactive status'] = count($GLOBALS['fixture_calls']) === 1;
} finally {
    foreach ($paths as $path) if (is_file($path)) unlink($path);
    rmdir($directory);
}
foreach ($tests as $name=>$pass) echo ($pass ? 'PASS ' : 'FAIL ') . $name . "\n";
exit(in_array(false, $tests, true) ? 1 : 0);
