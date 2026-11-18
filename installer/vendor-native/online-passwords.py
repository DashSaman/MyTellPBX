#!/usr/bin/env python3
"""Render the pinned native --init program with a one-use credential pipe."""

import importlib.util
import os
from pathlib import Path
import sys


READ_PASSWORDS = br'''    $passwordPipe = @fopen('php://fd/3', 'rb');
    $input = $passwordPipe ? stream_get_contents($passwordPipe, 2051) : FALSE;
    if ($passwordPipe) fclose($passwordPipe);
    if ($input === FALSE || !preg_match('/\A([a-zA-Z0-9.@=_!-]{1,1024})\n([a-zA-Z0-9.@=_!-]{1,1024})\n\z/', $input, $match)) {
        error_exit("MytelPBX did not receive two valid passwords.\n", 2);
    }
    $mytelOnlinePasswords = array($match[1], $match[2]);
    unset($input, $match);
'''

MYSQL_UPDATE = br'''                // Send the quoted option through an anonymous pipe, with SQL on stdin.
                $process = proc_open(array('/usr/bin/mysql', '--defaults-file=/proc/self/fd/3', '-u', 'root'), array(
                    0 => array('file', $script, 'r'),
                    1 => array('file', '/dev/null', 'w'),
                    2 => array('file', '/dev/null', 'w'),
                    3 => array('pipe', 'r'),
                ), $pipes);
                if (!is_resource($process)) return FALSE;
                $defaults = (is_file('/etc/my.cnf') ? "!include /etc/my.cnf\n" : '') .
                    "[client]\npassword=\"" . $passwords['mysqlrootpwd'] . "\"\n";
                $written = @fwrite($pipes[3], $defaults);
                fclose($pipes[3]);
                $status = proc_close($process);
                if ($written !== strlen($defaults) || $status !== 0) return FALSE;'''


def replace(source, original, new, count=1):
    if source.count(original) != count:
        raise ValueError('Unexpected native password initialization boundary')
    return source.replace(original, new)


