#!/usr/bin/env python3
"""Build a UI-only artifact outside the served trees. Python 3.6+, no installs.

The installed desk source/toolchain is a build input, never an output directory.
All candidate served bytes and their expected live hashes enter the manifest.
"""
# subprocess capture_output/text were introduced after the PBX's Python 3.6.
# ruff: noqa: UP021, UP022
import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]
PANEL_FILES = (
    "_common/index.tpl", "_common/_menu.tpl", "_common/_shortcut.tpl",
    "_common/_list.tpl", "_common/login.tpl", "_common/popup.tpl", "_common/help.tpl",
    "css/tokens.css", "css/workspace.css", "js/theme.js", "js/mytel-charts.js",
    "js/workspace.js", "js/appearance.js", "help.css", "styles.css",
)
DEFAULT_ROOTS = {
    "panel": "/var/www/html/themes/mytel", "admin": "/var/www/html/admin",
    "desk": "/opt/opdesk/frontend", "phone": "/var/www/html/Phone",
}


def sha(path):
    if path.is_symlink() or path.exists() and not path.is_file():
        raise ValueError("Refusing a non-regular build input")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(target))


def adapt_runner_config(path):
    """Vite's ESM runner does not inject the bundler's __dirname shim.

    Adapt only the isolated copy; the installed configuration stays a hash guard.
    """
    text = path.read_text(encoding="utf-8")
    if not re.search(r"\b__dirname\b", text) or re.search(r"\b(?:const|let|var)\s+__dirname\b", text):
        return
    if "__mtBuildFileURLToPath" in text:
        raise ValueError("Vite runner compatibility name collision")
    shim = "import { fileURLToPath as __mtBuildFileURLToPath } from 'node:url';\n"
    shim += "const __dirname = __mtBuildFileURLToPath(new URL('.', import.meta.url));\n"
    path.write_text(shim + text, encoding="utf-8")


