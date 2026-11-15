<?php
/* Actual Smarty rendering against an isolated synthetic web root; no framework boot. */
if (PHP_SAPI !== 'cli') exit(1);
$options = getopt('', array('smarty:', 'fixture:', 'case:'));
require $options['smarty'];
$root = $options['fixture'];
$web = $root . '/web';
mkdir($web, 0700, true);
$case = $options['case'];
if ($case !== 'absent') mkdir($web . '/Phone', 0700);
if ($case === 'html') file_put_contents($web . '/Phone/index.html', 'synthetic installed entry');
if ($case === 'php') file_put_contents($web . '/Phone/index.php', '<?php /* fixture, never executed */');
if ($case === 'assets') file_put_contents($web . '/Phone/workspace.css', '/* polish without a product */');
if ($case === 'dangling') symlink($root . '/missing-entry', $web . '/Phone/index.html');
$_SERVER['DOCUMENT_ROOT'] = $web;
chdir($web);
$templates = dirname(__DIR__, 2) . '/theme/_common';
mkdir($root . '/compiled', 0700);
$defaults = array();
foreach (array('login.tpl', 'index.tpl') as $name) {
    preg_match_all('/\$([A-Za-z_][A-Za-z0-9_]*)/', file_get_contents($templates . '/' . $name), $matches);
    foreach ($matches[1] as $variable) if ($variable !== 'smarty') $defaults[$variable] = '';
}
$results = array();
foreach (array('login.tpl', 'index.tpl') as $name) {
    $smarty = new Smarty();
    $smarty->setTemplateDir($templates);
    $smarty->setCompileDir($root . '/compiled');
    $smarty->force_compile = true;
    $smarty->caching = false;
    $smarty->error_reporting = E_ALL & ~E_DEPRECATED;
    $smarty->assign(array_merge($defaults, array(
        'LANG'=>'fa', 'THEME_DIR'=>'rtl', 'WEBPATH'=>'/', 'THEMENAME'=>'mytel',
        'BRAND_NAME'=>'MyTel', 'BRAND_TAGLINE'=>'Fixture', 'MT_CAN_ENTER_DESK'=>true,
        'MT_IS_HOMEPAGE'=>true, 'ISSABEL_PANELS'=>false,
        'NOTIFICATIONS'=>array(), 'arrMainMenu'=>array(), 'BREADCRUMB'=>array(),
    )));
    $html = $smarty->fetch($name);
    $results[$name] = array(
        'phone_links'=>substr_count($html, 'href="/Phone/"'),
        'phone_cards'=>substr_count($html, 'id="mt-webphone-card"'),
        'desk_links'=>substr_count($html, 'href="/MytellDesk/"'),
        'desk_cards'=>substr_count($html, 'id="mt-desk-banner"'),
        'unexpanded'=>strpos($html, '{$') !== false,
    );
}
echo json_encode($results, JSON_UNESCAPED_SLASHES) . "\n";
