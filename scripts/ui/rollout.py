#!/usr/bin/env python3
"""Hash-checked, journaled UI rollout with a narrow opt-in Apply/calendar profile.

Default operation is a read-only preflight. Apply requires an independent READY
line bound to the exact manifest plus an explicit expected server hostname.
Backups live outside served roots, never alongside a public PHP file.
The review file must be the saved independent review, not a generated local
receipt: the two exact lines bind it to the Git tree and artifact, not to an
assertion by this script about reviewer identity.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import socket
import tempfile

ROOTS = {"panel": "/var/www/html/themes/mytel", "admin": "/var/www/html/admin",
         "desk": "/opt/opdesk/frontend", "phone": "/var/www/html/Phone",
         "legacy": "/var/www/html"}
PANEL = {"_common/index.tpl", "_common/_menu.tpl", "_common/_shortcut.tpl", "_common/_list.tpl",
         "_common/login.tpl", "_common/popup.tpl", "_common/help.tpl", "css/tokens.css", "css/workspace.css",
         "js/theme.js", "js/mytel-charts.js", "js/workspace.js", "js/appearance.js", "js/mt-calendar.js", "js/calendar-core.js", "js/calendar-editor.js", "css/mt-calendar.css", "css/mt-secadv.css", "help.css", "styles.css"}
ALLOW = {
    "panel": PANEL,
    "admin": {"views/header.php", "views/footer.php", "assets/mytel/skin.css", "assets/mytel/workspace.css", "assets/mytel/workspace.js", "assets/mytel/apply.css", "assets/mytel/apply.js", "assets/mytel/feedback.js", "assets/mytel/save.js", "assets/mytel/sub.js", "modules/asternic_cdr/asternic_cdr.css"},
    "phone": {"index.html", "theme.js", "workspace.css"},
    "desk": {"src/main.tsx", "src/components/Login.tsx", "src/hooks/useWebPhone.ts", "src/styles/mytell-workspace.css", "src/i18n/locales/fa/translation.json", "src/i18n/locales/en/translation.json", "dist/index.html"},
    "legacy": {"libs/js/jquery/jquery-upl-colResizable-1.5.min.js", "modules/sec_geoip_map/themes/default/map.tpl"},
}
HASH = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_CHECKS = {"typecheck", "eslint-login", "stylelint-workspace", "vite", "php-header", "php-footer"}
SCOPED_PROFILE = 'panel-apply-calendar-v752'
SCOPED_CHECKS = {'offline-tests', 'js-syntax', 'php-syntax', 'apply-browser', 'reload-result', 'reload-guard', 'calendar-tests'}
SUBMIT_PROFILE = 'panel-submit-apply-v753'
SUBMIT_PATHS = {'views/header.php', 'assets/mytel/apply.js', 'assets/mytel/apply.css',
                'assets/mytel/feedback.js', 'assets/mytel/save.js', 'modules/sipsettings/page.sipsettings.php',
                'modules/sipsettings/functions.inc.php', 'libraries/mytell-sip-save.php'}
SUBMIT_CHECKS = SCOPED_CHECKS | {'save-browser', 'toast-lifecycle', 'sip-save-transaction'}
APPLY_PATHS = {'functions.inc.php', 'libraries/view.functions.php', 'libraries/mytell-apply.php'}
CALENDAR_PATHS = {'modules/calendar/index.php', 'modules/calendar/themes/default/calendar_gui.tpl',
                  'modules/calendar/themes/default/js/javascript.js', 'modules/calendar/scenarios/rest/CalendarEvent.class.php'}


def digest(path):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Refusing non-regular file: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def checked_bytes(path, expected, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(label + " is not a regular file")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(label + " hash mismatch")
    return data


def within(root, relative):
    if not isinstance(relative, str):
        raise TypeError("Unsafe relative path")
    rel = pathlib.PurePosixPath(relative)
    if not relative or relative != rel.as_posix() or rel.is_absolute() or ".." in rel.parts or "\\" in relative:
        raise ValueError("Unsafe relative path")
    root = root.resolve()
    target = root.joinpath(*rel.parts)
    if root not in target.resolve().parents:
        raise ValueError("Path escapes its allowed root")
    for ancestor in (target,) + tuple(target.parents):
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ValueError("Symlink in target path")
    return target


def allowed(item, profile=None):
    if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("root"), str):
        return False
    root, relative = item["root"], item["path"]
    if root not in ALLOW:
        return False
    if profile == SUBMIT_PROFILE:
        return root == 'admin' and relative in SUBMIT_PATHS
    if profile == SCOPED_PROFILE:
        return ((root == 'admin' and relative in ALLOW['admin'] | APPLY_PATHS) or
                (root == 'panel' and relative in PANEL) or
                (root == 'legacy' and relative in CALENDAR_PATHS))
    if profile is not None:
        return False
    return relative in ALLOW[root] or (root == "desk" and re.fullmatch(r"dist/assets/[A-Za-z0-9_.-]+\.(js|css|woff2?|svg|png)", relative) is not None)


def priority(item):
    if item["root"] == "desk":
        return 40 if item["path"] == "dist/index.html" else 20 if item["path"].startswith("src/") else 10
    return 30 if item["path"].endswith((".tpl", ".php", ".html")) else 10


def outside_served(path, roots):
    for root in list(roots.values()) + [pathlib.Path("/var/www/html")]:
        if path.resolve() == root.resolve() or root.resolve() in path.resolve().parents:
            raise ValueError("Private artifacts/backups must be outside served/source roots")


def valid_hash(value, nullable=False):
    return value is None and nullable or isinstance(value, str) and HASH.fullmatch(value) is not None


def validate(artifact, manifest, roots, expected="before"):
    outside_served(artifact, roots)
    if set(roots) != set(ROOTS) or any(not root.is_dir() for root in roots.values()):
        raise ValueError("All installed UI roots are required")
    if expected not in ("before", "after"):
        raise ValueError("Unknown validation phase")
    if manifest.get("schema") != 1 or manifest.get("base") != "/MytellDesk/" or not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("Unsupported or empty UI manifest")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", manifest.get("source_id", "")):
        raise ValueError("An exact Git tree ID is required")
    profile = manifest.get('profile')
    if profile not in (None, SCOPED_PROFILE, SUBMIT_PROFILE):
        raise ValueError('Unknown release profile')
    records = manifest.get("checks", [])
    if not isinstance(records, list) or any(not isinstance(item, dict) or not isinstance(item.get("check"), str) or type(item.get("rc")) is not int for item in records):
        raise ValueError("Malformed build checks")
    checks = {item["check"]: item["rc"] for item in records}
    if len(checks) != len(records):
        raise ValueError("Duplicate build checks")
    required = SUBMIT_CHECKS if profile == SUBMIT_PROFILE else SCOPED_CHECKS if profile == SCOPED_PROFILE else REQUIRED_CHECKS
    if not required.issubset(checks) or any(item["rc"] != 0 for item in records):
        raise ValueError("Required build checks did not pass")
    targets, plan = set(), []
    for item in manifest["files"]:
        if not allowed(item, profile):
            raise ValueError("Destination is outside the UI allowlist")
        if not valid_hash(item.get("before"), nullable=True) or not valid_hash(item.get("after")) or item.get("order") != priority(item) or type(item.get("size")) is not int or item["size"] < 0:
            raise ValueError("Malformed UI file record")
        if item.get("payload") != "payload/" + item["root"] + "/" + item["path"]:
            raise ValueError("Non-canonical payload path")
        target = within(roots[item["root"]], item["path"])
        if str(target) in targets:
            raise ValueError("Duplicate manifest destination")
        targets.add(str(target))
        payload = within(artifact, item["payload"])
        data = checked_bytes(payload, item["after"], "Candidate payload")
        if len(data) != item["size"]:
            raise ValueError("Candidate payload hash mismatch: " + item["path"])
        if not target.parent.is_dir():
            raise ValueError("Destination parent does not exist: " + item["path"])
        if digest(target) != item[expected]:
            raise ValueError("Live drift; nothing overwritten: " + item["root"] + "/" + item["path"])
        plan.append((item, target, data))
    inputs = manifest.get("inputs", [])
    if not isinstance(inputs, list):
        raise TypeError("Invalid build input inventory")
    guarded = set()
    for item in inputs:
        # Unchanged build/runtime inputs are guards, never write targets.
        if not isinstance(item, dict) or item.get("root") not in roots or not valid_hash(item.get("sha256")):
            raise ValueError("Invalid build input record")
        path = within(roots[item["root"]], item.get("path"))
        if str(path) in targets or str(path) in guarded or digest(path) != item["sha256"]:
            raise ValueError("Build input drift: " + item["path"])
        guarded.add(str(path))
    return sorted(plan, key=lambda entry: (priority(entry[0]), entry[0]["root"], entry[0]["path"]))


def sync_directory(directory):
    if os.name == "posix":
        fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def sync_file(path):
    # Windows _commit rejects a read-only descriptor. The production target is
    # Linux; Windows fixture tests retain the initial writable-stream fsync.
    if os.name == "posix":
        with open(str(path), "rb") as stream:
            os.fsync(stream.fileno())


def atomic_bytes(target, data, metadata=None, preserve_mtime=False):
    if not target.parent.is_dir():
        raise ValueError("Destination parent does not exist: " + str(target.parent))
    fd, temporary = tempfile.mkstemp(prefix=".mt-ui-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        previous = metadata.stat() if metadata and metadata.exists() else target.parent.stat()
        if hasattr(os, "chown"):
            os.chown(temporary, previous.st_uid, previous.st_gid)
        if metadata and metadata.exists():
            shutil.copystat(str(metadata), temporary)
        else:
            os.chmod(temporary, 0o644)
        # Changed content needs a new HTTP Last-Modified value. A rollback, on
        # the other hand, restores original timestamps as well as modes/xattrs.
        if not preserve_mtime:
            os.utime(temporary, None)
        sync_file(temporary)
        os.replace(temporary, str(target))
        sync_directory(target.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def journal_write(backup, journal):
    path = backup / "journal.json"
    atomic_bytes(path, (json.dumps(journal, indent=2) + "\n").encode("utf-8"), path if path.exists() else None)
    os.chmod(str(path), 0o600)


def rollback(backup, roots):
    outside_served(backup, roots)
    journal = json.loads((backup / "journal.json").read_text(encoding="utf-8"))
    if journal.get("schema") != 1 or journal.get("roots") != {key: str(value.resolve()) for key, value in roots.items()}:
        raise ValueError("Rollback roots differ from the deployed roots")
    # Validate the COMPLETE restore before touching any live path. A concurrent
    # owner's edit is a blocker, never an excuse to overwrite their work.
    targets, restore = set(), []
    for item in journal["files"]:
        if not allowed(item, journal.get('profile')) or not valid_hash(item.get("before"), nullable=True) or not valid_hash(item.get("after")):
            raise ValueError("Invalid rollback destination")
        if item.get("backup") != "original/" + item["root"] + "/" + item["path"] + ".bak-mt":
            raise ValueError("Invalid rollback backup path")
        target = within(roots[item["root"]], item["path"])
        if str(target) in targets:
            raise ValueError("Duplicate rollback destination")
        targets.add(str(target))
        if digest(target) not in (item["before"], item["after"]):
            raise ValueError("Rollback stopped at unrelated live drift: " + item["path"])
        original, data = None, None
        if item["before"] is not None:
            original = within(backup, item["backup"])
            data = checked_bytes(original, item["before"], "Rollback backup corrupted")
        restore.append((item, original, data))
    for item, original, data in reversed(restore):
        # Re-resolve after the complete preflight, including symlink checks.
        target = within(roots[item["root"]], item["path"])
        current = digest(target)
        if current == item["before"]:
            continue
        if current != item["after"]:
            raise ValueError("Live drift during rollback: " + item["path"])
        if item["before"] is None:
            target.unlink()  # Exact new manifest file only; no directory removal.
            sync_directory(target.parent)
        else:
            atomic_bytes(target, data, original, preserve_mtime=True)
        if digest(target) != item["before"]:
            raise RuntimeError("Rollback verification failed")
    journal["state"] = "ROLLED_BACK"
    journal_write(backup, journal)


def apply(artifact, roots, backup, review):
    manifest_path = within(artifact, "manifest.json")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    lines = review.read_text(encoding="utf-8").splitlines()
    if "READY sha256:" + manifest_hash not in lines or "TREE " + manifest.get("source_id", "") not in lines:
        raise ValueError("Independent review is not READY for this exact manifest")
    plan = validate(artifact, manifest, roots)
    if backup.exists():
        raise ValueError("Backup directory must be new")
    outside_served(backup, roots)
    if artifact.resolve() in backup.resolve().parents or backup.resolve() in artifact.resolve().parents:
        raise ValueError("Backup and publishable artifact must not overlap")
    backup.mkdir(parents=True, mode=0o700)
    journal = {"schema": 1, "profile": manifest.get('profile'), "state": "PREPARED", "manifest_sha256": manifest_hash,
               "source_id": manifest["source_id"], "roots": {key: str(value.resolve()) for key, value in roots.items()}, "files": []}
    for item, target, _ in plan:
        item = dict(item)
        item["backup"] = "original/" + item["root"] + "/" + item["path"] + ".bak-mt"
        if item["before"] is not None:
            original = within(backup, item["backup"])
            original.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(str(target), str(original))
            if hasattr(os, "chown"):
                previous = target.stat()
                os.chown(str(original), previous.st_uid, previous.st_gid)
            if digest(original) != item["before"]:
                raise ValueError("Live file changed during backup; no deployment started")
            sync_file(original)
            sync_directory(original.parent)
        journal["files"].append(item)
    # Re-check all sources after backup to detect drift before the first replace.
    plan = validate(artifact, manifest, roots)
    journal_write(backup, journal)
    try:
        for item, target, data in plan:
            target = within(roots[item["root"]], item["path"])
            if digest(target) != item["before"]:
                raise ValueError("Live file changed during deployment")
            atomic_bytes(target, data, target if target.exists() else None)
        validate(artifact, manifest, roots, "after")
        journal["state"] = "DEPLOYED_AWAITING_BROWSER_VERIFICATION"
        journal_write(backup, journal)
    except Exception:
        try:
            rollback(backup, roots)
        except Exception as restore_failure:
            raise RuntimeError("Deployment failed and rollback was blocked; preserve the private journal: " + str(backup)) from restore_failure
        raise
    return journal


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=pathlib.Path)
    parser.add_argument("--roots", type=pathlib.Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", type=pathlib.Path)
    parser.add_argument("--backup", type=pathlib.Path)
    parser.add_argument("--ready-review", type=pathlib.Path)
    parser.add_argument("--expect-hostname", required=True)
    args = parser.parse_args()
    if socket.gethostname() != args.expect_hostname:
        parser.error("Unexpected host; no files changed")
    roots = {key: pathlib.Path(value) for key, value in (json.loads(args.roots.read_text()) if args.roots else ROOTS).items()}
    if args.rollback:
        rollback(args.rollback, roots)
        print("ROLLBACK VERIFIED")
    elif args.artifact and args.apply and args.backup and args.ready_review:
        apply(args.artifact, roots, args.backup, args.ready_review)
        print("ASSET HASHES VERIFIED; real-browser verification is still required")
    elif args.artifact and not args.apply:
        validate(args.artifact, json.loads((args.artifact / "manifest.json").read_text()), roots)
        print("PREFLIGHT OK; no live path written")
    else:
        parser.error("Provide an artifact; apply additionally requires backup and READY review")
