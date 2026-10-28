<?php
/**
 * MyTellPBX Caller-ID normalization — test suite (mission synthetic
 * contract + upstream-observed shapes + negative cases).
 *
 * Run: php callerid/tests/CidNormTest.php   (exit 0 = pass)
 * @license GPL-2.0
 */
require_once __DIR__ . '/../lib/CidNorm.php';

use MyTellPBX\Cid\CidNorm;

$fails = 0;
$pass = 0;

function check($got, $want, $label)
{
    global $fails, $pass;
    if ($got === $want) {
        $pass++;
        return;
    }
    $fails++;
    echo "FAIL: $label — got " . var_export($got, true)
       . ", want " . var_export($want, true) . "\n";
}

/* ── Mission synthetic contract: all five forms -> 09123456789 ── */
foreach (array(
    '09123456789'  => '09123456789',
    '9123456789'   => '09123456789',
    '989123456789' => '09123456789',
    '+989123456789'=> '09123456789',
    '00989123456789' => '09123456789',
) as $in => $want) {
    $r = CidNorm::normalize($in);
    check($r['num'], $want, "synthetic $in");
}

/* ── Idempotence over every fixture ── */
$fixtures = array(
    '09123456789','9123456789','989123456789','+989123456789','00989123456789',
    '0989123456789', '982112345678', '+982112345678', '0098211234567',
    '2112345678', '02112345678', '021 1234 5678', '12345678',
    '100', '911', '+442071234567', '00442071234567', '00201234567890',
    'Anonymous', 'anonymous', 'private', '', 'unknown', '0912123456۷',
);
foreach ($fixtures as $f) {
    $once = CidNorm::normalize($f);
    $twice = CidNorm::normalize($once['num']);
    check($twice['num'], $once['num'], "idempotent $f");
}

/* ── Landline (Tehran family, validated patterns) ── */
check(CidNorm::normalize('982112345678')['num'], '02112345678', 'landline 98+21');
check(CidNorm::normalize('2112345678')['num'], '02112345678', 'landline 10d area');
check(CidNorm::normalize('02112345678')['num'], '02112345678', 'landline already-normalized');
check(CidNorm::normalize('2101234567890')['num'], '01234567890', 'tehran-210 echo (13d)');
check(CidNorm::normalize('210981234567890')['num'], '01234567890', 'tehran-21098 echo (15d)');

/* ── Other area codes: 10-digit with valid prefix -> 0+; else passthrough ── */
check(CidNorm::normalize('2632345678')['num'], '02632345678', 'area 026 10-digit');
check(CidNorm::normalize('3912345678')['num'], '3912345678', 'invalid area prefix unchanged');

/* ── Negative cases: preserve ── */
foreach (array(
    '+442071234567', '00442071234567',   // foreign
    '12345678',                            // ambiguous 8-digit tail
    '100', '911', '411',                   // short codes
    'Anonymous', 'PRIVATE', 'withheld', '', 'unknown', // privacy/empty
    'Rayan Clinic',                        // non-numeric
) as $in) {
    $r = CidNorm::normalize($in);
    check($r['num'], $in, "preserve [$in]");
}

/* ── Persian digits + separators ── */
check(CidNorm::normalize('۰۹۱۲۳۴۵۶۷۸۹')['num'], '09123456789', 'persian digits');
check(CidNorm::normalize('0912 123 4567')['num'], '09121234567', 'separators');

/* ── Provider quirks: explicit profile only ── */
check(CidNorm::normalize('00009123456789')['num'], '00009123456789', 'quirk off by default');
check(CidNorm::normalize('00009123456789', array('quirks' => true))['num'],
      '09123456789', 'quirk 0000 strip (enabled)');
check(CidNorm::normalize('0021989123456789', array('quirks' => true))['num'],
      '09123456789', 'quirk 002198 strip (enabled)');
// idempotence with quirks on
$q1 = CidNorm::normalize('00009123456789', array('quirks' => true));
check(CidNorm::normalize($q1['num'], array('quirks' => true))['num'],
      '09123456789', 'quirk idempotent');

/* ── changed-flag correctness ── */
check(CidNorm::normalize('9123456789')['changed'], true, 'changed flag true');
check(CidNorm::normalize('09123456789')['changed'], false, 'changed flag false');
check(CidNorm::normalize('+442071234567')['changed'], false, 'foreign unchanged flag');

echo $fails === 0
    ? "PASS: $pass checks OK\n"
    : "FAILURES: $fails (passed $pass)\n";
exit($fails === 0 ? 0 : 1);
