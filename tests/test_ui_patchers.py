"""UI migration regressions. Standard library only; never connects to a PBX."""
import contextlib
import importlib.util
import io
import json
import pathlib
import re
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ADMIN = load("admin_workspace", "admin-theme/patch-admin-theme.py")
DESK = load("desk_workspace", "modules/mytellpbxopdesk/patches/patch-workspace.py")
PHONE = load("phone_workspace", "webphone/patch-webphone.py")
HEADER = "<?php\n$html = '';\n$html .= '<head>';\n// Owner customization must survive\n$html .= '<title>PBX</title>';\n$html .= '</head>';\necho $html;\n"
LEGACY = """$html .= '<!-- MyTellPBX theme pre-paint (marker) -->';
$html .= '<script>'
. "(function(){var t='light';})();"
. '</script>';
"""
LEGACY_TOGGLE = """$html .= '<script>'
. "(function(){var btn=null;})();"
. '</script>';
"""
LOGIN_PREFIX = "import { Radio, LogIn, Loader2 } from 'lucide-react';\nfunction Login() {\n  const handleSubmit = async () => { /* unchanged authentication */ };\n"
LOGIN_VIEW = '  return (\n    <div className="login-page">old presentation</div>\n  );\n}\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AdminPatcherTests(unittest.TestCase):
    def test_fresh_and_previous_headers_upgrade_idempotently(self):
        for injection in ("", LEGACY, LEGACY + LEGACY_TOGGLE):
            with self.subTest(injection=injection):
                old = HEADER.replace("$html .= '<head>';", "$html .= '<head>';\n" + injection)
                new = ADMIN.transform_header(old)
                self.assertEqual(new, ADMIN.transform_header(new))
                self.assertEqual(new.count("workspace.js?v=740"), 1)
                self.assertEqual(new.count("workspace.css?v=740"), 1)
                self.assertNotIn("theme pre-paint (marker)", new)
                self.assertIn("// Owner customization must survive", new)
                self.assertTrue(new.endswith("echo $html;\n"))

    def test_unknown_owned_php_is_not_discarded(self):
        changed = HEADER.replace("$html .= '<head>';", "$html .= '<head>';\n" + LEGACY.splitlines()[0] + "\n// unexpected code\n")
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            ADMIN.transform_header(changed)
        with self.assertRaisesRegex(ValueError, "marker changed"):
            ADMIN.transform_header(HEADER + ADMIN.START + " edited " + ADMIN.END)

    def test_adjacent_owner_script_is_not_consumed_as_old_toggle(self):
        owner = "$html .= '<script>'\n. \"window.ownerFeature = true;\"\n. '</script>';\n"
        old = HEADER.replace("$html .= '<head>';", "$html .= '<head>';\n" + LEGACY + owner)
        self.assertIn(owner, ADMIN.transform_header(old))

    def test_missing_header_anchor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "anchor"):
            ADMIN.transform_header(HEADER.replace("$html .= '</head>';", ""))

    def test_footer_removes_only_legacy_owned_script(self):
        owner = '<script>window.ownerFeature = true;</script>\n'
        old = owner + '<script>/* MyTellPBX standalone theme toggle (old) */\n(function(){})();\n</script>\n</body>'
        new = ADMIN.transform_footer(old)
        self.assertIn(owner, new)
        self.assertNotIn("standalone theme toggle", new)
        self.assertEqual(new, ADMIN.transform_footer(new))

    def test_plan_validates_before_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write(root / "views/header.php", HEADER)
            write(root / "views/footer.php", "owner footer")
            with self.assertRaisesRegex(ValueError, "Missing"):
                ADMIN.plan(root)
            self.assertEqual((root / "views/header.php").read_text(encoding="utf-8"), HEADER)
            self.assertFalse(list(root.rglob("*.bak-mt")))

    def test_atomic_backup_never_overwrites_existing_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "header.php"
            write(path, "original")
            ADMIN.write_atomic(path, "first")
            ADMIN.write_atomic(path, "second")
            self.assertEqual(path.with_name("header.php.v740.bak-mt").read_text(), "original")
            self.assertFalse(ADMIN.write_atomic(path, "second"))
            self.assertEqual(path.read_text(), "second")

    def test_refresh_has_one_terminal_skin_block(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            write(root / "views/header.php", HEADER)
            write(root / "views/footer.php", "<?php echo 'owner'; ?>\n</body>")
            write(root / "assets/mytel/skin.css", "/* owner skin */\n" + ADMIN.SKIN_MARK + "\nold dark CSS\n/* owner appended rule */ .owner {color: red;}\n")
            for path, text in ADMIN.plan(root).items():
                ADMIN.write_atomic(path, text)
            second = ADMIN.plan(root)
            for path, text in second.items():
                self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertEqual(second[root / "assets/mytel/skin.css"].count(ADMIN.SKIN_MARK), 1)
            self.assertTrue(second[root / "assets/mytel/skin.css"].startswith("/* owner skin */"))
            self.assertIn("/* owner appended rule */ .owner {color: red;}", second[root / "assets/mytel/skin.css"])


class DeskPatcherTests(unittest.TestCase):
    def make_fixture(self, root):
        write(root / "src/main.tsx", "import './styles/utilities.css'\n// owner root\n")
        write(root / "src/components/Login.tsx", LOGIN_PREFIX + LOGIN_VIEW)
        write(root / "src/styles/variables.css", "/* owner tokens */")
        for language in ("fa", "en"):
            write(root / f"src/i18n/locales/{language}/translation.json", json.dumps({"owner": "preserved", "login": {"sourcePanel": "existing"}}))

    def test_authentication_prefix_and_owner_translations_survive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            self.make_fixture(root)
            changes = DESK.plan(root)
            self.assertTrue(changes[root / "src/components/Login.tsx"].startswith(LOGIN_PREFIX))
            self.assertEqual(changes[root / "src/main.tsx"].count(DESK.IMPORT), 1)
            for language in ("fa", "en"):
                data = json.loads(changes[root / f"src/i18n/locales/{language}/translation.json"])
                self.assertEqual(data["owner"], "preserved")
                self.assertEqual(data["login"]["sourcePanel"], "existing")

    def test_repeated_apply_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            self.make_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                DESK.apply(root)
            for path, text in DESK.plan(root).items():
                self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertEqual((root / "src/styles/variables.css").read_text(), "/* owner tokens */")

    def test_missing_translation_prevents_partial_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            self.make_fixture(root)
            (root / "src/i18n/locales/en/translation.json").unlink()
            with self.assertRaises(FileNotFoundError):
                DESK.apply(root)
            self.assertEqual((root / "src/components/Login.tsx").read_text(), LOGIN_PREFIX + LOGIN_VIEW)
            self.assertFalse(list(root.rglob("*.bak-mt")))


class PhonePatcherTests(unittest.TestCase):
    def test_csp_and_call_markup_remain_intact(self):
        old = '<html dir="ltr"><head>\n<meta http-equiv="Content-Security-Policy" content="script-src self">\n</head><body><section id="loginCard"></section><script src="phone.js?v=6"></script></body></html>'
        new = PHONE.transform(old)
        self.assertEqual(new, PHONE.transform(new))
        self.assertIn('dir="ltr"', new)
        self.assertIn('<script src="phone.js?v=6"></script>', new)
        self.assertIn('content="script-src self"', new)
        self.assertEqual(new.count('src="theme.js?v=740"'), 1)

    def test_phone_drift_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "anchors"):
            PHONE.transform("<head></head><body>unknown phone</body>")


