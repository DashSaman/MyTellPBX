<?php
/** Only the existing Apply privilege may enter the reload operation.
 * A custom same-origin XHR header prevents cross-site form submissions. */
function mytell_apply_authorized($user, $server) {
    if (!is_object($user) || !method_exists($user, 'checkSection') || !$user->checkSection('99')) return false;
    if (strtolower(isset($server['HTTP_X_REQUESTED_WITH']) ? $server['HTTP_X_REQUESTED_WITH'] : '') !== 'xmlhttprequest') return false;
    if (isset($server['HTTP_ORIGIN'])) {
        $scheme = !empty($server['HTTPS']) && $server['HTTPS'] !== 'off' ? 'https' : 'http';
        if ($server['HTTP_ORIGIN'] !== $scheme . '://' . $server['HTTP_HOST']) return false;
    }
    return true;
}

/** Called only after fileRequestHandler has authenticated the PBX user. */
function mytell_guarded_reload($callback, $lock_path = '/var/run/asterisk/mytell-apply.lock') {
    // A fixed file in Asterisk's private runtime directory, never a request path.
    if (is_link($lock_path)) {
        return array('status'=>false, 'http_status'=>503, 'num_errors'=>1,
            'message'=>'Cannot acquire the configuration apply lock.');
    }
    $lock = @fopen($lock_path, 'c');
    if ($lock === false) {
        return array('status'=>false, 'http_status'=>503, 'num_errors'=>1,
            'message'=>'Cannot acquire the configuration apply lock.');
    }
    if (!flock($lock, LOCK_EX | LOCK_NB)) {
        fclose($lock);
        return array('status'=>false, 'http_status'=>409, 'num_errors'=>0,
            'message'=>'Another configuration apply is already running.');
    }
    try {
        // Authentication/session writes are finished. Read-only pages should
        // not queue behind retrieve_conf for the entire PHP session lifetime.
        if (session_status() === PHP_SESSION_ACTIVE) session_write_close();
        return call_user_func($callback);
    } catch (Throwable $error) {
        // An interrupted operation has an uncertain outcome; the UI treats
        // HTTP 500 as unknown and never automatically repeats the request.
        error_log('MyTellPBX Apply: unexpected reload failure');
        return array('status'=>false, 'http_status'=>500, 'num_errors'=>1,
            'message'=>'The server could not confirm the configuration apply result.');
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}
