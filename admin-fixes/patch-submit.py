"""Add an attempt-bound result marker to the existing native SIP settings POST."""
from pathlib import Path

ANCHOR = '  <h2><?php echo __("SIP Settings"); ?></h2>'
OLD_REPLACE = '''        sql("DELETE FROM `sipsettings` WHERE 1");
        $compiled = $db->prepare('INSERT INTO `sipsettings` (`keyword`, `data`, `seq`, `type`) VALUES (?,?,?,?)');
        $result = $db->executeMultiple($compiled,$save_settings);'''
NEW_REPLACE = '''        // MyTellPBX SIP replacement v753: one owned InnoDB transaction.
        require_once dirname(__DIR__, 2) . '/libraries/mytell-sip-save.php';
        $result = mytell_sip_replace($db, $save_settings);'''
MARKER = '''<?php /* MyTellPBX native save result v753: no form values are echoed. */
if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] === 'POST' &&
    $action === 'edit' && isset($_POST['mt_save_attempt']) && is_string($_POST['mt_save_attempt']) &&
    preg_match('/^[a-f0-9]{32}$/D', $_POST['mt_save_attempt'])) {
    $mt_result = isset($errors) && $errors === true ? 'success' : 'validation-error';
    echo '<div hidden id="mt-save-result" data-attempt="' . htmlspecialchars($_POST['mt_save_attempt'], ENT_QUOTES, 'UTF-8') .
        '" data-status="' . $mt_result . '" data-display="sipsettings"></div>';
}
?>
'''


def transform(text):
    if text.count(MARKER) == 1:
        return text
    if 'MyTellPBX native save result v753' in text or text.count(ANCHOR) != 1:
        raise ValueError('SIP settings source drift; no partial save marker patch')
    return text.replace(ANCHOR, MARKER + ANCHOR, 1)


def transform_functions(text):
    if text.count(NEW_REPLACE) == 1 and OLD_REPLACE not in text:
        return text
    if 'MyTellPBX SIP replacement v753' in text or text.count(OLD_REPLACE) != 1:
        raise ValueError('SIP replacement source drift')
    return text.replace(OLD_REPLACE, NEW_REPLACE, 1)


def plan(admin):
    admin = Path(admin)
    path = admin / 'modules/sipsettings/page.sipsettings.php'
    functions = admin / 'modules/sipsettings/functions.inc.php'
    text = transform_functions(functions.read_text(encoding='utf-8'))
    # Full installer writes plan order; put the dependency before its caller.
    return {admin/'libraries/mytell-sip-save.php':(Path(__file__).parent/'sip-save-transaction.php').read_text(encoding='utf-8'),
            functions:text, path: transform(path.read_text(encoding='utf-8'))}
