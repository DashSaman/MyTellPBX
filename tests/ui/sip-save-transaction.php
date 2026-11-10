<?php
/* Fake DB only. Never include PBX/bootstrap/PEAR or connect to a real database. */
class SipFixtureError {
    public $message;
    function __construct($message) { $this->message = $message; }
    function getMessage() { return $this->message; }
    function getDebugInfo() { return $this->message; }
}
class DB {
    static function isError($value) { return $value instanceof SipFixtureError; }
}
class SipFixtureDB {
    public $autocommit = true;
    public $engine = 'InnoDB';
    public $inTransaction = false;
    public $data;
    public $committed;
    public $log = array();
    public $parameters;
    public $fail = array();
    public $throwAt = null;
    private $snapshot;
    function __construct() {
        $this->data = $this->committed = array(array('original', 'retained', 1, 1));
    }
    function raiseError($message) { return new SipFixtureError($message); }
    function failure($stage) {
        if ($this->throwAt === $stage) throw new RuntimeException('fixture exception');
        return isset($this->fail[$stage]) ? $this->fail[$stage] : null;
    }
    function persist() { if (!$this->inTransaction) $this->committed = $this->data; }
    function outerTransaction() { $this->snapshot = $this->data; $this->inTransaction = true; }
    function getOne($sql) {
        $this->log[] = $sql;
        if ($sql === 'SELECT @@in_transaction') {
            $error = $this->failure('probe');
            return $error ? $error : ($this->inTransaction ? '1' : '0');
        }
        if (stripos($sql, 'information_schema.TABLES') !== false && strpos($sql, "'sipsettings'") !== false) {
            $error = $this->failure('engine');
            return $error ? $error : $this->engine;
        }
        throw new RuntimeException('Unexpected metadata SQL');
    }
    function query($sql) {
        $this->log[] = $sql;
        if ($sql === 'START TRANSACTION') {
            $error = $this->failure('begin'); if ($error) return $error;
            if ($this->inTransaction) throw new RuntimeException('START would commit an outer transaction');
            $this->outerTransaction(); return 1;
        }
        if ($sql === 'DELETE FROM `sipsettings` WHERE 1') {
            $error = $this->failure('delete'); if ($error) return $error;
            $this->data = array(); $this->persist(); return 1;
        }
        if ($sql === 'COMMIT') {
            $error = $this->failure('commit'); if ($error) return $error;
            $this->committed = $this->data; $this->inTransaction = false;
            $error = $this->failure('commit_ack'); return $error ? $error : 1;
        }
        if ($sql === 'ROLLBACK') {
            $error = $this->failure('rollback'); if ($error) return $error;
            if ($this->inTransaction) $this->data = $this->snapshot;
            $this->inTransaction = false; return 1;
        }
        throw new RuntimeException('Unexpected write SQL');
    }
    function prepare($sql) {
        $this->log[] = 'PREPARE ' . $sql;
        $error = $this->failure('prepare'); if ($error) return $error;
        demand($sql === 'INSERT INTO `sipsettings` (`keyword`, `data`, `seq`, `type`) VALUES (?,?,?,?)', 'parameterized INSERT changed');
        return 'prepared-sip-insert';
    }
    function executeMultiple($statement, $rows) {
        demand($statement === 'prepared-sip-insert', 'invalid prepared handle');
        $this->parameters = $rows;
        foreach ($rows as $i => $row) {
            $this->log[] = 'EXECUTE ROW';
            if ($i === 1) { $error = $this->failure('execute'); if ($error) return $error; }
            $this->data[] = $row; $this->persist();
        }
        return 1;
    }
    function autoCommit($enabled) { throw new RuntimeException('Do not change autocommit'); }
    function commit() { throw new RuntimeException('Do not use PEAR commit'); }
    function rollback() { throw new RuntimeException('Do not use PEAR rollback'); }
}
function demand($condition, $message) { if (!$condition) throw new RuntimeException($message); }
function countSql($db, $sql) { return count(array_keys($db->log, $sql, true)); }

