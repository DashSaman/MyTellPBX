<?php
/* Offline Smarty 3 smoke render. Synthetic data only; no framework bootstrap. */
if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit(1);
}
$options = getopt('', array('smarty:', 'compile-dir:'));
if (empty($options['smarty']) || empty($options['compile-dir'])) {
    fwrite(STDERR, "Usage: php render-templates.php --smarty=/path/Smarty.class.php --compile-dir=/private/new-directory\n");
    exit(2);
}
$compile = $options['compile-dir'];
if (file_exists($compile) || strpos($compile, '/var/www/') === 0 || !mkdir($compile, 0700, true)) {
    throw new RuntimeException('Use a new private compile directory outside served paths');
}
require $options['smarty'];
$directory = dirname(__DIR__, 2) . '/theme/_common';
$files = array('_menu.tpl', '_shortcut.tpl', '_list.tpl', 'index.tpl', 'login.tpl', 'popup.tpl', 'help.tpl');
$defaults = array();
foreach ($files as $file) {
    preg_match_all('/\$([A-Za-z_][A-Za-z0-9_]*)/', file_get_contents($directory . '/' . $file), $names);
    foreach ($names[1] as $name) {
        if ($name !== 'smarty') {
            $defaults[$name] = '';
        }
    }
}
$sample = array('Type' => 'module', 'Name' => 'Sample page', 'Link' => '#', 'children' => array());
$fixture = array(
    'LANG' => 'fa', 'THEME_DIR' => 'rtl', 'THEMENAME' => 'mytel', 'WEBPATH' => '/',
    'HEADER_MODULES' => '<script src="modules/calendar/themes/default/js/javascript.js"></script>',
    'BRAND_NAME' => 'MyTellPBX', 'BRAND_TAGLINE' => 'Synthetic UI fixture',
    'PAGE_NAME' => 'Sign in', 'USERNAME' => 'Username', 'PASSWORD' => 'Password',
    'SUBMIT' => 'Sign in', 'titulo' => 'Help', 'id_nodo' => 'sample', 'name_nodo' => 'sample',
    'USER_LOGIN' => 'fixture', 'MT_CAN_ENTER_DESK' => true, 'MT_IS_HOMEPAGE' => true,
    'arrMainMenu' => array('home' => array('Name' => 'Home', 'icon' => 'fa fa-home',
        'children' => array('sample' => $sample))),
    'idMainMenuSelected' => 'home', 'idSubMenuSelected' => 'sample',
    'BREADCRUMB' => array('Home', 'Sample'), 'ISSABEL_PANELS' => false,
    'NOTIFICATIONS' => array('LBL_NOTIFICATION_SYSTEM' => 'System', 'LBL_NOTIFICATION_USER' => 'User',
        'TXT_NO_NOTIFICATIONS' => 'None', 'NOTIFICATIONS_PUBLIC' => array(), 'NOTIFICATIONS_PRIVATE' => array()),
    'SHORTCUT_BOOKMARKS' => array(array('namemenu' => 'sample', 'name' => 'Sample')),
    'SHORTCUT_HISTORY' => array(array('namemenu' => 'sample', 'name' => 'Sample')),
    'arrActions' => array(), 'arrFiltersControl' => array(), 'arrData' => array(),
    'header' => array(array('name' => 'Column one'), array('name' => 'Column two')),
    'numColumns' => 2, 'numData' => 0, 'numPage' => 1, 'pagingShow' => false,
    'start' => 1, 'end' => 0, 'total' => 0, 'currentPage' => 1,
    'enableExport' => true, 'contentFilter' => '<label>Fixture filter<input name="fixture"></label>',
    'NO_DATA_FOUND' => 'No sample records', 'AS_OPTION' => false,
);
$report = array('smarty' => Smarty::SMARTY_VERSION, 'renders' => array());
foreach (array('empty', 'populated') as $mode) {
    $smarty = new Smarty();
    $smarty->setTemplateDir($directory);
    $smarty->setCompileDir($compile);
    $smarty->caching = false;
    $smarty->force_compile = true;
    $smarty->error_reporting = E_ALL & ~E_DEPRECATED;
    $smarty->assign(array_merge($defaults, $fixture));
    if ($mode === 'populated') {
        $rows = array();
        for ($i = 0; $i < 4; $i++) {
            $rows[] = array('ctrl' => '', 0 => 'Sample A', 1 => 'Sample B');
        }
        $smarty->assign('arrData', $rows);
        $smarty->assign('numData', count($rows));
    }
    foreach ($files as $file) {
        $html = $smarty->fetch($file);
        if (strlen($html) < 80 || strpos($html, '{$') !== false) {
            throw new RuntimeException('Incomplete render: ' . $file);
        }
        if ($file === '_list.tpl' && (substr_count($html, 'class="mt-table-scroll"') !== 1 ||
                strpos($html, 'form.issabel-standard-formgrid>.mt-table-scroll>table.issabel-standard-table') === false)) {
            throw new RuntimeException('List scroll/resize contract missing');
        }
        if ($file === 'index.tpl' && strpos($html, 'modules/calendar/themes/default/js/javascript.js?v=752') === false) {
            throw new RuntimeException('Native calendar cache-busting missing');
        }
        $report['renders'][] = array('template' => $file, 'fixture' => $mode, 'bytes' => strlen($html));
    }
}
echo json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
