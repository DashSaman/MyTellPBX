#!/usr/bin/env python3
"""Install the MyTellDesk presentation overlay. No backend restart or build.

Use --frontend-root for an isolated build tree. Build that tree with the existing
toolchain and --base=/MytellDesk/ before publishing any dist assets.
"""
import argparse
import json
import os
import pathlib
import shutil
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
OVERLAY = ROOT / "opdesk/frontend-src"
MARK = "  // MyTell workspace v740: presentation only; authentication above is preserved."
IMPORT = "import './styles/mytell-workspace.css';"
TRANSLATIONS = {
    "fa": {
        "workspaceProduct": "میز کار یکپارچه مرکز تماس",
        "workspaceHeading": "هر تماس، در دید شما.",
        "workspaceDescription": "داخلی‌ها، صف‌ها و مکالمات را در یک میز کار دنبال کنید.",
        "workspaceSignIn": "ورود به میز کار",
        "workspaceWelcome": "حساب خود را انتخاب کنید و وارد شوید.",
        "workspacePanelHint": "با حساب مدیر پنل مرکز تماس وارد شوید.",
        "workspaceDeskHint": "از نام کاربری یا شماره داخلیِ حساب میز کار استفاده کنید.",
        "workspacePanelUsername": "نام کاربری پنل",
        "workspaceBack": "بازگشت به پنل مدیریت",
    },
    "en": {
        "workspaceProduct": "Your contact center workspace",
        "workspaceHeading": "Every call, in view.",
        "workspaceDescription": "Follow extensions, queues and conversations from one operator workspace.",
        "workspaceSignIn": "Sign in to your workspace",
        "workspaceWelcome": "Choose your account type to continue.",
        "workspacePanelHint": "Use your contact center panel administrator account.",
        "workspaceDeskHint": "Use the username or extension of your desk account.",
        "workspacePanelUsername": "Panel username",
        "workspaceBack": "Back to the management panel",
    },
}


def sound_paths(text):
    # Dynamic Audio URLs are not rewritten by Vite. Keep call logic unchanged.
    for name, count in (("ringtone", 1), ("dialing", 2), ("hangup", 1)):
        old = "new Audio('/sounds/" + name + ".wav')"
        new = "new Audio(import.meta.env.BASE_URL + 'sounds/" + name + ".wav')"
        if text.count(old) + text.count(new) != count:
            raise ValueError("Desk sound URL anchors changed: " + name)
        text = text.replace(old, new)
    return text


def plan(frontend):
    src = frontend / "src"
    main = src / "main.tsx"
    login = src / "components/Login.tsx"
    main_text = main.read_text(encoding="utf-8")
    login_text = login.read_text(encoding="utf-8")
    if IMPORT not in main_text:
        anchor = "import './styles/utilities.css'"
        if anchor not in main_text:
            raise ValueError("Desk main.tsx styles anchor changed")
        # Keep utility import intact; the workspace layer intentionally follows it.
        end = main_text.index("\n", main_text.index(anchor))
        main_text = main_text[:end] + "\n" + IMPORT + main_text[end:]
    anchor = MARK if MARK in login_text else '  return (\n    <div className="login-page">'
    if anchor not in login_text or 'const handleSubmit = async' not in login_text:
        raise ValueError("Desk login presentation anchor changed")
    prefix = login_text[:login_text.index(anchor)]
    login_text = prefix + (OVERLAY / "components/login-view.tsx.part").read_text(encoding="utf-8")
    changes = {main: main_text, login: login_text,
               src / "styles/mytell-workspace.css": (OVERLAY / "styles/mytell-workspace.css").read_text(encoding="utf-8")}
    phone_hook = src / "hooks/useWebPhone.ts"
    changes[phone_hook] = sound_paths(phone_hook.read_text(encoding="utf-8"))
    for language, values in TRANSLATIONS.items():
        path = src / f"i18n/locales/{language}/translation.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("login", {}).update(values)
        changes[path] = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return changes


def apply(frontend, check=False):
    changes = plan(frontend)  # Validate everything before making any write.
    for path, text in changes.items():
        previous = path.stat() if path.exists() else path.parent.stat()
        if path.exists() and path.read_text(encoding="utf-8") == text:
            print("UNCHANGED", path.relative_to(frontend))
            continue
        if check:
            print("WOULD UPDATE", path.relative_to(frontend))
            continue
        if path.exists():
            backup = path.with_name(path.name + ".v740.bak-mt")
            if not backup.exists():
                shutil.copy2(str(path), str(backup))
        fd, temporary = tempfile.mkstemp(prefix=".mt-ui-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
            os.chmod(temporary, (previous.st_mode & 0o777) if path.exists() else 0o644)
            if hasattr(os, "chown"):
                os.chown(temporary, previous.st_uid, previous.st_gid)
            os.replace(temporary, str(path))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        print("UPDATED", path.relative_to(frontend))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-root", type=pathlib.Path, default=pathlib.Path("/opt/opdesk/frontend"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    apply(args.frontend_root, args.check)
