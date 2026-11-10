<?php
/* Own only the native SIP table replacement, never the caller's transaction. */
function mytell_sip_replace($db, $rows) {
    if (!is_array($rows) || empty($rows)) {
        return $db->raiseError('SIP settings replacement requires populated rows.');
    }
    foreach ($rows as $row) {
        if (!is_array($row) || array_keys($row) !== array(0, 1, 2, 3)) {
            return $db->raiseError('Invalid SIP settings replacement row.');
        }
    }

    $owned = false;
    try {
        // A driver may not reflect a transaction started through raw SQL.
        // Both ownership checks must pass before START, which would otherwise
        // implicitly commit the caller's transaction. Unknown engines/drivers
        // retain the existing replacement behavior without an owned commit.
        if (isset($db->autocommit) && $db->autocommit === true) {
            $inTransaction = $db->getOne('SELECT @@in_transaction');
            if ($inTransaction === 0 || $inTransaction === '0') {
                $engine = $db->getOne("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sipsettings'");
                if (is_string($engine) && strcasecmp($engine, 'InnoDB') === 0) {
                    $result = $db->query('START TRANSACTION');
                    if (DB::isError($result)) return $result;
                    $owned = true;
                }
            }
        }

        $result = $db->query('DELETE FROM `sipsettings` WHERE 1');
        if (DB::isError($result)) return $result;
        $statement = $db->prepare('INSERT INTO `sipsettings` (`keyword`, `data`, `seq`, `type`) VALUES (?,?,?,?)');
        if (DB::isError($statement)) return $statement;
        $result = $db->executeMultiple($statement, $rows);
        if (DB::isError($result)) return $result;

        if ($owned) {
            // PEAR's commit() can mask the COMMIT result with a later SET.
            // Raw query preserves that first error and changes no autocommit.
            $result = $db->query('COMMIT');
            if (DB::isError($result)) return $result;
            $owned = false;
        }
        return true;
    } catch (Throwable $error) {
        return $db->raiseError('SIP settings replacement could not be confirmed.');
    } finally {
        if ($owned) {
            // A lost commit acknowledgment remains an error even if rollback
            // cannot undo an already committed result. Never claim success or
            // replace the first error with a secondary rollback failure.
            try { $db->query('ROLLBACK'); } catch (Throwable $rollbackError) {}
        }
    }
}
