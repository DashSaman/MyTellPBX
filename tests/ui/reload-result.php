<?php
// Executes only the extracted function in a namespace with a mocked exec().
// No PBX bootstrap, database, AMI connection or shell command is executed.
namespace ApplyRepairTest;
function __($text) { return $text; }
function exec($command, &$output, &$status) { global $exec_status; $output = array('fixture'); $status = $exec_status; }
class issabelpbx_conf {
    public static function &create() { static $value; if (!$value) $value = new self(); return $value; }
    public function get_conf_setting($key, $passthru) { return $key === 'AMPBIN' ? '/never-execute' : false; }
}
class notifications {
    public static function &create($db) { static $value; if (!$value) $value = new self(); return $value; }
    public function __call($name, $args) {}
}
class DB {
    public $queries = array();
    public static function IsError($result) { return false; }
    public function query($sql) { $this->queries[] = $sql; return true; }
}
class Manager {
    public $response;
    public function __construct($response) { $this->response = $response; }
    public function Reload() { return $this->response; }
}
$source = file_get_contents($argv[1]);
$start = strpos($source, 'function do_reload(');
$end = strpos($source, '// draw list for users', $start);
if ($start === false || $end === false) throw new \RuntimeException('Fixture extraction anchor missing');
eval('namespace ApplyRepairTest; ' . substr($source, $start, $end - $start));
$version = '18.26'; $amp_conf = array(); $asterisk_conf = array();
$cases = array(
    array('AMI error retains pending changes', array('Response'=>'Error','Message'=>'rejected'), 0, false),
    array('missing AMI response is not success', null, 0, false),
    array('malformed AMI response is not success', array('Message'=>'unknown'), 0, false),
    array('AMI success clears pending changes', array('Response'=>'Success'), 0, true),
    array('retrieve failure does not clear pending changes', array('Response'=>'Success'), 1, false),
);
$failures=0;
foreach ($cases as $case) {
    list($name, $response, $exec_status, $expected) = $case;
    $db = new DB(); $astman = new Manager($response);
    $result = do_reload();
    $pass = $result['status'] === $expected && count($db->queries) === ($expected ? 1 : 0);
    echo ($pass ? 'PASS ' : 'FAIL ') . $name . "\n";
    if (!$pass) $failures++;
}
exit($failures ? 1 : 0);
