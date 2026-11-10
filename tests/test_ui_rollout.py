"""Offline build/transaction regressions; all roots are disposable fixtures."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, str(REPO / relative))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROLLOUT = load("ui_rollout_test", "scripts/ui/rollout.py")
PREPARE = load("ui_prepare_test", "scripts/ui/prepare.py")
LEGACY = load("ui_legacy_test", "scripts/ui/legacy.py")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)


def fingerprint(roots):
    return {(name, path.relative_to(root).as_posix()): path.read_bytes()
            for name, root in roots.items() for path in root.rglob("*") if path.is_file()}


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.roots = {name: self.root / name for name in ROLLOUT.ROOTS}
        for root in self.roots.values():
            root.mkdir()
        self.artifact, self.backup = self.root / "artifact", self.root / "backup"
        self.artifact.mkdir()
        self.review = self.root / "independent-review.txt"
        files = []
        for root, relative, old, new in (
            ("panel", "css/tokens.css", b"old tokens", b"new tokens"),
            ("panel", "js/appearance.js", None, b"new theme script"),
            ("phone", "workspace.css", b"old phone", b"new phone"),
            ("desk", "dist/index.html", b"old index", b"new index"),
        ):
            target = self.roots[root] / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if old is not None:
                target.write_bytes(old)
            payload = "payload/" + root + "/" + relative
            write(self.artifact / payload, new)
            item = {"root": root, "path": relative, "payload": payload,
                    "before": hashlib.sha256(old).hexdigest() if old is not None else None,
                    "after": hashlib.sha256(new).hexdigest(), "size": len(new)}
            item["order"] = ROLLOUT.priority(item)
            files.append(item)
        self.manifest = {"schema": 1, "base": "/MytellDesk/", "source_id": "a" * 40,
                         "checks": [{"check": name, "rc": 0} for name in sorted(ROLLOUT.REQUIRED_CHECKS)],
                         "inputs": [], "files": files}
        self.save()
        self.original = fingerprint(self.roots)

    def save(self):
        write(self.artifact / "manifest.json", json.dumps(self.manifest, indent=2))
        write(self.review, "Independent reviewer\nTREE " + self.manifest["source_id"] +
              "\nREADY sha256:" + ROLLOUT.digest(self.artifact / "manifest.json") + "\n")

    def apply(self):
        return ROLLOUT.apply(self.artifact, self.roots, self.backup, self.review)

    def test_preflight_is_read_only(self):
        ROLLOUT.validate(self.artifact, self.manifest, self.roots)
        self.assertEqual(fingerprint(self.roots), self.original)
        self.assertFalse(self.backup.exists())

    def test_legacy_root_cannot_write_backend_or_call_control_paths(self):
        for path in ("index.php", "modules/sec_geoip_map/index.php", "etc/asterisk/sip.conf", "libs/js/owner.js"):
            self.assertFalse(ROLLOUT.allowed({"root": "legacy", "path": path}))
        for path in ROLLOUT.ALLOW["legacy"]:
            self.assertTrue(ROLLOUT.allowed({"root": "legacy", "path": path}))

    def test_apply_repair_paths_require_the_explicit_scoped_profile(self):
        for path in ('functions.inc.php', 'libraries/view.functions.php', 'libraries/mytell-apply.php'):
            item = {'root': 'admin', 'path': path}
            self.assertFalse(ROLLOUT.allowed(item))
            self.assertTrue(ROLLOUT.allowed(item, 'panel-apply-calendar-v752'))
        for path in ('config.php', 'libraries/gui_auth.php', '../etc/asterisk/sip.conf'):
            self.assertFalse(ROLLOUT.allowed({'root':'admin', 'path':path}, 'panel-apply-calendar-v752'))

    def test_unknown_profile_fails_closed(self):
        self.manifest['profile'] = 'unchecked-deployment'
        self.save()
        with self.assertRaisesRegex(ValueError, 'profile'):
            ROLLOUT.validate(self.artifact, self.manifest, self.roots)

    def test_scoped_calendar_and_apply_files_roundtrip_through_private_journal(self):
        self.manifest['profile'] = ROLLOUT.SCOPED_PROFILE
        self.manifest['files'] = [item for item in self.manifest['files'] if item['root'] == 'panel']
        self.manifest['checks'] = [{'check': name, 'rc': 0} for name in ROLLOUT.SCOPED_CHECKS]
        for root, relative in [('admin', 'libraries/mytell-apply.php'), ('legacy', 'modules/calendar/scenarios/rest/CalendarEvent.class.php')]:
            item = {'root': root, 'path': relative, 'payload': 'payload/' + root + '/' + relative,
                    'before': None, 'after': hashlib.sha256(b'fixture').hexdigest(), 'size': 7, 'order': 30}
            self.assertFalse(ROLLOUT.allowed(item))
            self.assertTrue(ROLLOUT.allowed(item, ROLLOUT.SCOPED_PROFILE))
            (self.roots[root] / relative).parent.mkdir(parents=True, exist_ok=True)
            write(self.artifact / item['payload'], b'fixture')
            self.manifest['files'].append(item)
        self.save()
        self.apply()
        ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(fingerprint(self.roots), self.original)

    def test_scoped_profile_cannot_bypass_desk_and_phone_build_checks(self):
        for root, relative in [('desk', 'dist/index.html'), ('desk', 'src/main.tsx'),
                               ('phone', 'workspace.css'), ('legacy', 'libs/js/jquery/jquery-upl-colResizable-1.5.min.js')]:
            self.assertFalse(ROLLOUT.allowed({'root':root,'path':relative}, ROLLOUT.SCOPED_PROFILE))
        self.manifest['profile'] = ROLLOUT.SCOPED_PROFILE
        self.manifest['checks'] = [{'check':name,'rc':0} for name in ROLLOUT.SCOPED_CHECKS]
        self.save()
        with self.assertRaisesRegex(ValueError,'allowlist'):
            ROLLOUT.validate(self.artifact,self.manifest,self.roots)

    def test_apply_and_rollback_restore_bytes_and_remove_only_new_files(self):
        unrelated = self.roots["panel"] / "owner.txt"
        write(unrelated, "keep owner work")
        journal = self.apply()
        self.assertEqual(journal["state"], "DEPLOYED_AWAITING_BROWSER_VERIFICATION")
        self.assertNotEqual(fingerprint(self.roots), self.original)
        for item in journal["files"]:
            if item["before"] is not None:
                self.assertEqual(ROLLOUT.digest(self.backup / item["backup"]), item["before"])
        ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(unrelated.read_text(), "keep owner work")
        unrelated.unlink()
        self.assertEqual(fingerprint(self.roots), self.original)
        self.assertEqual(json.loads((self.backup / "journal.json").read_text())["state"], "ROLLED_BACK")
        ROLLOUT.rollback(self.backup, self.roots)  # Idempotent, including new paths.

    def test_changed_content_gets_new_mtime_and_rollback_restores_metadata(self):
        target = self.roots["panel"] / "css/tokens.css"
        os.utime(str(target), (946684800, 946684800))
        if os.name == "posix":
            target.chmod(0o640)
        before = target.stat()
        self.apply()
        self.assertGreater(target.stat().st_mtime, before.st_mtime)
        if os.name == "posix":
            self.assertEqual(target.stat().st_mode, before.st_mode)
            self.assertEqual(target.stat().st_uid, before.st_uid)
        ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(target.stat().st_mtime_ns, before.st_mtime_ns)
        if os.name == "posix":
            self.assertEqual(target.stat().st_mode, before.st_mode)

    @unittest.skipUnless(hasattr(os, "setxattr"), "Extended attributes are a Linux acceptance check")
    def test_extended_attributes_survive_apply_and_rollback(self):
        target = self.roots["phone"] / "workspace.css"
        try:
            os.setxattr(str(target), "user.mytell-test", b"preserved")
        except OSError as error:
            self.skipTest(str(error))
        self.apply()
        self.assertEqual(os.getxattr(str(target), "user.mytell-test"), b"preserved")
        ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(os.getxattr(str(target), "user.mytell-test"), b"preserved")

    def test_unready_or_wrong_tree_review_prevents_every_write(self):
        for text in ("PROVISIONAL publication_ready:false", "READY sha256:" + ROLLOUT.digest(self.artifact / "manifest.json")):
            with self.subTest(review=text):
                write(self.review, text)
                with self.assertRaisesRegex(ValueError, "Independent review"):
                    self.apply()
                self.assertEqual(fingerprint(self.roots), self.original)
                self.assertFalse(self.backup.exists())

    def test_drift_on_last_target_prevents_partial_apply(self):
        target = self.roots["desk"] / "dist/index.html"
        write(target, "new owner edit")
        before = fingerprint(self.roots)
        with self.assertRaisesRegex(ValueError, "Live drift"):
            self.apply()
        self.assertEqual(fingerprint(self.roots), before)
        self.assertFalse(self.backup.exists())

    def test_payload_tampering_prevents_partial_apply(self):
        write(self.artifact / self.manifest["files"][-1]["payload"], "tampered")
        with self.assertRaisesRegex(ValueError, "payload hash"):
            self.apply()
        self.assertEqual(fingerprint(self.roots), self.original)
        self.assertFalse(self.backup.exists())

    def test_only_the_hash_checked_payload_buffer_enters_the_plan(self):
        payload = self.artifact / self.manifest["files"][0]["payload"]
        original_read = pathlib.Path.read_bytes
        reads = []

        def changing_read(path):
            data = original_read(path)
            if path == payload:
                reads.append(True)
                return data if len(reads) == 1 else b"changed between hash and read"
            return data

        with mock.patch.object(pathlib.Path, "read_bytes", changing_read):
            plan = ROLLOUT.validate(self.artifact, self.manifest, self.roots)
        self.assertEqual(len(reads), 1)
        for item, _, data in plan:
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["after"])

    def test_invalid_manifests_fail_closed(self):
        original = copy.deepcopy(self.manifest)
        changes = (
            lambda value: value.update(schema=2),
            lambda value: value.update(source_id="dirty tree"),
            lambda value: value.update(files=[]),
            lambda value: value["checks"][0].update(rc=1),
            lambda value: value["checks"][0].update(rc=False),
            lambda value: value["checks"].append(copy.deepcopy(value["checks"][0])),
            lambda value: value["checks"].append({"check": "extra-failed-check", "rc": 1}),
            lambda value: value["files"].append(copy.deepcopy(value["files"][0])),
            lambda value: value["files"][0].update(path="../../etc/asterisk/extensions.conf"),
            lambda value: value["files"][0].update(root="trunks"),
            lambda value: value["files"][0].update(payload="../secret"),
            lambda value: value["files"][0].update(after=None),
            lambda value: value["files"][0].update(size=999),
            lambda value: value["files"][0].update(order=40),
        )
        for number, change in enumerate(changes):
            with self.subTest(change=number):
                invalid = copy.deepcopy(original)
                change(invalid)
                with self.assertRaises(ValueError):
                    ROLLOUT.validate(self.artifact, invalid, self.roots)
                self.assertEqual(fingerprint(self.roots), self.original)

    def test_traversal_absolute_and_noncanonical_paths_are_rejected(self):
        for relative in ("../outside", "/absolute", "css/../tokens.css", "css//tokens.css", "css\\tokens.css", "./css/tokens.css"):
            with self.subTest(path=relative), self.assertRaises(ValueError):
                ROLLOUT.within(self.roots["panel"], relative)

    def test_symlink_targets_and_payloads_are_rejected(self):
        target = self.roots["panel"] / "css/tokens.css"
        outside = self.root / "owner-file"
        write(outside, target.read_bytes())
        target.unlink()
        try:
            target.symlink_to(outside)
        except OSError as error:
            self.skipTest("Symlink privilege unavailable: " + str(error))
        with self.assertRaisesRegex(ValueError, "escapes|Symlink"):
            ROLLOUT.validate(self.artifact, self.manifest, self.roots)
        self.assertEqual(outside.read_bytes(), b"old tokens")

    def test_nonlist_build_input_inventory_is_rejected_without_writes(self):
        for invalid in (None, {}, "invalid"):
            with self.subTest(inputs=invalid):
                self.manifest["inputs"] = invalid
                with self.assertRaisesRegex(TypeError, "Invalid build input inventory"):
                    ROLLOUT.validate(self.artifact, self.manifest, self.roots)
                self.assertEqual(fingerprint(self.roots), self.original)

    def test_unchanged_build_input_drift_blocks_deployment(self):
        source = self.roots["desk"] / "src/owner.ts"
        write(source, "original handler")
        self.manifest["inputs"] = [{"root": "desk", "path": "src/owner.ts", "sha256": ROLLOUT.digest(source)}]
        self.save()
        write(source, "owner changed handler")
        before = fingerprint(self.roots)
        with self.assertRaisesRegex(ValueError, "Build input drift"):
            self.apply()
        self.assertEqual(fingerprint(self.roots), before)

    def test_unchanged_runtime_inputs_and_duplicate_guards_are_checked(self):
        source = self.roots["admin"] / "views/header.php"
        write(source, "unchanged rendered dependency")
        guard = {"root": "admin", "path": "views/header.php", "sha256": ROLLOUT.digest(source)}
        self.manifest["inputs"] = [guard]
        ROLLOUT.validate(self.artifact, self.manifest, self.roots)
        self.manifest["inputs"].append(copy.deepcopy(guard))
        with self.assertRaisesRegex(ValueError, "Build input drift"):
            ROLLOUT.validate(self.artifact, self.manifest, self.roots)
        self.manifest["inputs"].pop()
        write(source, "owner edit after packaging")
        with self.assertRaisesRegex(ValueError, "Build input drift"):
            ROLLOUT.validate(self.artifact, self.manifest, self.roots)

    def test_backup_must_be_new_and_outside_served_roots(self):
        self.backup.mkdir()
        write(self.backup / "owner-note", "keep")
        with self.assertRaisesRegex(ValueError, "must be new"):
            self.apply()
        self.assertEqual((self.backup / "owner-note").read_text(), "keep")
        self.backup = self.roots["admin"] / "public-backup"
        with self.assertRaisesRegex(ValueError, "outside served"):
            self.apply()
        self.assertEqual(fingerprint(self.roots), self.original)

    def test_mid_apply_failure_automatically_rolls_back(self):
        real_atomic = ROLLOUT.atomic_bytes
        failed = []

        def fail_once(target, data, *args, **kwargs):
            if target == self.roots["desk"] / "dist/index.html" and not failed:
                failed.append(True)
                raise OSError("injected disk failure")
            return real_atomic(target, data, *args, **kwargs)

        with mock.patch.object(ROLLOUT, "atomic_bytes", side_effect=fail_once), self.assertRaisesRegex(OSError, "injected"):
            self.apply()
        self.assertTrue(failed)
        self.assertEqual(fingerprint(self.roots), self.original)
        self.assertEqual(json.loads((self.backup / "journal.json").read_text())["state"], "ROLLED_BACK")

    def test_backups_cannot_enter_the_publishable_artifact(self):
        self.backup = self.artifact / "private-backups"
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            self.apply()
        self.assertFalse(self.backup.exists())
        self.assertEqual(fingerprint(self.roots), self.original)

    def test_rollback_restores_the_verified_backup_buffer_not_a_second_read(self):
        journal = self.apply()
        original = self.backup / next(item["backup"] for item in journal["files"] if item["before"] is not None)
        original_read = pathlib.Path.read_bytes
        reads = []

        def changing_read(path):
            data = original_read(path)
            if path == original:
                reads.append(True)
                return data if len(reads) == 1 else b"backup changed after preflight"
            return data

        with mock.patch.object(pathlib.Path, "read_bytes", changing_read):
            ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(len(reads), 1)
        self.assertEqual(fingerprint(self.roots), self.original)

    def test_rollback_refuses_owner_drift_before_restoring_any_file(self):
        self.apply()
        write(self.roots["panel"] / "css/tokens.css", "owner edit after release")
        before = fingerprint(self.roots)
        with self.assertRaisesRegex(ValueError, "unrelated live drift"):
            ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(fingerprint(self.roots), before)

    def test_rollback_refuses_corrupt_backup_before_restoring_any_file(self):
        journal = self.apply()
        item = next(item for item in journal["files"] if item["before"] is not None)
        write(self.backup / item["backup"], "corrupt original")
        before = fingerprint(self.roots)
        with self.assertRaisesRegex(ValueError, "backup corrupted"):
            ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(fingerprint(self.roots), before)

    def test_rollback_is_bound_to_original_roots(self):
        self.apply()
        changed_roots = dict(self.roots, panel=self.roots["phone"])
        with self.assertRaisesRegex(ValueError, "roots differ"):
            ROLLOUT.rollback(self.backup, changed_roots)

    def test_prepared_journal_recovers_an_interrupted_process(self):
        self.apply()
        journal = json.loads((self.backup / "journal.json").read_text())
        journal["state"] = "PREPARED"
        write(self.backup / "journal.json", json.dumps(journal))
        ROLLOUT.rollback(self.backup, self.roots)
        self.assertEqual(fingerprint(self.roots), self.original)


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.roots = {name: self.root / name for name in ROLLOUT.ROOTS}
        for name, root in self.roots.items():
            root.mkdir()
            for relative in ROLLOUT.ALLOW[name]:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
        write(self.roots["admin"] / "views/header.php", "<?php\n$html = '';\n$html .= '<head>';\n$html .= '</head>';\necho $html;\n")
        write(self.roots["admin"] / "views/footer.php", "<?php echo 'owner footer'; ?>\n</body>")
        write(self.roots["admin"] / "assets/mytel/skin.css", "/* installed skin */")
        write(self.roots["admin"] / "modules/asternic_cdr/asternic_cdr.css", LEGACY.ASTERNIC_OLD)
        write(self.roots["legacy"] / "libs/js/jquery/jquery-upl-colResizable-1.5.min.js", LEGACY.COLRESIZE_OLD + "}}")
        fallback = "homePolygon   = polygonSeries.getPolygonById(home);\nhomeLatitude  = homePolygon.visualLatitude;\nhomeLongitude = homePolygon.visualLongitude;\n"
        write(self.roots["legacy"] / "modules/sec_geoip_map/themes/default/map.tpl", fallback * 2)
        write(self.roots["phone"] / "index.html", '<html dir="ltr"><head></head><body><section id="loginCard"></section><script src="phone.js"></script></body></html>')
        desk = self.roots["desk"]
        write(desk / "src/main.tsx", "import './styles/utilities.css'\n")
        self.login_prefix = "// owner authentication prefix\nfunction Login() {\n  const handleSubmit = async () => {};\n"
        write(desk / "src/components/Login.tsx", self.login_prefix + '  return (\n    <div className="login-page">old view</div>\n  );\n}\n')
        write(desk / "src/styles/variables.css", "/* owner tokens */")
        write(desk / "src/hooks/useWebPhone.ts", "\n".join("new Audio('/sounds/" + name + ".wav');" for name in ("ringtone", "dialing", "dialing", "hangup")))
        write(desk / "src/owner.ts", "// owner backend boundary")
        for language in ("fa", "en"):
            write(desk / ("src/i18n/locales/" + language + "/translation.json"), '{"owner":"keep","login":{}}')
        write(desk / "package.json", '{"type":"module"}')
        write(desk / "index.html", "<html>source entry</html>")
        write(desk / "public/logo.svg", "<svg/>")
        write(desk / "dist/logo.svg", "<svg/>")
        (desk / "dist/assets").mkdir()
        (desk / "node_modules").mkdir()
        self.work = self.root / "isolated-build"
        self.commands = []

    def fake_command(self, argv, **kwargs):
        self.commands.append(argv)
        if "node_modules/vite/bin/vite.js" in argv:
            write(self.work / "build/desk/dist/assets/workspace-fixture.js", "// compiled fixture")
            write(self.work / "build/desk/dist/index.html", '<script src="/MytellDesk/assets/workspace-fixture.js"></script>')
            write(self.work / "build/desk/dist/logo.svg", "<svg/>")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    def prepare(self, command=None):
        # Simulate a toolchain link on Windows too; no dependency installation.
        with mock.patch.object(PREPARE.os, "symlink", side_effect=lambda source, target, **kwargs: pathlib.Path(target).mkdir()), \
                mock.patch.object(PREPARE.subprocess, "run", side_effect=command or self.fake_command), \
                contextlib.redirect_stdout(io.StringIO()):
            return PREPARE.prepare(self.work, self.roots, "a" * 40)

    def test_preparation_never_writes_installed_inputs_and_binds_the_artifact(self):
        before = fingerprint(self.roots)
        manifest = self.prepare()
        self.assertEqual(fingerprint(self.roots), before)
        self.assertEqual(manifest["source_id"], "a" * 40)
        self.assertEqual(manifest["base"], "/MytellDesk/")
        self.assertTrue((self.work / "build/desk/src/components/Login.tsx").read_text(encoding="utf-8").startswith(self.login_prefix))
        self.assertIn("src/owner.ts", [item["path"] for item in manifest["inputs"]])
        self.assertIn("dist/logo.svg", [item["path"] for item in manifest["inputs"]])
        vite = next(argv for argv in self.commands if "node_modules/vite/bin/vite.js" in argv)
        self.assertIn("--base=/MytellDesk/", vite)
        self.assertEqual(vite[vite.index("--configLoader") + 1], "runner")
        ROLLOUT.validate(self.work, manifest, self.roots)

    def test_failed_build_does_not_produce_a_manifest_or_touch_live_files(self):
        before = fingerprint(self.roots)
        with self.assertRaisesRegex(RuntimeError, "typecheck failed"):
            self.prepare(lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, stdout="", stderr="fixture error"))
        self.assertFalse((self.work / "manifest.json").exists())
        self.assertEqual(fingerprint(self.roots), before)

    def test_runner_dirname_shim_is_private_idempotent_and_never_deployed(self):
        config = self.roots["desk"] / "vite.config.ts"
        original = "import path from 'node:path';\nconst certDir = path.resolve(__dirname, '../cert');\n"
        write(config, original)
        before = fingerprint(self.roots)
        manifest = self.prepare()
        candidate = self.work / "build/desk/vite.config.ts"
        adapted = candidate.read_text(encoding="utf-8")
        self.assertIn("const __dirname = __mtBuildFileURLToPath(new URL('.', import.meta.url));", adapted)
        self.assertTrue(adapted.endswith(original))
        PREPARE.adapt_runner_config(candidate)
        self.assertEqual(candidate.read_text(encoding="utf-8"), adapted)
        self.assertEqual(fingerprint(self.roots), before)
        self.assertNotIn("vite.config.ts", [item["path"] for item in manifest["files"]])
        self.assertIn("vite.config.ts", [item["path"] for item in manifest["inputs"]])

    def test_source_drift_during_build_does_not_produce_a_releasable_manifest(self):
        def command(argv, **kwargs):
            result = self.fake_command(argv, **kwargs)
            if "node_modules/vite/bin/vite.js" in argv:
                write(self.roots["desk"] / "src/owner.ts", "owner concurrent change")
            return result

        with self.assertRaisesRegex(ValueError, "changed during preparation"):
            self.prepare(command)
        self.assertFalse((self.work / "manifest.json").exists())

    def test_unchanged_served_asset_drift_after_build_blocks_deployment(self):
        manifest = self.prepare()
        write(self.roots["desk"] / "dist/logo.svg", "owner replaced public asset")
        with self.assertRaisesRegex(ValueError, "Build input drift"):
            ROLLOUT.validate(self.work, manifest, self.roots)

    def test_existing_or_served_work_directory_is_never_deleted(self):
        self.work.mkdir()
        write(self.work / "owner-note", "keep")
        with self.assertRaisesRegex(ValueError, "existing work"):
            self.prepare()
        self.assertEqual((self.work / "owner-note").read_text(), "keep")
        self.work = self.roots["panel"] / "unsafe-build"
        with self.assertRaisesRegex(ValueError, "outside served"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
