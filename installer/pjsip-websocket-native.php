<?php
/* Native PEAR DB adapter for an owned fresh bootstrap. SPDX-License-Identifier: GPL-2.0-only */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }

function mytel_ws_result($result) {
    if (DB::isError($result)) throw new RuntimeException('Native database operation failed');
    return $result;
}

function mytel_ws_rows($db, $lock = false) {
    $sql = 'SELECT keyword,data,seq,type FROM sipsettings ORDER BY keyword,data,seq,type';
    if ($lock) $sql .= ' FOR UPDATE';
    $raw = mytel_ws_result($db->getAll($sql, null, DB_FETCHMODE_ORDERED));
    if (!is_array($raw) || count($raw) > 1000) throw new RuntimeException('Unknown native row set');
    $rows = array();
    foreach ($raw as $row) {
        if (!is_array($row) || count($row) !== 4) throw new RuntimeException('Unknown row shape');
        foreach ($row as $value) {
            if (!is_string($value) && !is_int($value)) throw new RuntimeException('Unknown native cell type');
        }
        $rows[] = array_map('strval', array_values($row));
    }
    sort($rows);
    return $rows;
}

function mytel_ws_snapshot($db) {
    $columns = array();
    foreach (mytel_ws_result($db->getAll('SHOW COLUMNS FROM sipsettings', null, DB_FETCHMODE_ASSOC)) as $column) {
        $columns[] = array((string)$column['Field'], (string)$column['Type'], (string)$column['Null'],
                           $column['Default'] === null ? null : (string)$column['Default'],
                           (string)$column['Key'], (string)$column['Extra']);
    }
    $primary = array();
    foreach (mytel_ws_result($db->getAll('SHOW INDEX FROM sipsettings', null, DB_FETCHMODE_ASSOC)) as $index) {
        if ($index['Key_name'] === 'PRIMARY') $primary[(int)$index['Seq_in_index']] = $index['Column_name'];
    }
    ksort($primary);
    $counts = array();
    foreach (array('devices', 'users', 'trunks') as $table) {
        $value = mytel_ws_result($db->getOne('SELECT COUNT(*) FROM ' . $table));
        if (!ctype_digit((string)$value)) throw new RuntimeException('Unknown native count');
        $counts[$table] = (int)$value;
    }
    $engine = mytel_ws_result($db->getOne("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='sipsettings'"));
    $transaction = mytel_ws_result($db->getOne('SELECT @@in_transaction'));
    if ($transaction !== 0 && $transaction !== '0' && $transaction !== 1 && $transaction !== '1') {
        throw new RuntimeException('Unknown transaction status');
    }
    return array('rows'=>mytel_ws_rows($db), 'columns'=>$columns, 'primary'=>array_values($primary),
                 'engine'=>$engine, 'counts'=>$counts, 'transaction'=>(int)$transaction,
                 'autocommit'=>isset($db->autocommit) && $db->autocommit === true);
}

function mytel_ws_insert($db, $expected) {
    $owned = false;
    try {
        $before = mytel_ws_snapshot($db);
        $schema = array(array('keyword','varchar(50)','NO','','PRI',''), array('data','varchar(255)','NO','','',''),
                        array('seq','tinyint(1)','NO','1','PRI',''), array('type','tinyint(1)','NO','0','PRI',''));
        if ($before['columns'] !== $schema || $before['primary'] !== array('keyword','seq','type')
            || $before['engine'] !== 'InnoDB' || $before['transaction'] !== 0 || !$before['autocommit']
            || $before['counts'] !== array('devices'=>0,'users'=>0,'trunks'=>0)
            || count($before['rows']) !== 17) throw new RuntimeException('Native fresh transaction refused');
        mytel_ws_result($db->query('START TRANSACTION'));
        $owned = true;
        $rows = mytel_ws_rows($db, true);
        $actual = hash('sha256', json_encode($rows, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
        if (!is_string($expected) || !preg_match('/\A[a-f0-9]{64}\z/', $expected) || !hash_equals($expected, $actual)) {
            throw new RuntimeException('Native rows changed after prepare');
        }
        // Exactly the native SIP_NORMAL row emitted by sipsettings' normal generator.
        $statement = mytel_ws_result($db->prepare('INSERT INTO sipsettings (keyword,data,seq,type) VALUES (?,?,?,?)'));
        mytel_ws_result($db->execute($statement, array('websocket_enabled','no','0','0')));
        $wanted = $rows; $wanted[] = array('websocket_enabled','no','0','0'); sort($wanted);
        if (mytel_ws_rows($db) !== $wanted) throw new RuntimeException('Native write verification failed');
        mytel_ws_result($db->query('COMMIT'));
        $owned = false;
        return mytel_ws_snapshot($db);
    } finally {
        if ($owned) { try { $db->query('ROLLBACK'); } catch (Throwable $ignored) {} }
    }
}

// Tests require only the pure functions above; the executable path has no test/config include override.
if (isset($argv[0]) && realpath($argv[0]) === __FILE__) {
    try {
        if (!function_exists('posix_geteuid') || posix_geteuid() !== 0) throw new RuntimeException('root required');
        $input = stream_get_contents(STDIN, 65537);
        if (strlen($input) > 65536) throw new RuntimeException('Input too large');
        $request = json_decode($input, true);
        $action = isset($argv[1]) ? $argv[1] : '';
        if (!is_array($request) || !in_array($action, array('snapshot','insert'), true)
            || array_keys($request) !== ($action === 'insert' ? array('before_rows_sha256') : array())) {
            throw new RuntimeException('Unknown adapter request');
        }
        $restrict_mods = true;
        $bootstrap_settings = array('skip_astman'=>true, 'issabelpbx_error_handler'=>false);
        // The captured native CLI bootstrap owns configuration/PEAR initialization.
        // Its vendor hooks can run: this path is restricted to the verified fresh cohort.
        require '/etc/issabelpbx.conf';
        $result = $action === 'snapshot' ? mytel_ws_snapshot($db) : mytel_ws_insert($db, $request['before_rows_sha256']);
        echo json_encode($result, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    } catch (Throwable $error) {
        fwrite(STDERR, "Native WebSocket adapter refused; no success claimed.\n");
        exit(1);
    }
}
