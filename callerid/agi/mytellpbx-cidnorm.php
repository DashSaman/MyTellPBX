#!/usr/bin/env php
<?php
/**
 * MyTellPBX Caller-ID normalization — shared AGI application.
 *
 * Runs inside the Asterisk Gosub hook ([mytellpbx-cidnorm]) on inbound
 * calls.  Uses the SAME CidNorm library as the panel preview and the
 * test suite, so runtime, preview and tests share one contract.
 *
 * Design constraints (GPT decision 3 D1):
 *  - Bounded execution: every AGI exchange has a read timeout.
 *  - Protocol-safe output: only valid AGI commands on stdout.
 *  - Failure preserves the original identity and lets routing continue:
 *    any exception or unexpected condition exits 0 WITHOUT touching the
 *    channel beyond what already succeeded.
 *  - Re-entry safe via the __MYPBX_CID_DONE completion flag; the original
 *    number is preserved once in __MYPBX_CID_ORIG for diagnostics.
 *
 * CLI self-test: php mytellpbx-cidnorm.php --selftest
 *
 * @license GPL-2.0 (MyTellPBX project)
 */

namespace MyTellPBX\Cid;

require_once __DIR__ . '/../lib/CidNorm.php';

/**
 * Minimal AGI protocol session.  Injectable for tests.
 */
interface AgiIo
{
    /** @return string|false next response line (without newline) */
    public function readLine();

    /** @param string $command  full AGI command  @return string response line */
    public function command($command);

    /** آرگومان‌های agi_arg_N (پرچم‌ها را دیال‌پلان قطعاً پاس می‌دهد) */
    public function envArgs();
}

/** Real AGI session over stdin/stdout with a bounded read timeout. */
final class StdAgiIo implements AgiIo
{
    private $in;
    private $out;
    private $env = array();

    public function __construct($in = null, $out = null)
    {
        $this->in  = $in  === null ? STDIN  : $in;
        $this->out = $out === null ? STDOUT : $out;
        stream_set_timeout($this->in, 4);
        // Consume the AGI environment block (agi_*: value lines).
        while (true) {
            $line = fgets($this->in);
            if ($line === false || rtrim($line, "\r\n") === '') {
                break;
            }
            if (preg_match('/^agi_(\w+):\s*(.*)$/', rtrim($line, "\r\n"), $m)) {
                $this->env[$m[1]] = $m[2];
            }
        }
    }

    public function env($key, $default = '')
    {
        return isset($this->env[$key]) ? $this->env[$key] : $default;
    }

    public function envArgs()
    {
        $out = array();
        foreach ($this->env as $k => $v) {
            if (preg_match('/^arg_(\d+)$/', $k, $m)) {
                $out[(int)$m[1]] = $v;
            }
        }
        return $out;
    }

    public function readLine()
    {
        $line = fgets($this->in);
        return $line === false ? false : rtrim($line, "\r\n");
    }

    public function command($command)
    {
        fwrite($this->out, $command . "\n");
        fflush($this->out);
        return $this->readLine();
    }
}

/** The application logic, isolated from the transport for testability. */
final class CidAgiApp
{
    /** @var AgiIo */
    private $io;
    private $verbose = array();

    public function __construct(AgiIo $io)
    {
        $this->io = $io;
    }

    /**
     * @param array $opts 'enabled','done','quirks','callerNum','callerName'
     *                    pre-fetched channel state (tests); null = read via AGI.
     */
    public function run(array $state = null)
    {
        try {
            $s = $state !== null ? $state : $this->readState();
        } catch (\Exception $e) {
            return 0; // bounded failure: leave channel untouched
        }

        if ($s['done'] === '1' || $s['enabled'] !== '1') {
            return 0;
        }

        $rawNum = $s['callerNum'];
        // Empty / Asterisk unknown markers: nothing to normalize.
        if ($rawNum === '' || $rawNum === '<unknown>' || $rawNum === 'unknown') {
            $this->markDone($s);
            return 0;
        }

        $r = CidNorm::normalize($rawNum, array('quirks' => $s['quirks'] === '1'));
        $newNum = $r['num'];

        if ($newNum !== $rawNum) {
            try {
                if ($s['orig'] === '') {
                    $this->io->command('SET VARIABLE __MYPBX_CID_ORIG "' . $rawNum . '"');
                }
                $this->io->command('SET VARIABLE CALLERID(num) "' . $newNum . '"');
                // Name policy: a number-as-name placeholder follows the
                // number; a real name is never touched.
                if ($s['callerName'] !== '' && $s['callerName'] === $rawNum) {
                    $this->io->command('SET VARIABLE CALLERID(name) "' . $newNum . '"');
                }
                $this->verbose[] = "cidnorm: {$r['note']} {$rawNum} -> {$newNum}";
            } catch (\Exception $e) {
                // Partial failure: identity may be half-set; still mark done
                // to keep execution bounded and let routing continue.
            }
        } else {
            $this->verbose[] = "cidnorm: passthrough {$r['note']}";
        }

        $this->markDone($s);
        return 0;
    }

    private function readState()
    {
        // پرچم‌ها از آرگومان‌های ای‌جی‌آی (دیال‌پلان سراسری‌ها را قطعاً
        // حل می‌کند)؛ متغیرهای کانال از پروتکل.
        $args = $this->io->envArgs();
        $enabled = (isset($args[1]) && $args[1] !== '')
            ? $args[1] : $this->getVar('MYTELLPBX_CIDNORM', '0');
        $quirks = (isset($args[2]) && $args[2] !== '')
            ? $args[2] : $this->getVar('MYTELLPBX_CIDNORM_QUIRKS', '0');
        $done    = $this->getVar('__MYPBX_CID_DONE', '');
        $orig    = $this->getVar('__MYPBX_CID_ORIG', '');
        $num     = $this->getVar('CALLERID(num)', '');
        $name    = $this->getVar('CALLERID(name)', '');
        return array(
            'enabled' => $enabled, 'done' => $done, 'quirks' => $quirks,
            'orig' => $orig, 'callerNum' => $num, 'callerName' => $name,
        );
    }

    private function getVar($name, $default)
    {
        $line = (string)$this->io->command('GET VARIABLE ' . $name);
        // AGI: «200 result=<code> (<value>)» یا بدون مقدار «200 result=0»
        if (preg_match('/^200 result=\d+ \((.*)\)$/', $line, $m)) {
            $v = $m[1];
        } elseif (preg_match('/^200 result=\((.*)\)$/', $line, $m)) {
            $v = $m[1];
        } else {
            return $default;
        }
        return $v === '' ? $default : $v;
    }

    private function markDone(array $s)
    {
        try {
            $this->io->command('SET VARIABLE __MYPBX_CID_DONE "1"');
        } catch (\Exception $e) {
            // ignore; re-entry still guarded by idempotent normalization
        }
    }

    public function verboseLines()
    {
        return $this->verbose;
    }
}

// ── Entry point ───────────────────────────────────────────────────────────
if (PHP_SAPI === 'cli' && isset($argv[0])
    && realpath($argv[0]) === realpath(__FILE__)) {
    if (in_array('--selftest', $argv, true)) {
        // Handled by tests/AgiAdapterTest.php through this flag.
        require_once __DIR__ . '/../tests/AgiAdapterTest.php';
        exit(\run_adapter_selftest());
    }
    $app = new CidAgiApp(new StdAgiIo());
    $app->run();
    foreach ($app->verboseLines() as $v) {
        fwrite(STDERR, $v . "\n");
    }
    exit(0);
}