class PresentationContractTests(unittest.TestCase):
    def test_admin_never_forces_rtl_or_reorders_forms(self):
        css = (ROOT / "admin-theme/workspace.css").read_text(encoding="utf-8")
        script = (ROOT / "admin-theme/workspace.js").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"direction\s*:\s*rtl|row-reverse|column-reverse", css))
        self.assertNotIn("setAttribute('dir'", script)
        self.assertNotIn(".submit(", script)

    def test_apply_config_can_still_be_hidden(self):
        css = (ROOT / "admin-theme/workspace.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        for block in re.findall(r"#button_reload[^{}]*\{([^}]+)\}", css):
            self.assertIsNone(re.search(r"display\s*:[^;]+!important", block))

    def test_phone_logout_is_not_hidden_when_connection_error_shows_login(self):
        css = (ROOT / "webphone/workspace.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
        self.assertIsNone(re.search(r"#btnLogout\b[^{}]*\{[^{}]*\bdisplay\s*:\s*none\b", css))

    def test_chip_and_loader_use_theme_foregrounds_not_brand_fills(self):
        css = (ROOT / "theme/css/workspace.css").read_text(encoding="utf-8")
        for selector, token in ((".mt-chip", "--mt-primary-fg"),
                                (".mt-page-loader-label b", "--mt-primary-fg"),
                                (".mt-page-loader-label span", "--mt-text-muted")):
            self.assertRegex(css, re.escape(selector) + r"\s*\{[^{}]*color:\s*var\(" + re.escape(token) + r"\)")
        self.assertRegex(css, r"\.mt-page-loader\s*\{[^{}]*background:\s*var\(--mt-bg\)")

    def test_firewall_tables_have_local_keyboard_scroll_without_reparenting(self):
        css = (ROOT / "theme/css/workspace.css").read_text(encoding="utf-8")
        script = (ROOT / "theme/js/workspace.js").read_text(encoding="utf-8")
        self.assertRegex(css, r":is\(#geoiptable, #rulestable\)\s*\{[^{}]*overflow-x:\s*auto")
        self.assertIn("querySelectorAll('#geoiptable, #rulestable')", script)
        self.assertIn("if (!table.hasAttribute('tabindex')) table.tabIndex = 0;", script)
        self.assertNotIn("table.parentNode", script)

    def test_mobile_report_filter_overrides_the_legacy_table_minimum(self):
        css = (ROOT / "theme/css/workspace.css").read_text(encoding="utf-8")
        mobile = css.split("@media (max-width: 700px)", 1)[1]
        self.assertRegex(mobile, r"body\.mt-body\.mt-cdr-page #formFilter table\s*\{[^{}]*min-width:\s*0\b")

    def test_no_live_credentials_in_new_ui_sources(self):
        for folder in ("admin-theme", "webphone", "opdesk/frontend-src"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and path.suffix in (".js", ".css", ".py", ".part"):
                    text = path.read_text(encoding="utf-8")
                    self.assertIsNone(re.search(r"github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}|-----BEGIN .*PRIVATE KEY-----", text), str(path))


class AuditHarnessTests(unittest.TestCase):
    """Exercise route handlers in a VM: no browser, credentials or network."""

    def run_audit(self, body):
        harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const source = fs.readFileSync('tests/ui/audit.cjs', 'utf8');
function audit(env = {}, documents = []) {
  const files = new Map();
  const records = documents.map(([root, name, text]) => {
    const data = Buffer.from(text);
    const payload = 'payload/' + root + '/' + name;
    files.set(path.resolve('/artifact', payload), data);
    return { root, path: name, payload, size: data.length, after: crypto.createHash('sha256').update(data).digest('hex') };
  });
  files.set(path.resolve('/artifact', 'manifest.json'), Buffer.from(JSON.stringify({ files: records })));
  const sandbox = {
    require: name => name === 'playwright-core' ? { chromium: {} } : name === 'node:fs' ? {
      mkdirSync() {},
      readFileSync(file) { assert.ok(files.has(file), 'Unexpected non-artifact read: ' + file); return files.get(file); },
    } : require(name),
    process: { env: { MT_BASE_URL: 'https://audit.invalid', ...env }, argv: [] },
    module: { exports: {} }, URL, console,
  };
  vm.runInNewContext(source, sandbox);
  return sandbox.module.exports;
}
async function routes(api, documentHTML) {
  let handler, socketHandler;
  const events = { blocked: [], external: new Set() };
  await api.installRoutes({
    async route(pattern, fn) { handler = fn; },
    async routeWebSocket(pattern, fn) { socketHandler = fn; },
  }, events);
  return { events, socket: socketHandler, async request(url, method = 'GET', navigation = true) {
    return handler({
      request: () => ({ url: () => new URL(url, 'https://audit.invalid').href, method: () => method,
        isNavigationRequest: () => navigation, resourceType: () => navigation ? 'document' : 'fetch' }),
      fulfill: options => ({ kind: 'fulfill', ...options }),
      continue: () => ({ kind: 'continue' }), abort: () => ({ kind: 'abort' }),
      fetch: () => {
        if (documentHTML === undefined) throw new Error('Unexpected live document fetch');
        return { status: () => 200, headers: () => ({ 'content-type': 'text/html' }), text: async () => documentHTML };
      },
    });
  } };
}
"""
        # PIPE and universal_newlines keep this runner compatible with Python 3.6.
        result = subprocess.run(["node", "-e", harness + "\n(async () => {\n" + body +  # noqa: UP022
                                 "\n})().catch(error => { console.error(error); process.exitCode = 1; });"],
                                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, timeout=30, check=False)  # noqa: UP021
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_artifact_only_navigation_uses_the_artifact_documents(self):
        self.run_audit("""
const r = await routes(audit({ MT_ARTIFACT_ROOT: '/artifact' }, [
  ['desk', 'dist/index.html', 'artifact desk'], ['phone', 'index.html', 'artifact phone'],
]));
assert.equal((await r.request('/MytellDesk/dashboard')).body.toString(), 'artifact desk');
assert.equal((await r.request('/Phone/')).body.toString(), 'artifact phone');
assert.equal((await r.request('/Phone/index.html')).body.toString(), 'artifact phone');
assert.equal((await r.request('/MytellDesk/api/calls', 'GET', false)).kind, 'continue');
assert.equal((await r.request('/MytellDesk/assets/unchanged.js', 'GET', false)).kind, 'continue');
""")

    def test_email_audit_waits_for_the_deferred_template_card(self):
        self.run_audit("""
const waits = [];
await audit({}).settle({
  async waitForLoadState() {}, async evaluate() {},
  locator: selector => ({ async waitFor() { waits.push(selector); } }),
}, { surface: 'panel', name: 'email_template' });
assert.deepEqual(waits, ['.mt-tpl']);
""")

    def test_panel_preview_uses_actual_template_skip_and_burger_markup(self):
        self.run_audit("""
const index = fs.readFileSync('theme/_common/index.tpl', 'utf8');
const menu = fs.readFileSync('theme/_common/_menu.tpl', 'utf8');
const r = await routes(audit({ MT_ARTIFACT_ROOT: '/artifact' }, [
  ['panel', '_common/index.tpl', index], ['panel', '_common/_menu.tpl', menu],
]), '<html><head></head><body class="mt-body page-body"><button id="mt-burger" aria-label="menu"></button><div id="neo-contentbox-maincolumn"></div></body></html>');
const response = await r.request('/index.php?menu=dashboard');
assert.ok(response.body.includes(index.match(/<a[^>]*class="mt-skip-link"[^>]*>[\\s\\S]*?<\\/a>/)[0]));
assert.ok(response.body.includes(menu.match(/<button[^>]*id="mt-burger"[^>]*>/)[0]));
assert.ok(response.body.includes('tabindex="-1"'));
""")

    def test_missing_artifact_documents_fail_closed(self):
        self.run_audit("""
const r = await routes(audit({ MT_ARTIFACT_ROOT: '/artifact' }));
await assert.rejects(() => r.request('/Phone/'), /Missing artifact phone document/);
await assert.rejects(() => r.request('/MytellDesk/dashboard'), /Missing artifact desk document/);
""")

    def test_non_get_actions_remain_blocked_in_live_and_artifact_modes(self):
        self.run_audit("""
for (const env of [{}, { MT_ARTIFACT_ROOT: '/artifact' }]) {
  const r = await routes(audit(env, [['phone', 'index.html', 'artifact phone']]));
  for (const method of ['POST', 'PUT', 'PATCH', 'DELETE']) {
    for (const url of ['/index.php', '/MytellDesk/api/calls', '/Phone/index.html']) {
      assert.equal((await r.request(url, method)).status, 405);
    }
  }
  assert.equal(r.events.blocked.length, 12);
  assert.equal((await r.request('https://outside.invalid/index.php', 'POST')).kind, 'abort');
}
""")

    def test_websockets_never_connect_to_production(self):
        self.run_audit("""
for (const env of [{}, { MT_ARTIFACT_ROOT: '/artifact' }]) {
  const r = await routes(audit(env));
  let closed = false;
  await r.socket({ url: () => 'wss://audit.invalid/socket?token=private',
    close() { closed = true; }, connectToServer() { throw new Error('Production socket opened'); } });
  assert.ok(closed);
  assert.equal(r.events.webSockets.length, 1);
  assert.equal(r.events.webSockets[0].path, '/socket');
}
await assert.rejects(() => audit().installRoutes({ async route() {} }, { blocked: [], external: new Set() }), /WebSocket routing/);
""")

    def test_unavailable_and_iframe_errors_are_findings(self):
        self.run_audit("""
const { hasFindings } = audit();
const clean = { documentOverflow: 0, lowContrast: [], lightBlocks: [], pageErrors: [], resources: [], frames: [] };
assert.equal(hasFindings(clean), false);
for (const change of [{ unavailable: true }, { status: 503 }, { pageErrors: ['t.removeClass is not a function'] },
  { resources: [{ status: 405 }] }, { resources: [{ error: 'Document load failed' }] },
  { frames: [{ ...clean, path: '/admin/config.php', direction: 'ltr', unavailable: true }] },
  { frames: [{ ...clean, path: '/admin/config.php', direction: 'rtl' }] },
  { frames: [{ path: '/admin/config.php', error: 'Iframe failed' }] }]) {
  assert.equal(hasFindings({ ...clean, ...change }), true, JSON.stringify(change));
}
assert.equal(hasFindings({ ...clean, frames: [{ ...clean, path: '/admin/config.php', direction: 'ltr' }] }), false);
""")


if __name__ == "__main__":
    unittest.main()
