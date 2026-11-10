"""Add an attempt-bound result marker to the existing native SIP settings POST."""
from pathlib import Path

ANCHOR = '  <h2><?php echo __("SIP Settings"); ?></h2>'
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


def plan(admin):
    path = Path(admin) / 'modules/sipsettings/page.sipsettings.php'
    return {path: transform(path.read_text(encoding='utf-8'))}
