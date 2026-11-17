"""Guarded Asternic source transformation, no PBX/database connection."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'admin-fixes/patch-asternic-direction.py'
def data_table_fixture(name, arguments, columns):
    return ('function '+name+'('+arguments+') {\n?>\n'
            "        <a name='1'></a>\n        <table width='99%' cellpadding=3 cellspacing=3 border=0 >\n"
            '<thead><tr>'+''.join('<th>fixture-'+str(number)+'</th>' for number in range(1,columns+1))+'</tr></thead>\n<?php\n'
            '    echo "</tbody>\\n";\n    echo "</table>\\n";\n\n    $cover_pdf = \'export remains outside\';\n}\n')


HOUR_TABLES = '''function asternic_distribution($appconfig) {
    if($appconfig['period']>1) {
        foreach ($dur as $chann=>$vel) {
            echo "<table>\\n<thead>";
            echo "<tr><th></th><th colspan=25>"._('Hour of day (8 means 08h00 - 08h59)')."</th></tr>\\n";
            echo "<tr><th>Date</th>";
            for ($hour=0;$hour<24;$hour++) {
                echo "<th>$hour</th>";
            }
            echo "<th>Total</th></tr></thEAD><TBODY>\\n";
            echo "</tbody></table>";
        }
    } else {
      echo "<table>\\n<thead>";
      echo "<tr><th></th><th colspan=25>"._('Hour of day (8 means 08h00 - 08h59)')."</th></tr>\\n";
      echo "<tr><th>User</th>";
      for ($hour=0;$hour<24;$hour++) {
         echo "<th>$hour</th>";
      }
      echo "<th>"._('total')."</th></tr></thead><tbody>\\n";
      echo "</table>";
    }
}
'''


PAGE = '''<?php
require_once(dirname(__FILE__) . '/functions.inc.php');
// Owner material is preserved.
''' + '\n'.join('$query .= "AND ' + condition + ' ";' for condition in ("dst LIKE '9%'", "src REGEXP '^[0-9]{7,11}$'") for _ in range(3)) + '''
$extra_where = " AND dst LIKE '9%'";
$extra_where = " AND src REGEXP '^[0-9]{7,11}$'";
''' + HOUR_TABLES + data_table_fixture('inbound_outbound','$type,$appconfig',12) + data_table_fixture('asternic_report','$typereport,$appconfig',10) + '''
function asternic_home($appconfig) {
 $sql = "SELECT if(j1.dial is not null and j2.dial is null,'outbound',''),if(j1.dial is null and j2.dial is not null,'inbound',''),if(j1.dial is not null and j2.dial is not null,'internal','')";
}
'''
FUNCTIONS = '''<?php
function asternic_getrecords( $MYVARS ,$appconfig) {
 $condicionextra .= " AND dst LIKE '9%'";
 $condicionextra .= " AND src REGEXP '^[0-9]{7,11}$'";
    if($gtype=='combined') {
        $query  = "SELECT substring(channel,1,1) FROM asteriskcdrdb.cdr";
    }
            // --- فیلتر تماس‌های خارجی برای تب Combined ---
            if (preg_match('/^9[0-9]*/', $dst) || preg_match('/^[0-9]{7,11}$/', $src)) { $is_external = true; }
            // --- پایان فیلتر خارجی ---
 // Existing ACL/date/BUSY/export material is preserved.
}
''' + (ROOT / 'tests/fixtures/asternic-fancy-table.php').read_text(encoding='utf-8')[len('<?php'):]


def installed_fixture(root):
    root.mkdir()
    (root / 'module.xml').write_text('<module><version>1.6.6</version></module>')
    (root / 'page.asternic_cdr.php').write_text(PAGE, encoding='utf-8')
    (root / 'functions.inc.php').write_text(FUNCTIONS, encoding='utf-8')


class AsternicDirectionPatcherTests(unittest.TestCase):
    def load(self):
        self.assertTrue(PATH.is_file(), 'Asternic direction patcher missing')
        spec = importlib.util.spec_from_file_location('asternic_direction_patch', str(PATH))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_unknown_page_and_function_sources_fail_before_changes(self):
        patcher = self.load()
        for transform in (patcher.transform_page, patcher.transform_functions):
            with self.subTest(transform=transform.__name__):
                with self.assertRaises(ValueError): transform('<?php // unfamiliar optional report module\n')

    def test_planning_missing_optional_module_is_explicit_and_non_mutating(self):
        patcher = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'missing-module'
            self.assertEqual(patcher.plan(root), {})
            self.assertFalse(root.exists())

    def test_all_direction_gates_are_shared_idempotent_and_preserve_owner_material(self):
        patcher = self.load()
        for source, transform in ((PAGE, patcher.transform_page), (FUNCTIONS, patcher.transform_functions)):
            for newline in ('\n', '\r\n'):
                with self.subTest(transform=transform.__name__, newline=newline):
                    candidate = transform(source.replace('\n', newline))
                    self.assertEqual(candidate, transform(candidate))
                    self.assertNotIn("dst LIKE '9%'", candidate)
                    self.assertNotIn("src REGEXP '^[0-9]{7,11}$'", candidate)
                    self.assertIn('preserved.', candidate)
                    self.assertEqual(candidate.count('mytell-direction.php'), 1)
                    self.assertIn("asternic_mytel_direction_sql($db, 'incoming')", candidate)
                    self.assertIn("asternic_mytel_direction_sql($db, 'outgoing')", candidate)

    def test_changed_anchor_or_partial_marker_is_rejected(self):
        patcher = self.load()
        for source, transform in ((PAGE, patcher.transform_page), (FUNCTIONS, patcher.transform_functions)):
            with self.assertRaises(ValueError): transform(source.replace("dst LIKE '9%'", "dst LIKE '7%'", 1))
            candidate = transform(source)
            with self.assertRaises(ValueError): transform(candidate.replace(patcher.END, 'unrecognized marker', 1))
            with self.assertRaises(ValueError): transform(candidate.replace("direction_sql($db, 'incoming')", "direction_sql($db, 'unknown')", 1))

    def test_only_native_data_tables_get_accessible_intrinsic_width_scroll_regions(self):
        patcher=self.load();candidate=patcher.transform_page(PAGE)
        self.assertEqual(candidate.count('mt-cdr-data-scroll'),2,'Populated native data tables need local scroll regions')
        for width,columns in ((960,12),(800,10)):
            self.assertTrue('min-width: '+str(width)+'px' in candidate,'Native header count must determine intrinsic width')
            self.assertTrue("data-mt-cdr-columns='"+str(columns)+"'" in candidate)
        self.assertEqual(candidate.count("mt-cdr-data-scroll' tabindex='0' role='region'"),2)
        self.assertEqual(candidate.count('<th>fixture-'),22)
        self.assertEqual(candidate.count("<a name='1'></a>"),2)
        self.assertEqual(candidate.count('echo "</div>\\n";\n\n    $cover_pdf'),2,'Exports stay outside the data scroll region')
        self.assertEqual(candidate,patcher.transform_page(candidate))

    def test_changed_native_header_count_requires_review(self):
        patcher=self.load()
        with self.assertRaises(ValueError):patcher.transform_page(PAGE.replace('<th>fixture-12</th>','',1))

    def test_hour_data_grids_have_twenty_six_column_scroll_regions_in_both_branches(self):
        patcher=self.load();candidate=patcher.transform_page(PAGE)
        self.assertEqual(candidate.count('mt-cdr-hour-scroll'),2)
        self.assertEqual(candidate.count("data-mt-cdr-columns='26'"),2)
        self.assertEqual(candidate.count('min-width: 1040px'),2)
        self.assertEqual(candidate.count("mt-cdr-hour-scroll' tabindex='0' role='region'"),2)
        self.assertEqual(candidate.count('colspan=25'),2)
        self.assertEqual(candidate,patcher.transform_page(candidate))

    def test_changed_hour_grid_span_requires_review(self):
        patcher=self.load()
        with self.assertRaises(ValueError):patcher.transform_page(PAGE.replace('colspan=25','colspan=24',1))

    def test_pdf_data_cells_cast_scalars_without_changing_csv_or_format(self):
        patcher=self.load();candidate=patcher.transform_functions(FUNCTIONS)
        original="$this->Cell($w[$contador],6,$valor,'LR',0,'C',$fill);"
        fixed="$this->Cell($w[$contador],6,(string)$valor,'LR',0,'C',$fill);"
        self.assertTrue(fixed in candidate,'Legacy FPDF must receive string zero at the data-cell boundary')
        self.assertNotIn(original,candidate)
        source_pdf=FUNCTIONS.split('class PDF extends FPDF',1)[1]
        candidate_pdf=candidate.split('class PDF extends FPDF',1)[1]
        self.assertEqual(candidate_pdf,source_pdf.replace(original,fixed,1))
        self.assertEqual(candidate,patcher.transform_functions(candidate))

    def test_unknown_pdf_cell_boundary_requires_review(self):
        patcher=self.load()
        with self.assertRaises(ValueError):patcher.transform_functions(FUNCTIONS.replace("6,$valor,'LR',0,'C'","6,$valor,'LR',1,'R'",1))

    @unittest.skipUnless(shutil.which('php'), 'Native PHP CLI required')
    def test_derived_pdf_cells_execute_with_the_legacy_php_comparison(self):
        patcher=self.load()
        with tempfile.TemporaryDirectory() as directory:
            candidate=Path(directory)/'candidate-functions.php'
            candidate.write_text(patcher.transform_functions(FUNCTIONS),encoding='utf-8')
            result=subprocess.run([shutil.which('php'),'-n',str(ROOT/'tests/ui/asternic-pdf-zero.php'),str(candidate)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(result.returncode,0,result.stdout.decode('utf-8','replace')+result.stderr.decode('utf-8','replace'))

    def test_plan_refuses_other_versions_and_unknown_existing_helper(self):
        patcher = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'module'; installed_fixture(root)
            (root / 'module.xml').write_text('<module><version>1.6.7</version></module>')
            with self.assertRaises(ValueError): patcher.plan(root)
            (root / 'module.xml').write_text('<module><version>1.6.6</version></module>')
            (root / 'mytell-direction.php').write_text('<?php // unknown owner customization')
            with self.assertRaises(ValueError): patcher.plan(root)

    @unittest.skipIf(os.name == 'nt', 'Target POSIX symlink operations')
    def test_broken_optional_module_link_is_rejected_instead_of_reported_absent(self):
        patcher=self.load()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'module';root.symlink_to(base/'missing-target', target_is_directory=True)
            with self.assertRaises(ValueError):patcher.plan(root)

    @unittest.skipIf(os.name == 'nt', 'Target POSIX descriptor operations')
    def test_apply_preserves_backups_and_rejects_source_changes_since_plan(self):
        patcher = self.load()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'module';installed_fixture(root)
            changes=patcher.plan(root)
            page=root/'page.asternic_cdr.php'
            original=page.read_bytes();page.write_bytes(original+b'\n// Later owner change\n')
            with self.assertRaises(ValueError): patcher.apply(changes,base/'backups')
            self.assertIn(b'Later owner change',page.read_bytes())

    @unittest.skipIf(os.name == 'nt', 'Target POSIX descriptor operations')
    def test_apply_is_resumable_and_does_not_follow_source_symlinks(self):
        patcher=self.load()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'module';installed_fixture(root)
            original=(root/'page.asternic_cdr.php').read_bytes();changes=patcher.plan(root)
            backup=patcher.apply(changes,base/'backups')
            self.assertEqual((backup/'page.asternic_cdr.php').read_bytes(),original)
            self.assertEqual(patcher.plan(root),changes)
            patcher.apply(patcher.plan(root),base/'backups')
            target=root/'page.asternic_cdr.php';target.unlink();target.symlink_to(base/'unrelated')
            with self.assertRaises(ValueError):patcher.plan(root)

    @unittest.skipIf(os.name == 'nt', 'Target POSIX descriptor operations')
    def test_parent_substitution_cannot_redirect_the_original_bound_plan(self):
        patcher=self.load()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);parent=base/'modules';parent.mkdir();root=parent/'asternic_cdr';installed_fixture(root)
            changes=patcher.plan(root);substitute=base/'substitute';substitute.mkdir()
            shutil.copytree(str(root),str(substitute/'asternic_cdr'))
            parent.rename(base/'original-modules');parent.symlink_to(substitute,target_is_directory=True)
            with self.assertRaises(ValueError):patcher.apply(changes,base/'backups')

    @unittest.skipIf(os.name == 'nt', 'Target POSIX descriptor operations')
    def test_replaced_real_module_directory_cannot_inherit_a_previous_plan(self):
        patcher=self.load()
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'module';installed_fixture(root)
            changes=patcher.plan(root);replacement=base/'replacement';shutil.copytree(str(root),str(replacement))
            root.rename(base/'original-module');replacement.rename(root)
            with self.assertRaises(ValueError):patcher.apply(changes,base/'backups')

    def test_main_and_bundle_require_direction_runtime_dependencies(self):
        native = (ROOT / 'installer/native-addons.py').read_text(encoding='utf-8')
        self.assertIn('patch-asternic-direction.py', native, 'Shared native addon hook missing')
        self.assertIn('native-addons.py', (ROOT / 'installer/install-mytel-addons.sh').read_text(encoding='utf-8'))
        bundle = (ROOT / 'scripts/build-installer-bundle.sh').read_text(encoding='utf-8')
        for name in ('patch-asternic-direction.py', 'asternic-direction.php', 'licenses/GPL-3.0.txt'):
            self.assertTrue('copy_path "admin-fixes/' + name + '"' in bundle, 'Bundle dependency missing: ' + name)

    def test_optional_installer_hook_skips_absent_module_and_propagates_source_failure(self):
        spec=importlib.util.spec_from_file_location('native_addons_asternic',str(ROOT/'installer/native-addons.py'))
        native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        with tempfile.TemporaryDirectory() as directory:
            web=Path(directory)/'web'
            self.assertEqual(native.optional_asternic_plan(ROOT,web),{})
            self.assertFalse(web.exists())
            module=web/'admin/modules/asternic_cdr';module.parent.mkdir(parents=True)
            installed_fixture(module)
            changes=native.optional_asternic_plan(ROOT,web)
            self.assertIn(module/'mytell-direction.php',changes)
            (module/'module.xml').write_text('<module><version>1.6.7</version></module>')
            before=(module/'page.asternic_cdr.php').read_bytes()
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                native.optional_asternic_plan(ROOT,web)
            self.assertEqual((module/'page.asternic_cdr.php').read_bytes(),before)


if __name__ == '__main__': unittest.main()
