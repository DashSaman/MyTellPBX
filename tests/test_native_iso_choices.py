"""Native ISO environment choices and a comps-only repository change boundary.

Fixtures are byte-exact public files from the supplied Issabel DVD/runtime.
The UI checks execute its real Python methods with only Gtk/thread adapters.
No native runtime, repository tool, network or installation is executed here.
"""
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/vendor-iso'
NS = 'http://linux.duke.edu/metadata/repo'
TAG = '{' + NS + '}'
COMPS_SHA = '1718aa060cb2b5d63df62e1efb8a47f2b4a16a3d757c623c42b2901974618a43'
UI_SHA = '4452c956beb5498e1a9b64546baf04d47db352b481abb5c59943dd0e60cfda39'
REPOMD_SHA = 'f840cc8b082545f31782adb13611eca0f3c2236216300991ca970a8a05ecb8c9'
NAMES_SHA = '7dc673a7643d664e607a2d612f0fd79aae9dca3de757933bca538b7d1b28a570'


def builder():
    spec = importlib.util.spec_from_file_location('native_iso_choices', ROOT / 'scripts/remaster-vendor-iso.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def package_names():
    return set(json.loads((FIXTURE / 'original-primary-names.json').read_text())['package_names'])


def semantic(node, brand=False):
    text = (node.text or '').strip()
    if brand and node.tag in ('name', 'description'):
        # Human labels may be branded or name an upstream service neutrally.
        # IDs, package names, defaults, visibility, attributes and refs may not.
        text = ''
    return node.tag, tuple(sorted(node.attrib.items())), text, tuple(semantic(child, brand) for child in node)


class NativeCompsChoicesTests(unittest.TestCase):
    def setUp(self):
        self.module = builder()
        self.original = (FIXTURE / 'original-comps.xml').read_bytes()
        self.names = package_names()

    def test_reference_bytes_and_primary_inventory_are_bound_to_original_native_media(self):
        for filename, expected in [('original-comps.xml', COMPS_SHA), ('native-software-selection.py', UI_SHA),
                                   ('original-repomd.xml', REPOMD_SHA), ('original-primary-names.json', NAMES_SHA)]:
            self.assertEqual(hashlib.sha256((FIXTURE / filename).read_bytes()).hexdigest(), expected)
        record = ET.fromstring((FIXTURE / 'original-repomd.xml').read_bytes())
        primary = next(item for item in record.findall(TAG + 'data') if item.get('type') == 'primary')
        evidence = json.loads((FIXTURE / 'original-primary-names.json').read_text())
        self.assertEqual(evidence['source_primary'], primary.find(TAG + 'location').get('href'))
        self.assertEqual(evidence['source_compressed_sha256'], primary.findtext(TAG + 'checksum'))
        self.assertEqual(len(self.names), 2179)

    def test_choices_reuse_all_native_group_data_and_ids_with_only_human_brand_labels(self):
        original = ET.fromstring(self.original)
        result = ET.fromstring(self.module.derive_comps(self.original, self.names))
        old_groups = {node.findtext('id'): node for node in original.findall('group')}
        groups = {node.findtext('id'): node for node in result.findall('group')}
        self.assertEqual(set(groups), set(old_groups), 'Do not synthesize or replace native package groups')
        for identity in old_groups:
            self.assertEqual(semantic(groups[identity], brand=True),
                             semantic(old_groups[identity], brand=True), identity)
        environments = {node.findtext('id'): node for node in result.findall('environment')}
        self.assertEqual(set(environments), {'issabelast16', 'issabelast18', 'issabelast20'})
        for version, order in [('20', '1'), ('18', '2'), ('16', '3')]:
            item = environments['issabelast' + version]
            self.assertIn('MytelPBX', item.findtext('name'))
            self.assertIn('Asterisk ' + version, item.findtext('name'))
            self.assertEqual(item.findtext('display_order'), order)
            self.assertEqual([node.text.strip() for node in item.findall('grouplist/groupid')],
                             ['asterisk' + version, 'issabel'])
        native18 = next(node for node in original.findall('environment') if node.findtext('id') == 'issabelast18')
        self.assertEqual(semantic(environments['issabelast16'].find('optionlist')),
                         semantic(native18.find('optionlist')))
        ks = self.module.kickstart((FIXTURE / 'issabel.ks').read_text())
        self.assertIn('@^issabelast20', ks, 'Preserve the supplied ISO default unless separately authorized')

    def test_original_supported_mandatory_package_names_all_exist_on_the_actual_dvd(self):
        root = ET.fromstring(self.original)
        for version in ('16', '18', '20'):
            group = root.find("group[id='asterisk" + version + "']")
            required = {node.text.strip() for node in group.findall('packagelist/packagereq')
                        if node.get('type') == 'mandatory'}
            self.assertTrue(required)
            self.assertTrue(required <= self.names, (version, sorted(required - self.names)))
        self.module.derive_comps(self.original, self.names)

    def test_missing_mandatory_asterisk16_package_refuses_a_false_offline_choice(self):
        self.assertIn('asterisk16-core', self.names)
        with self.assertRaises(ValueError):
            self.module.derive_comps(self.original, self.names - {'asterisk16-core'})

    def test_unknown_original_source_is_refused_before_metadata_derivation(self):
        with self.assertRaises(ValueError):
            self.module.derive_comps(self.original + b'\n<!-- source drift -->\n', self.names)


class NativeSoftwareSelectionTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((FIXTURE / 'native-software-selection.py').read_text())
        original = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == 'SoftwareSelectionSpoke')
        self.original_class = original
        names = {'environment', 'environment_id', 'environment_valid', 'completed', 'ready',
                 'showable', 'txid_valid', 'on_environment_activated'}
        nodes = [copy.deepcopy(node) for node in original.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
        fixture_class = ast.ClassDef(name='NativeSelection', bases=[ast.Name(id='NativeBase', ctx=ast.Load())],
                                    keywords=[], body=nodes, decorator_list=[])

        class NativeBase:
            # RHEL8's base Spoke.sensitive is True; the actual supplied software
            # spoke has no override. No vendor program is patched to make it so.
            @property
            def sensitive(self):
                return True

        class ThreadAdapter:
            active = set()

            def get(self, name):
                return name in self.active

        class BlockedHandler:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        self.thread = ThreadAdapter()
        self.constants = types.SimpleNamespace(THREAD_CHECK_SOFTWARE='check', THREAD_PAYLOAD='payload',
                                               THREAD_SOFTWARE_WATCHER='watcher')
        namespace = dict(NativeBase=NativeBase, threadMgr=self.thread, constants=self.constants,
                         PAYLOAD_TYPE_DNF='DNF', NoSuchGroup=KeyError,
                         blockedHandler=lambda *args: BlockedHandler())
        module = ast.fix_missing_locations(ast.Module(body=[fixture_class], type_ignores=[]))
        exec(compile(module, 'actual-native-software-selection-methods', 'exec'), namespace)
        self.spoke = namespace['NativeSelection']()
        self.spoke.data = types.SimpleNamespace(packages=types.SimpleNamespace(environment='issabelast20', seen=True))
        self.spoke.payload = types.SimpleNamespace(type='DNF', base_repo='file:///native-dvd',
            environments=['issabelast20', 'issabelast18', 'issabelast16'], environment_id=lambda value: value, tx_id=1)
        self.spoke._kickstarted = True
        self.spoke._error_msgs = None
        self.spoke._tx_id = 1

    def test_seen_kickstart_default20_does_not_hide_or_lock_the_settled_native_spoke(self):
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == 'sensitive'
                             for node in self.original_class.body))
        self.assertTrue(self.spoke.data.packages.seen)
        self.assertTrue(self.spoke._kickstarted)
        self.assertTrue(self.spoke.showable)
        self.assertTrue(self.spoke.sensitive)
        self.assertTrue(self.spoke.ready)
        self.assertTrue(self.spoke.completed)

    def test_native_threads_and_absent_installation_source_temporarily_disable_readiness(self):
        for worker in ('watcher', 'payload', 'check'):
            with self.subTest(thread=worker):
                self.thread.active = {worker}
                self.assertFalse(self.spoke.ready)
        self.thread.active = set()
        self.spoke.payload.base_repo = None
        self.assertFalse(self.spoke.ready)
        self.spoke.payload.base_repo = 'file:///native-dvd'
        self.assertTrue(self.spoke.ready)
        self.spoke.payload.type = 'not-dnf'
        self.assertFalse(self.spoke.showable)

    def test_actual_native_handler_can_select_each_metadata_environment_from_default20(self):
        self.spoke._select_flag = True
        self.spoke.refresh_addons = lambda: None
        self.spoke._addon_list_box = types.SimpleNamespace(show_all=lambda: None)
        self.spoke.on_radio_button_toggled = lambda: None
        button = types.SimpleNamespace(set_active=lambda value: None)
        box = types.SimpleNamespace(get_children=lambda: [button])
        for index, identity in enumerate(self.spoke.payload.environments):
            with self.subTest(environment=identity):
                self.spoke.environment = 'issabelast20'
                self.spoke._kickstarted = True
                row = types.SimpleNamespace(get_children=lambda: [box], get_index=lambda: index)
                self.spoke.on_environment_activated(None, row)
                self.assertEqual(self.spoke.environment, identity)
                self.assertFalse(self.spoke._kickstarted)
                self.assertTrue(self.spoke.environment_valid)


class RepositoryCompsDeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='native-comps-delta-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.before = self.base / 'before/repodata'
        self.after = self.base / 'after/repodata'
        self.before.mkdir(parents=True)
        self.module = builder()
        self.original = (FIXTURE / 'original-comps.xml').read_bytes()
        self.expected = self.module.derive_comps(self.original, package_names())
        self.root = ET.Element(TAG + 'repomd')
        ET.SubElement(self.root, TAG + 'revision').text = '1716822203'
        for kind in ('primary', 'filelists', 'other', 'primary_db', 'filelists_db', 'other_db', 'modules'):
            self.record(self.before, self.root, kind, ('native-' + kind).encode(), compressed=True)
        self.record(self.before, self.root, 'group', self.original)
        self.record(self.before, self.root, 'group_gz', self.original, compressed=True)
        self.write_repomd(self.before, self.root)
        shutil.copytree(self.before.parent, self.after.parent)
        self.updated = ET.fromstring((self.after / 'repomd.xml').read_bytes())
        for kind in ('group', 'group_gz'):
            node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == kind)
            (self.after / Path(node.find(TAG + 'location').get('href')).name).unlink()
            self.updated.remove(node)
            self.record(self.after, self.updated, kind, self.expected, compressed=kind == 'group_gz')
        self.write_repomd(self.after, self.updated)

    @staticmethod
    def write_repomd(directory, root):
        (directory / 'repomd.xml').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))

    @staticmethod
    def record(directory, root, kind, raw, compressed=False):
        data = gzip.compress(raw, mtime=0) if compressed else raw
        checksum = hashlib.sha256(data).hexdigest()
        name = checksum + '-' + ('comps.xml' if kind.startswith('group') else kind + '.xml')
        name += '.gz' if compressed else ''
        (directory / name).write_bytes(data)
        record = ET.SubElement(root, TAG + 'data', type=kind)
        ET.SubElement(record, TAG + 'checksum', type='sha256').text = checksum
        if compressed:
            ET.SubElement(record, TAG + 'open-checksum', type='sha256').text = hashlib.sha256(raw).hexdigest()
        ET.SubElement(record, TAG + 'location', href='repodata/' + name)
        ET.SubElement(record, TAG + 'timestamp').text = '1716822203'
        ET.SubElement(record, TAG + 'size').text = str(len(data))
        if compressed:
            ET.SubElement(record, TAG + 'open-size').text = str(len(raw))
        return record

    def verify(self):
        return self.module.verify_repository_delta(self.before, self.after, self.expected)

    def test_only_new_comps_variants_and_repomd_change_and_original_input_is_preserved(self):
        original = {path.name: path.read_bytes() for path in self.before.iterdir()}
        self.assertTrue(self.verify())
        self.assertEqual(original, {path.name: path.read_bytes() for path in self.before.iterdir()})
        for node in self.root.findall(TAG + 'data'):
            if not node.get('type').startswith('group'):
                name = Path(node.find(TAG + 'location').get('href')).name
                self.assertEqual((self.before / name).read_bytes(), (self.after / name).read_bytes())

    def test_changed_nongroup_file_is_refused_even_if_its_record_is_not_edited(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'primary')
        path = self.after / Path(node.find(TAG + 'location').get('href')).name
        path.write_bytes(b'changed native package index')
        with self.assertRaises(ValueError):
            self.verify()

    def test_changed_nongroup_record_is_refused_even_when_its_bytes_are_unchanged(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'modules')
        node.find(TAG + 'timestamp').text = '9999999999'
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    def test_nongroup_field_serialization_order_can_change_with_all_values_and_bytes_preserved(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'primary')
        node[:] = list(reversed(list(node)))
        self.write_repomd(self.after, self.updated)
        self.assertTrue(self.verify())

    def test_unlisted_added_or_removed_file_is_refused(self):
        extra = self.after / 'unlisted-extra.xml'
        extra.write_bytes(b'unrelated output')
        with self.assertRaises(ValueError):
            self.verify()
        extra.unlink()
        original_extra = self.before / 'original-unlisted.txt'
        original_extra.write_bytes(b'original retained material')
        with self.assertRaises(ValueError):
            self.verify()

    def test_stale_compressed_group_is_refused_even_with_accurate_new_record_checksums(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group_gz')
        (self.after / Path(node.find(TAG + 'location').get('href')).name).unlink()
        self.updated.remove(node)
        self.record(self.after, self.updated, 'group_gz', self.original, compressed=True)
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    def test_missing_group_variant_is_refused(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group_gz')
        (self.after / Path(node.find(TAG + 'location').get('href')).name).unlink()
        self.updated.remove(node)
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    def test_false_group_open_checksum_or_open_size_is_refused(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group_gz')
        digest = node.find(TAG + 'open-checksum')
        saved = digest.text
        digest.text = '0' * 64
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()
        digest.text = saved
        node.find(TAG + 'open-size').text = str(len(self.expected) + 1)
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    def reject_compression_change(self, kind, compressed):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == kind)
        (self.after / Path(node.find(TAG + 'location').get('href')).name).unlink()
        self.updated.remove(node)
        self.record(self.after, self.updated, kind, self.expected, compressed=compressed)
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    def test_native_group_must_remain_uncompressed(self):
        self.reject_compression_change('group', compressed=True)

    def test_native_group_gz_must_remain_gzip(self):
        self.reject_compression_change('group_gz', compressed=False)

    def test_group_gz_requires_both_native_open_integrity_fields(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group_gz')
        for key in ('open-checksum', 'open-size'):
            with self.subTest(field=key):
                field = node.find(TAG + key)
                node.remove(field)
                self.write_repomd(self.after, self.updated)
                with self.assertRaises(ValueError):
                    self.verify()
                node.append(field)

    def test_xml_base_is_refused_on_root_record_and_location_ancestors(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group')
        for element in (self.updated, node, node.find(TAG + 'location')):
            with self.subTest(element=element.tag):
                element.set('{http://www.w3.org/XML/1998/namespace}base', 'https://foreign.invalid/')
                self.write_repomd(self.after, self.updated)
                with self.assertRaises(ValueError):
                    self.verify()
                del element.attrib['{http://www.w3.org/XML/1998/namespace}base']

    def test_escaping_metadata_path_and_duplicate_type_are_refused(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group')
        location = node.find(TAG + 'location')
        saved = location.get('href')
        location.set('href', '../escape.xml')
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()
        location.set('href', saved)
        self.updated.append(copy.deepcopy(node))
        self.write_repomd(self.after, self.updated)
        with self.assertRaises(ValueError):
            self.verify()

    @unittest.skipUnless(os.name == 'posix', 'Native POSIX metadata symlink boundary')
    def test_symlinked_metadata_file_is_refused_without_following_or_changing_it(self):
        node = next(item for item in self.updated.findall(TAG + 'data') if item.get('type') == 'group')
        path = self.after / Path(node.find(TAG + 'location').get('href')).name
        target = self.base / 'outside.xml'
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(ValueError):
            self.verify()
        self.assertEqual(target.read_bytes(), self.expected)


if __name__ == '__main__':
    unittest.main()
