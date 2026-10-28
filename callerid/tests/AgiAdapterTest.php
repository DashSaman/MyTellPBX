<?php
/**
 * Adapter self-test with a scripted fake AGI session (no Asterisk).
 * Also runnable standalone: php tests/AgiAdapterTest.php
 *
 * @license GPL-2.0
 */
require_once __DIR__ . '/../lib/CidNorm.php';
require_once __DIR__ . '/../agi/mytellpbx-cidnorm.php';

use MyTellPBX\Cid\AgiIo;
use MyTellPBX\Cid\CidAgiApp;

/** Fake AGI transport: scripted variable values + recorded commands. */
class FakeAgiIo implements AgiIo
{
    public $vars;
    public $commands = array();

    public function __construct(array $vars)
    {
        $this->vars = $vars;
    }

    public function readLine()
    {
        return '200 result=0';
    }

    public function envArgs()
    {
        return array();
    }

    public function command($command)
    {
        $this->commands[] = $command;
        if (preg_match('/^GET VARIABLE (\S+)/', $command, $m)) {
            $v = isset($this->vars[$m[1]]) ? $this->vars[$m[1]] : '';
            return '200 result=1 (' . $v . ')';
        }
        return '200 result=1';
    }
}

/** فقط فرمان‌های نوشتنی (SET VARIABLE) — خواندن‌ها بی‌اثرند */
function sets_of($io)
{
    $out = '';
    foreach ($io->commands as $c) {
        if (strpos($c, 'SET VARIABLE') === 0) {
            $out .= $c . "\n";
        }
    }
    return $out;
}

function run_adapter_selftest()
{
    $fails = 0;
    $pass = 0;
    $check = function ($cond, $label) use (&$fails, &$pass) {
        if ($cond) { $pass++; return; }
        $fails++; echo "FAIL: $label\n";
    };

    // ۱) فعال: موبایل ۱۰رقمی → افزودن صفر + پرچم پایان + ذخیرهٔ اصلی
    $io = new FakeAgiIo(array(
        'MYTELLPBX_CIDNORM' => '1',
        '__MYPBX_CID_DONE' => '',
        'MYTELLPBX_CIDNORM_QUIRKS' => '0',
        '__MYPBX_CID_ORIG' => '',
        'CALLERID(num)' => '9123456789',
        'CALLERID(name)' => '9123456789',
    ));
    (new CidAgiApp($io))->run();
    $cmds = sets_of($io);
    $check(strpos($cmds, 'SET VARIABLE CALLERID(num) "09123456789"') !== false,
           'mobile 10d -> 0+ set');
    $check(strpos($cmds, 'SET VARIABLE CALLERID(name) "09123456789"') !== false,
           'number-as-name follows number');
    $check(strpos($cmds, 'SET VARIABLE __MYPBX_CID_ORIG "9123456789"') !== false,
           'orig preserved once');
    $check(strpos($cmds, 'SET VARIABLE __MYPBX_CID_DONE "1"') !== false,
           'done flag set');

    // ۲) نام واقعی دست نمی‌خورد
    $io = new FakeAgiIo(array(
        'MYTELLPBX_CIDNORM' => '1',
        '__MYPBX_CID_DONE' => '',
        'MYTELLPBX_CIDNORM_QUIRKS' => '0',
        '__MYPBX_CID_ORIG' => '',
        'CALLERID(num)' => '+989121112233',
        'CALLERID(name)' => 'Rayan Clinic',
    ));
    (new CidAgiApp($io))->run();
    $check(strpos(sets_of($io), 'SET VARIABLE CALLERID(name)') === false,
           'real name untouched');

    // ۳) ورود دوباره: پرچم پایان → هیچ فرمانی
    $io = new FakeAgiIo(array(
        'MYTELLPBX_CIDNORM' => '1',
        '__MYPBX_CID_DONE' => '1',
        'MYTELLPBX_CIDNORM_QUIRKS' => '0',
        '__MYPBX_CID_ORIG' => 'x',
        'CALLERID(num)' => '9123456789',
        'CALLERID(name)' => '',
    ));
    (new CidAgiApp($io))->run();
    $check(sets_of($io) === '', 're-entry no-op');

    // ۴) غیرفعال: هیچ تغییری
    $io = new FakeAgiIo(array(
        'MYTELLPBX_CIDNORM' => '0',
        '__MYPBX_CID_DONE' => '',
        'MYTELLPBX_CIDNORM_QUIRKS' => '0',
        '__MYPBX_CID_ORIG' => '',
        'CALLERID(num)' => '9123456789',
        'CALLERID(name)' => '',
    ));
    (new CidAgiApp($io))->run();
    $check(sets_of($io) === '', 'disabled no-op');

    // ۵) خارجی/ناشناس: بدون تغییر شماره
    foreach (array('+442071234567', 'Anonymous', '') as $num) {
        $io = new FakeAgiIo(array(
            'MYTELLPBX_CIDNORM' => '1',
            '__MYPBX_CID_DONE' => '',
            'MYTELLPBX_CIDNORM_QUIRKS' => '0',
            '__MYPBX_CID_ORIG' => '',
            'CALLERID(num)' => $num,
            'CALLERID(name)' => '',
        ));
        (new CidAgiApp($io))->run();
        $check(strpos(sets_of($io), 'SET VARIABLE CALLERID(num)') === false,
               "no rewrite for [$num]");
    }

    // ۶) پاسخ نامعتبر پروتکل → خروج بی‌خطر
    $io = new class(array(
        'MYTELLPBX_CIDNORM' => '1',
        '__MYPBX_CID_DONE' => '',
        'MYTELLPBX_CIDNORM_QUIRKS' => '0',
        '__MYPBX_CID_ORIG' => '',
        'CALLERID(num)' => '9123456789',
        'CALLERID(name)' => '',
    )) extends FakeAgiIo {
        public function command($c)
        {
            $this->commands[] = $c;
            return '510 Invalid or unknown command';
        }
    };
    (new CidAgiApp($io))->run(); // نباید استثنا بیرون بزند
    $pass++;

    echo $fails === 0 ? "PASS: adapter $pass checks OK\n"
                      : "FAILURES: $fails\n";
    return $fails === 0 ? 0 : 1;
}

// اجرای مستقیم
if (PHP_SAPI === 'cli' && isset($argv[0])
    && realpath($argv[0]) === realpath(__FILE__)) {
    exit(run_adapter_selftest());
}
