"""Remove the native web language controls without changing Asterisk prompts."""

from pathlib import Path


MENU_GUARD = '''    if (!is_array($arrMenuFiltered)) {
        die("FATAL: unable to filter module list for user: ".$pMenu->errMsg);
    }
'''
MENU_FILTER = MENU_GUARD + "    unset($arrMenuFiltered['language']);\n"
MENU_REQUEST = "    $selectedMenu = getParameter('menu');\n"
PANEL_REQUEST = MENU_REQUEST + """    if ($selectedMenu === 'language') {
        $selectedMenu = 'index';
    }
"""
OLD_COOKIE = """if (!isset($_COOKIE['lang'])) { setcookie("lang", $lang); }"""
PANEL_COOKIE = """if (!isset($_COOKIE['lang']) || $_COOKIE['lang'] !== $lang) { setcookie("lang", $lang); }"""
PICKER_START = "\n$current_lang = $_COOKIE['lang'];\n"
PICKER_END = """$out .= '<div class="navbar-item"><div class="buttons">';"""
PICKER_REMOVED = "\n// MytelPBX uses the panel language in the embedded console.\n\n"


def replace_once(text, before, after):
    if text.count(after) == 1 and text.count(before) == after.count(before):
        return text
    if text.count(before) != 1 or after in text:
        raise ValueError("Native panel locale anchor changed: " + before.splitlines()[0])
    return text.replace(before, after, 1)


def remove_pbx_picker(text):
    if text.count(PICKER_REMOVED) == 1 and PICKER_START not in text:
        return text
    if text.count(PICKER_START) != 1 or text.count(PICKER_END) != 1 or PICKER_REMOVED in text:
        raise ValueError("Native PBX language selector boundaries changed")
    before, rest = text.split(PICKER_START, 1)
    picker, after = rest.split(PICKER_END, 1)
    for anchor in ("if($amp_conf['SHOWLANGUAGE'])", 'id="language-menu-button"', "data-lang="):
        if picker.count(anchor) != 1:
            raise ValueError("Native PBX language selector changed: " + anchor)
    return before + PICKER_REMOVED + PICKER_END + after


def plan(web):
    web = Path(web).absolute()
    panel, console = web / "index.php", web / "admin/views/menu.php"
    originals = {}
    for path in (panel, console):
        if not path.is_file() or path.resolve() != path:
            raise ValueError("Missing or symlinked panel locale input: " + str(path))
        originals[path] = path.read_text(encoding="utf-8")

    # Filter normal navigation and reject the old writer before the optional
    # global-module dispatch. Stale session menu IDs fall back in navigation.
    text = replace_once(originals[panel], MENU_GUARD, MENU_FILTER)
    text = replace_once(text, MENU_REQUEST, PANEL_REQUEST)
    return {
        panel: replace_once(text, OLD_COOKIE, PANEL_COOKIE),
        console: remove_pbx_picker(originals[console]),
    }