def render(source):
    path = Path(__file__).resolve().with_name('brand-native-dialogs.py')
    spec = importlib.util.spec_from_file_location('native_dialog_branding', str(path))
    branding = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(branding)
    source = branding.transform('passwords', source)
    source = replace(source, b'// Parse command-line options\n', br'''if (PHP_SAPI !== 'cli' || $argc !== 2 || $argv[1] !== '--init') {
    exit(2);
}

// Parse command-line options
''')
    source = replace(source, b'''$langs = array('ipbxLang'=>'en');
if(file_exists("/tmp/ipbx.lang")) {
    $langs=parse_ini_file("/tmp/ipbx.lang");
}''', b"$langs = array('ipbxLang'=>'en_US');")
    source = replace(source, b"case '--init':\n", b"case '--init':\n" + READ_PASSWORDS)
    source = replace(source, b'''        //if(!is_file("/tmp/ipbx.lang")) {
            action_changeLanguage();
        //}
        action_changeFop2();
        action_changeSip();
        system("/usr/bin/issabel-patreon > /dev/null 2>&1");''', b'''        unset($mytelOnlinePasswords);
        if (!action_changeLanguage()) error_exit("Asterisk language setup failed.\n");
        action_changeFop2();
        if (!action_changeSip()) error_exit("SIP channel setup failed.\n");''')
    source = replace(source, b'''function action_initPasswords($opt)
{
    global $langs;
''', b'''function action_initPasswords($opt)
{
    global $langs, $mytelOnlinePasswords;
''')
    source = replace(source, b"    action_installIssabelPBX($langs['ipbxLang']);",
                     b"    if (file_exists('/installamp')) print \"    Initializing the PBX core and database schemas...\\n\";\n"
                     b"    action_installIssabelPBX($langs['ipbxLang']);")
    source = replace(source, br'''        // Prompt for the MySQL password for this system
        if (!issabel_prompt_mysql_passwd()) return FALSE;
    } else {
        //dialog_infobox('Status', 'Password configuration already present.', 7, 70);
        print "Password configuration already present.\n";
        die();
    }

    apply_updatesql();''', br'''        if (!issabel_cli_mysql_passwd($mytelOnlinePasswords[0])) return FALSE;
        unset($mytelOnlinePasswords[0]);
    } else {
        fwrite(STDERR, "Password configuration already present.\n");
        return FALSE;
    }

    if (!apply_updatesql()) error_exit("Native MariaDB initialization scripts failed.\n");''')
    source = replace(source, b'if (!issabel_prompt_web_passwd(FALSE)) return FALSE;',
                     b'if (!issabel_cli_web_passwd(FALSE, $mytelOnlinePasswords[1])) return FALSE;\n'
                     b'        unset($mytelOnlinePasswords[1]);')
    source = replace(source, b'''    $res_connection = test_MySQLcon($sIssabelPBX_passwd);
''' + b'    \n' + b'''    $updateList = phase1_mkarray_updates_passwd($res_connection['qPwd'],$sIssabelPBX_passwd);

    phase2_cond_updates($updateList,$res_connection['db'],$sIssabelPBX_passwd);''', b'''    $res_connection = test_MySQLcon($sIssabelPBX_passwd);
    if ($res_connection === FALSE) return FALSE;
    $updateList = phase1_mkarray_updates_passwd($res_connection['qPwd'],$sIssabelPBX_passwd);
    if (phase2_cond_updates($updateList,$res_connection['db'],$sIssabelPBX_passwd) === FALSE) return FALSE;''')
    source = replace(source, b'''                $output = $retval = NULL;
                exec('mysql -u root '.escapeshellarg('-p'.$passwords['mysqlrootpwd']).' < '.escapeshellarg($script), $output, $retval);
                if ($retval != 0) return FALSE;''', MYSQL_UPDATE)
    source = replace(source, b'''    system("/usr/bin/issabel-change-language > /dev/null 2>&1");''', b'''    $script = escapeshellarg(__DIR__ . '/mytel-online-language.sh');
    print "    Applying Persian settings.\\n";
    system('/bin/bash ' . $script, $status);
    return $status === 0;''')
    source = replace(source, b'''    system("/usr/bin/issabel-change-sip > /dev/null 2>&1");
    restart_amportal();''', b'''    $script = escapeshellarg(__DIR__ . '/mytel-online-sip.sh');
    print "    Configuring the selected SIP driver.\\n";
    system('/bin/bash ' . $script, $status);
    if ($status !== 0) return FALSE;
    restart_amportal();
    return TRUE;''')
    source = replace(source, br'''        fwrite(STDERR, 'FATAL: unable to change mysql root password: '.$e->getMessage()."\n");''',
                     br'''        fwrite(STDERR, "Unable to set the MariaDB root password.\n");''')
    source = replace(source, br'''                    fwrite(STDERR, "FATAL: unable to update $k: ".$e->getMessage()."\n");''',
                     br'''                    fwrite(STDERR, "Unable to update $k.\n");''', 2)
    return replace(source, b'''    $height = (int)$height;
    $width = (int)$width;
    system('/usr/bin/dialog'.
        ' --stdout --sleep 1 --backtitle '.escapeshellarg($backtitle).
        ' --infobox '.escapeshellarg($msgbox).
        " $height $width");''', br'''    $message = trim($msgbox);
    if (preg_match('/\A[A-Za-z][A-Za-z0-9 .\/_-]+\z/', $message)) {
        printf("    %s\n", $message);
    }''')


def main():
    if len(sys.argv) != 2 or os.geteuid() != 0:
        raise ValueError('Expected a root-owned private initializer path')
    destination = Path(sys.argv[1]).absolute()
    parent = destination.parent
    parent_info = parent.stat()
    if parent.resolve() != parent or parent_info.st_uid != 0 or parent_info.st_mode & 0o077:
        raise ValueError('Unsafe online installer workspace')
    source = Path('/usr/bin/issabel-admin-passwords')
    info = source.lstat()
    if not source.is_file() or source.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Unexpected installed native password initializer')
    data = render(source.read_bytes())
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('MytelPBX cannot prepare native password initialization: ' + str(error))
