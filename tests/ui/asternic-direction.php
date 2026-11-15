<?php
// Synthetic fixtures only. Native mode refuses every non-fixture database.
require $argv[1];
$trunks = array(
    array('tech'=>'sip','channelid'=>'carrier-main'),
    array('tech'=>'pjsip','channelid'=>'pj-main'),
    array('tech'=>'iax2','channelid'=>'iax-main'),
    array('tech'=>'dahdi','channelid'=>'g0'),
    array('tech'=>'dahdi','channelid'=>'12'),
    array('tech'=>'custom','channelid'=>'Local/$OUTNUM$@external-carrier/n'),
    array('tech'=>'sip','channelid'=>"literal_%'peer"),
    array('tech'=>'sip','channelid'=>'100'),
);
$devices = array_map(function ($dial) { return array('dial'=>$dial); }, array(
    'SIP/100','SIP/101','SIP/carrier-main-extra','PJSIP/200','IAX2/300','DAHDI/1','Local/400@from-internal'
));
$predicates = asternic_mytel_direction_predicates($trunks, $devices);
$tests = array();
function verify_direction($name, $pass) { global $tests; $tests[$name] = (bool)$pass; }
verify_direction('four explicit direction predicates', array_keys($predicates) === array('outgoing','incoming','internal','external'));
verify_direction('no destination-number prefix or from-internal guess', strpos(implode(' ', $predicates), 'dst LIKE') === false && strpos(implode(' ', $predicates), 'dcontext') === false);
verify_direction('metadata quote is encoded instead of entering SQL text', strpos(implode(' ', $predicates), "literal_%'peer") === false);
foreach (array(array(array('tech'=>'unknown','channelid'=>'x')), array(array('tech'=>'sip','channelid'=>'')), array(array('tech'=>'sip','channelid'=>"bad\npeer")), array(array('tech'=>'custom','channelid'=>'Local/${UNRECOGNIZED}@x'))) as $invalid) {
    $rejected = false;
    try { asternic_mytel_direction_predicates($invalid, $devices); } catch (InvalidArgumentException $error) { $rejected = true; }
    verify_direction('invalid catalog fails explicitly ' . count($tests), $rejected);
}
class DirectionFixtureDB {
    public $calls = 0;
    public function getAll($query, $mode) { global $trunks, $devices; $this->calls++; return strpos($query, 'asterisk.trunks') !== false ? $trunks : $devices; }
}
if (!defined('DB_FETCHMODE_ASSOC')) define('DB_FETCHMODE_ASSOC', 2);
$fake = new DirectionFixtureDB();
verify_direction('runtime catalog produces same outgoing predicate', asternic_mytel_direction_sql($fake, 'outgoing') === $predicates['outgoing']);
asternic_mytel_direction_sql($fake, 'incoming');
verify_direction('metadata is reused only within the request object', $fake->calls === 2);
$invalidDirection = false;
try { asternic_mytel_direction_sql($fake, 'outgoing OR 1=1'); } catch (InvalidArgumentException $error) { $invalidDirection = true; }
verify_direction('unknown direction rejected', $invalidDirection);

$rows = array();
function direction_row($id, $changes, $out = false, $in = false, $internal = false) {
    global $rows;
    $rows[] = array('row'=>array_merge(array('id'=>$id,'channel'=>'SIP/100-00000001','dstchannel'=>'','lastapp'=>'Hangup','lastdata'=>'','src'=>'fixture-rewritten-cid','dst'=>'12345','dcontext'=>'from-internal','disposition'=>'ANSWERED'), $changes), 'expected'=>array('outgoing'=>$out,'incoming'=>$in,'internal'=>$internal,'external'=>$out || $in));
}
foreach (array('9'=>'912345','7'=>'712345','none'=>'12345','arbitrary'=>'512345','e164'=>'+12025550100') as $name=>$destination)
    direction_row('prefix-'.$name, array('dst'=>$destination,'dstchannel'=>'SIP/carrier-main-00000002'), true);
foreach (array('ANSWERED','BUSY','NO ANSWER','FAILED') as $status)
    direction_row('blank-'.$status, array('lastapp'=>'Dial','lastdata'=>'SIP/carrier-main/12345,20,T','disposition'=>$status), true);
foreach (array(
    'pjsip-endpoint'=>'PJSIP/pj-main/12345,20',
    'pjsip-at'=>'PJSIP/+12025550100@pj-main,20',
    'sip-at'=>'SIP/12345@carrier-main,20',
    'iax'=>'IAX2/iax-main/12345,20',
    'iax-at'=>'IAX2/fixture-user@iax-main/12345,20',
    'dahdi-group'=>'DAHDI/g0/12345,20',
    'custom-local'=>'Local/12345@external-carrier/n,20',
    'multiple-targets'=>'SIP/101&SIP/carrier-main/12345,20',
) as $name=>$target) direction_row($name, array('lastapp'=>'Dial','lastdata'=>$target,'disposition'=>'FAILED'), true);
foreach (array('PJSIP/pj-main-00000002','IAX2/iax-main-12345','DAHDI/12-1','Local/12345@external-carrier-00000042;1',"SIP/literal_%'peer-00000002") as $number=>$channel)
    direction_row('destination-tech-'.$number, array('dstchannel'=>$channel), true);