def prepare(work, roots, source_id, node="node", php="php"):
    work = work.resolve()
    policy = load("ui_rollout_policy", "scripts/ui/rollout.py")
    policy.outside_served(work, roots)
    if set(roots) != set(DEFAULT_ROOTS) or any(not root.is_dir() for root in roots.values()):
        raise ValueError("All four installed UI roots are required")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source_id):
        raise ValueError("An exact Git tree ID is required")
    if work.exists():
        raise ValueError("Use a new isolated build directory; no existing work is deleted")
    baseline = {}

    def remember(root, relative):
        file = policy.within(roots[root], relative)
        baseline[(root, relative)] = sha(file)

    for root, names in policy.ALLOW.items():
        for relative in names:
            remember(root, relative)
    for file in (roots["desk"] / "dist").rglob("*"):
        if file.is_symlink():
            raise ValueError("Symlink in desk runtime inputs")
        if file.is_file():
            remember("desk", file.relative_to(roots["desk"]).as_posix())
    for directory in ("src", "public"):
        for file in (roots["desk"] / directory).rglob("*"):
            if any(part == "__pycache__" or ".bak" in part for part in file.parts):
                continue
            if file.is_symlink():
                raise ValueError("Symlink in desk build inputs")
            if file.is_file():
                relative = file.relative_to(roots["desk"]).as_posix()
                remember("desk", relative)
    configurations = set()
    for pattern in ("package*.json", "tsconfig*.json", "vite.config.*", "*eslint*", "*stylelint*", "index.html"):
        for file in roots["desk"].glob(pattern):
            if file.is_file():
                configurations.add(file.name)
                remember("desk", file.name)
    work.mkdir(parents=True, mode=0o700)
    candidate = work / "build"
    frontend = candidate / "desk"
    frontend.mkdir(parents=True)
    shutil.copytree(str(roots["desk"] / "src"), str(frontend / "src"),
                    ignore=shutil.ignore_patterns("*.bak*", "__pycache__"))
    for name in sorted(configurations):
        copy(roots["desk"] / name, frontend / name)
    if (frontend / "vite.config.ts").is_file():
        adapt_runner_config(frontend / "vite.config.ts")
    os.symlink(str(roots["desk"] / "node_modules"), str(frontend / "node_modules"), target_is_directory=True)
    shutil.copytree(str(roots["desk"] / "public"), str(frontend / "public"))
    desk_patch = load("desk_workspace_build", "modules/mytellpbxopdesk/patches/patch-workspace.py")
    desk_changes = desk_patch.plan(frontend)
    for file, text in desk_changes.items():
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
    admin_patch = load("admin_workspace_build", "admin-theme/patch-admin-theme.py")
    phone_patch = load("phone_workspace_build", "webphone/patch-webphone.py")
    checks = []
    environment = dict(os.environ)
    environment["PATH"] = str(pathlib.Path(node).resolve().parent) + os.pathsep + environment.get("PATH", "") if os.path.isabs(node) else environment.get("PATH", "")

    def check(label, argv, cwd=frontend):
        result = subprocess.run(argv, cwd=str(cwd), env=environment, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, timeout=600, check=False)
        (work / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        checks.append({"check": label, "rc": result.returncode})
        if result.returncode:
            raise RuntimeError(label + " failed; see its private build log")

    check("typecheck", [node, "node_modules/typescript/bin/tsc", "--noEmit"])
    check("eslint-login", [node, "node_modules/eslint/bin/eslint.js", "src/components/Login.tsx", "--quiet"])
    check("stylelint-workspace", [node, "node_modules/stylelint/bin/stylelint.mjs", "src/styles/mytell-workspace.css"])
    # The runner avoids Vite's temporary config in the symlinked live toolchain.
    check("vite", [node, "node_modules/vite/bin/vite.js", "build", "--configLoader", "runner",
                   "--outDir", str(frontend / "dist"), "--assetsDir", "assets", "--base=/MytellDesk/"])
    index = (frontend / "dist/index.html").read_text(encoding="utf-8")
    if 'src="/MytellDesk/assets/' not in index or 'src="/opdesk/' in index:
        raise ValueError("Incorrect desk public base")
    files = []

    def add(root, relative, data, order=10):
        target = roots[root] / relative
        before = baseline.get((root, relative))
        if sha(target) != before:
            raise ValueError("Live drift during preparation: " + root + "/" + relative)
        after = hashlib.sha256(data).hexdigest()
        if before == after:
            return
        payload = "payload/" + root + "/" + relative
        output = work / payload
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        files.append({"root": root, "path": relative, "payload": payload, "before": before,
                      "after": after, "size": len(data), "order": order})

    for relative in PANEL_FILES:
        add("panel", relative, (REPO / "theme" / relative).read_bytes(), 30 if relative.endswith(".tpl") else 10)
    for file, text in admin_patch.plan(roots["admin"]).items():
        relative = file.relative_to(roots["admin"]).as_posix()
        data = text.encode("utf-8")
        add("admin", relative, data, 30 if relative.endswith(".php") else 10)
        if relative.endswith(".php"):
            output = candidate / "admin" / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
            check("php-" + file.stem, [php, "-l", str(output)], work)
    for file, text in phone_patch.plan(roots["phone"]).items():
        add("phone", file.name, text.encode("utf-8"), 30 if file.name == "index.html" else 10)
    for file in desk_changes:
        add("desk", file.relative_to(frontend).as_posix(), file.read_bytes(), 20)
    for file in sorted((frontend / "dist").rglob("*")):
        if file.is_file():
            relative = file.relative_to(frontend / "dist").as_posix()
            if relative.startswith("assets/"):
                add("desk", "dist/" + relative, file.read_bytes())
            elif relative != "index.html" and sha(roots["desk"] / "dist" / relative) != sha(file):
                raise ValueError("Unrelated desk public asset differs; reconcile before release: " + relative)
    add("desk", "dist/index.html", (frontend / "dist/index.html").read_bytes(), 40)
    for (root, relative), previous in baseline.items():
        if sha(roots[root] / relative) != previous:
            raise ValueError("Live input changed during preparation: " + root + "/" + relative)
    changed = {(item["root"], item["path"]) for item in files}
    manifest = {"schema": 1, "source_id": source_id, "base": "/MytellDesk/",
                "checks": checks, "files": sorted(files, key=lambda item: (item["order"], item["root"], item["path"])),
                "inputs": [{"root": root, "path": relative, "sha256": previous}
                           for (root, relative), previous in sorted(baseline.items())
                           if previous is not None and (root, relative) not in changed]}
    policy.validate(work, manifest, roots)
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_sha256": sha(work / "manifest.json"), "files": len(files), "checks": checks}, indent=2))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=pathlib.Path, required=True)
    parser.add_argument("--source-id", required=True, help="Exact candidate Git tree ID; independent review is a separate gate")
    parser.add_argument("--node", default="node")
    parser.add_argument("--php", default="php")
    parser.add_argument("--roots", type=pathlib.Path, help="External JSON root mapping; no credentials")
    args = parser.parse_args()
    roots = json.loads(args.roots.read_text()) if args.roots else DEFAULT_ROOTS
    prepare(args.workdir, {key: pathlib.Path(value) for key, value in roots.items()}, args.source_id, args.node, args.php)