/* Native owner behavior, used only to demonstrate RED before the helper exists. */
function legacy_sip_replace_fixture($db, $rows) {
    $db->query('DELETE FROM `sipsettings` WHERE 1');
    $compiled = $db->prepare('INSERT INTO `sipsettings` (`keyword`, `data`, `seq`, `type`) VALUES (?,?,?,?)');
    if (DB::isError($compiled)) return $compiled;
    $result = $db->executeMultiple($compiled, $rows);
    return DB::isError($result) ? $result : true;
}
$helper = isset($argv[1]) ? $argv[1] : dirname(__DIR__, 2) . '/admin-fixes/sip-save-transaction.php';
$operation = 'legacy_sip_replace_fixture';
if (is_file($helper)) {
    require $helper;
    demand(function_exists('mytell_sip_replace'), 'helper function missing');
    $operation = 'mytell_sip_replace';
}
$rows = array();
for ($i = 0; $i < 77; $i++) $rows[] = array('key_' . $i, "quote'\\value" . $i, $i, 1);
$tests = array();
function checkCase($name, $test) {
    global $tests;
    try { $test(); $tests[$name] = true; echo 'PASS ' . $name . "\n"; }
    catch (Throwable $error) { $tests[$name] = false; echo 'FAIL ' . $name . ': ' . $error->getMessage() . "\n"; }
}
echo 'MODE ' . ($operation === 'mytell_sip_replace' ? 'helper' : 'native legacy reproducer') . "\n";
checkCase('77 rows replace atomically with one owned commit', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $result = $operation($db, $rows);
    demand($result === true && $db->data === $rows && $db->committed === $rows, 'replacement differs');
    demand(countSql($db, 'START TRANSACTION') === 1 && countSql($db, 'COMMIT') === 1 && countSql($db, 'ROLLBACK') === 0, 'missing single transaction');
    demand($db->parameters === $rows && $db->autocommit === true, 'parameters or autocommit changed');
});
foreach (array('delete', 'prepare', 'execute', 'commit') as $stage) {
    checkCase($stage . ' failure preserves original rows and first error', function () use ($operation, $rows, $stage) {
        $db = new SipFixtureDB(); $original = $db->data;
        $error = $db->fail[$stage] = new SipFixtureError($stage);
        $result = $operation($db, $rows);
        demand($result === $error, 'failure lost or reported true');
        demand($db->data === $original && $db->committed === $original, 'table left empty or partial');
        demand(countSql($db, 'ROLLBACK') === 1, 'owned transaction not rolled back');
    });
}
checkCase('rollback failure cannot mask the original commit error', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $first = $db->fail['commit'] = new SipFixtureError('commit');
    $db->fail['rollback'] = new SipFixtureError('rollback');
    demand($operation($db, $rows) === $first && countSql($db, 'ROLLBACK') === 1, 'first error replaced or rollback skipped');
});
checkCase('lost commit acknowledgment is never reported as success', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $error = $db->fail['commit_ack'] = new SipFixtureError('commit acknowledgment lost');
    demand($operation($db, $rows) === $error, 'uncertain commit reported true');
    demand(countSql($db, 'ROLLBACK') === 1, 'rollback not attempted after commit error');
});
checkCase('failed START cannot reach DELETE', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $original = $db->data; $error = $db->fail['begin'] = new SipFixtureError('begin');
    demand($operation($db, $rows) === $error && $db->data === $original, 'failed START continued');
    demand(countSql($db, 'DELETE FROM `sipsettings` WHERE 1') === 0 && countSql($db, 'ROLLBACK') === 0, 'write or rollback without ownership');
});
foreach (array(false, true) as $driverAuto) {
    checkCase('outer transaction retained with driver autocommit ' . ($driverAuto ? 'true' : 'false'), function () use ($operation, $rows, $driverAuto) {
        $db = new SipFixtureDB(); $db->autocommit = $driverAuto; $original = $db->committed; $db->outerTransaction();
        demand($operation($db, $rows) === true && $db->inTransaction && $db->committed === $original, 'outer transaction committed');
        demand(countSql($db, 'START TRANSACTION') + countSql($db, 'COMMIT') + countSql($db, 'ROLLBACK') === 0, 'outer ownership changed');
        $db->query('ROLLBACK'); demand($db->data === $original, 'caller cannot rollback its replacement');
    });
}
checkCase('outer transaction failure remains for caller rollback', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $db->autocommit = false; $db->outerTransaction(); $original = $db->committed;
    $error = $db->fail['execute'] = new SipFixtureError('execute');
    demand($operation($db, $rows) === $error && countSql($db, 'ROLLBACK') === 0, 'helper rolled back caller transaction');
    $db->query('ROLLBACK'); demand($db->data === $original, 'caller state lost');
});
foreach (array('MyISAM', '', null) as $engine) {
    checkCase('unverified engine uses legacy ownership ' . var_export($engine, true), function () use ($operation, $rows, $engine) {
        $db = new SipFixtureDB(); $db->engine = $engine;
        demand($operation($db, $rows) === true && $db->data === $rows, 'legacy behavior changed');
        demand(countSql($db, 'START TRANSACTION') + countSql($db, 'COMMIT') + countSql($db, 'ROLLBACK') === 0, 'transaction assumed on unverified engine');
    });
}
foreach (array('probe', 'engine') as $stage) {
    checkCase('unavailable ' . $stage . ' metadata does not assume ownership', function () use ($operation, $rows, $stage) {
        $db = new SipFixtureDB(); $db->fail[$stage] = new SipFixtureError($stage);
        demand($operation($db, $rows) === true && countSql($db, 'START TRANSACTION') === 0, 'metadata failure changed legacy save');
    });
}
checkCase('unknown driver ownership never starts a transaction', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); unset($db->autocommit);
    demand($operation($db, $rows) === true && countSql($db, 'START TRANSACTION') === 0, 'unknown driver ownership assumed');
});
foreach (array(array(), array(array('short', 'row'))) as $invalid) {
    checkCase('invalid row set cannot delete existing settings ' . count($invalid), function () use ($operation, $invalid) {
        $db = new SipFixtureDB(); $original = $db->data;
        demand(DB::isError($operation($db, $invalid)), 'invalid rows accepted');
        demand($db->data === $original && count($db->log) === 0, 'invalid input reached database');
    });
}
checkCase('exception in middle of INSERT rolls back owned replacement', function () use ($operation, $rows) {
    $db = new SipFixtureDB(); $original = $db->data; $db->throwAt = 'execute';
    demand(DB::isError($operation($db, $rows)), 'exception not converted to DB error');
    demand($db->data === $original && countSql($db, 'ROLLBACK') === 1, 'exception left table partial');
});
echo 'RESULT ' . count(array_filter($tests)) . '/' . count($tests) . " passed; fake DB only\n";
exit(in_array(false, $tests, true) ? 1 : 0);