direction_row('forward-trunk-to-trunk', array('channel'=>'SIP/carrier-main-00000001','dstchannel'=>'PJSIP/pj-main-00000002'), true);
direction_row('local-origin', array('channel'=>'Local/400@from-internal-00000001;1','dstchannel'=>'SIP/carrier-main-00000002'), true);
direction_row('incoming', array('channel'=>'SIP/carrier-main-00000001','dstchannel'=>'SIP/100-00000002','src'=>'short-label'), false, true);
direction_row('incoming-numeric-cid', array('channel'=>'PJSIP/pj-main-00000001','dstchannel'=>'SIP/101-00000002','src'=>'123456789'), false, true);
direction_row('internal', array('dstchannel'=>'SIP/101-00000002'), false, false, true);
direction_row('unauthorized-internal', array('channel'=>'SIP/101-00000001','dstchannel'=>'SIP/100-00000002'), false, false, true);
direction_row('internal-name-lookalike', array('dstchannel'=>'SIP/carrier-main-extra-00000002'), false, false, true);
direction_row('device-trunk-name-collision', array('dstchannel'=>'SIP/100-00000002','lastapp'=>'Dial','lastdata'=>'SIP/100,20'), false, false, true);
direction_row('unknown-endpoint', array('dstchannel'=>'SIP/carrier-main-bogus-00000002'));
direction_row('unknown-failed-dial', array('lastapp'=>'Dial','lastdata'=>'SIP/unknown/12345,20','disposition'=>'FAILED'));
direction_row('not-a-dial', array('lastapp'=>'Playback','lastdata'=>'SIP/carrier-main/12345'));
direction_row('unknown-local-context', array('dstchannel'=>'Local/12345@external-carrier-extra-00000042;1'));
direction_row('incoming-internal-callerid', array('channel'=>'SIP/101-00000001','dstchannel'=>'SIP/100-00000002','src'=>'91234567'), false, false, true);

if (in_array('--native-sql', $argv, true)) {
    $socket = getenv('MT_ASTERNIC_TEST_MYSQL_SOCKET');
    $scratch = realpath(getenv('MT_ASTERNIC_TEST_DIRECTORY') ?: '/not-a-fixture');
    if (!$socket || !$scratch || strpos(realpath($socket) ?: '', $scratch . DIRECTORY_SEPARATOR) !== 0)
        throw new RuntimeException('Explicit private MariaDB fixture socket/directory required');
    $pdo = new PDO('mysql:unix_socket='.$socket.';charset=utf8mb4', getenv('MT_ASTERNIC_TEST_MYSQL_USER') ?: 'root', '');
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $datadir = realpath($pdo->query('SELECT @@datadir')->fetchColumn());
    if (!$datadir || strpos($datadir . DIRECTORY_SEPARATOR, $scratch . DIRECTORY_SEPARATOR) !== 0)
        throw new RuntimeException('MariaDB is outside the private fixture');
    $pdo->exec('CREATE DATABASE IF NOT EXISTS asternic_direction_fixture');
    $pdo->exec('USE asternic_direction_fixture');
    $pdo->exec('CREATE TABLE cdr (id VARCHAR(80) PRIMARY KEY, channel VARCHAR(255),dstchannel VARCHAR(255),lastapp VARCHAR(80),lastdata VARCHAR(255),src VARCHAR(80),dst VARCHAR(80),dcontext VARCHAR(80),disposition VARCHAR(80))');
    $insert=$pdo->prepare('INSERT INTO cdr (id,channel,dstchannel,lastapp,lastdata,src,dst,dcontext,disposition) VALUES (?,?,?,?,?,?,?,?,?)');
    foreach ($rows as $case) $insert->execute(array_values($case['row']));
    foreach ($predicates as $direction=>$predicate) {
        $actual=$pdo->query('SELECT id FROM cdr WHERE '.$predicate)->fetchAll(PDO::FETCH_COLUMN);
        $wanted=array(); foreach ($rows as $case) if ($case['expected'][$direction]) $wanted[]=$case['row']['id'];
        sort($actual); sort($wanted);
        verify_direction('native MariaDB complete '.$direction.' cohort', $actual === $wanted);
        foreach ($rows as $case) verify_direction('native '.$direction.' '.$case['row']['id'], in_array($case['row']['id'], $actual, true) === $case['expected'][$direction]);
    }
    $permitted=$pdo->query("SELECT COUNT(*) FROM cdr WHERE (".$predicates['outgoing'].") AND channel='SIP/100-00000001' AND id='prefix-none'")->fetchColumn();
    verify_direction('channel attribution survives rewritten caller ID', (int)$permitted === 1);
}
foreach ($tests as $name=>$pass) echo ($pass ? 'PASS ' : 'FAIL ') . $name . "\n";
exit(in_array(false,$tests,true) ? 1 : 0);
