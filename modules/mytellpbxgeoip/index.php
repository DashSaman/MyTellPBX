<?php
/** MyTellPBX automatic country database status; GPL-2.0-or-later. */

function mytellGeoipValidStatus($value)
{
    if (!is_array($value) || !isset($value['schema']) || $value['schema'] !== 1) return false;
    $fixed = array('owner' => 'MyTellPBX GeoIP', 'provider' => 'DB-IP Country Lite',
        'status' => 'ready', 'layout' => 'flat-network-BE', 'license' => 'CC-BY-4.0',
        'attribution_url' => 'https://db-ip.com',
        'license_url' => 'https://creativecommons.org/licenses/by/4.0/');
    foreach ($fixed as $key => $expected) {
        if (!isset($value[$key]) || $value[$key] !== $expected) return false;
    }
    if (!isset($value['month']) || !is_string($value['month'])
        || !preg_match('/\A20[0-9]{2}-(?:0[1-9]|1[0-2])\z/', $value['month'])) return false;
    if (!isset($value['source_url']) || $value['source_url'] !==
        'https://download.db-ip.com/free/dbip-country-lite-' . $value['month'] . '.csv.gz') return false;
    if (!isset($value['source_sha256']) || !is_string($value['source_sha256'])
        || !preg_match('/\A[a-f0-9]{64}\z/', $value['source_sha256'])) return false;
    foreach (array('rows', 'ipv4_ranges', 'ipv6_ranges', 'country_count') as $key) {
        if (!isset($value[$key]) || !is_int($value[$key]) || $value[$key] < 1
            || $value[$key] > 5000000) return false;
    }
    if ($value['country_count'] > 300 || $value['rows'] !== $value['ipv4_ranges'] + $value['ipv6_ranges']) return false;
    if (!isset($value['updated_utc']) || !is_string($value['updated_utc'])) return false;
    $date = DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s\Z', $value['updated_utc'], new DateTimeZone('UTC'));
    return $date !== false && $date->format('Y-m-d\TH:i:s\Z') === $value['updated_utc'];
}

function mytellGeoipValidModuleStatus($value)
{
    $keys = array('schema','owner','module','state','running_kernel','target_kernel','loaded','persistent','module_sha256');
    if (!is_array($value) || count($value) !== count($keys)
        || count(array_diff_key($value, array_fill_keys($keys, true))) !== 0) return false;
    if ($value['schema'] !== 'mytellpbx-geoip-module/1' || $value['owner'] !== 'MyTellPBX'
        || $value['module'] !== 'xt_geoip'
        || !in_array($value['state'], array('ready','pending-reboot','unavailable'), true)
        || !is_bool($value['loaded']) || !is_bool($value['persistent'])) return false;
    foreach (array('running_kernel','target_kernel') as $key) {
        if ($key === 'target_kernel' && $value[$key] === null) continue;
        if (!is_string($value[$key]) || !preg_match('/\A[A-Za-z0-9][A-Za-z0-9._+-]{1,127}\z/', $value[$key])) return false;
    }
    if ($value['module_sha256'] !== null && (!is_string($value['module_sha256'])
        || !preg_match('/\A[a-f0-9]{64}\z/', $value['module_sha256']))) return false;
    if ($value['state'] === 'ready') return $value['loaded'] && $value['persistent']
        && $value['target_kernel'] === $value['running_kernel'] && $value['module_sha256'] !== null;
    if ($value['state'] === 'pending-reboot') return !$value['loaded'] && $value['persistent']
        && $value['target_kernel'] !== null && $value['target_kernel'] !== $value['running_kernel']
        && $value['module_sha256'] !== null;
    return true;
}

function mytellGeoipConsumerState($status, $kernel, $loaded)
{
    if (!mytellGeoipValidModuleStatus($status) || !is_bool($loaded) || !is_string($kernel)
        || !preg_match('/\A[A-Za-z0-9][A-Za-z0-9._+-]{1,127}\z/', $kernel)) return 'unknown';
    if ($status['state'] === 'unavailable') return 'unavailable';
    if ($loaded) {
        // A pending receipt can become ready after the exact verified target
        // kernel boots. Country-data readiness is never a module-load proof.
        return $status['target_kernel'] === $kernel ? 'ready' : 'unknown';
    }
    if ($status['state'] === 'pending-reboot' && $status['running_kernel'] === $kernel
        && $status['target_kernel'] !== $kernel) return 'pending-reboot';
    return 'unavailable';
}

function mytellGeoipReadStatus($path, $module = false)
{
    // This is a public, non-secret receipt. Refuse writable or redirected inputs.
    $parent = dirname($path);
    $meta = @lstat($path);
    $directory = @lstat($parent);
    if ($meta === false || $directory === false || is_link($path) || is_link($parent)
        || ($meta['mode'] & 0170000) !== 0100000 || ($directory['mode'] & 0170000) !== 0040000
        || $meta['uid'] !== 0 || $directory['uid'] !== 0
        || ($meta['mode'] & 0022) || ($directory['mode'] & 0022)
        || $meta['size'] < 2 || $meta['size'] > 8192) return null;
    $raw = @file_get_contents($path, false, null, 0, 8193);
    if ($raw === false || strlen($raw) > 8192) return null;
    $value = json_decode($raw, true);
    $valid = $module === true ? mytellGeoipValidModuleStatus($value) : mytellGeoipValidStatus($value);
    return $valid ? $value : null;
}

function mytellGeoipRender($status, $persian, $consumer = null, $kernel = null, $loaded = false)
{
    $title = $persian ? 'پایگاه دادهٔ کشورها' : 'IP country database';
    $description = $persian ? 'داده‌های کشورها به‌صورت خودکار به‌روز می‌شوند و به کلید یا ثبت‌نام نیاز ندارند.'
        : 'Country data updates automatically. No license key or signup is required.';
    $html = '<section class="panel panel-default"><div class="panel-heading"><h2 class="panel-title">'
        . $title . '</h2></div><div class="panel-body"><p>' . $description . '</p>';
    if (!mytellGeoipValidStatus($status)) {
        $html .= '<p role="status">' . ($persian ? 'پایگاه داده هنوز آماده نیست. پس از تکمیل نصب، وضعیت اینجا نمایش داده می‌شود.'
            : 'The database is not ready yet. Its status appears here after installation completes.') . '</p>';
    } else {
        $labels = $persian ? array('وضعیت', 'نسخهٔ داده', 'تعداد کشورها', 'بازه‌های IPv4', 'بازه‌های IPv6')
            : array('Status', 'Dataset version', 'Countries', 'IPv4 ranges', 'IPv6 ranges');
        $values = array($persian ? 'آماده' : 'Ready', $status['month'], $status['country_count'],
            $status['ipv4_ranges'], $status['ipv6_ranges']);
        $html .= '<dl class="dl-horizontal">';
        foreach ($labels as $index => $label) {
            $html .= '<dt>' . $label . '</dt><dd>' . htmlspecialchars((string)$values[$index], ENT_QUOTES, 'UTF-8') . '</dd>';
        }
        $html .= '</dl>';
    }
    $state = mytellGeoipConsumerState($consumer, $kernel, $loaded);
    $labels = $persian
        ? array('ready'=>'آماده','pending-reboot'=>'نیاز به راه‌اندازی مجدد','unavailable'=>'در دسترس نیست','unknown'=>'وضعیت تأیید نشده')
        : array('ready'=>'Ready','pending-reboot'=>'Restart required','unavailable'=>'Unavailable','unknown'=>'Not verified');
    $details = $persian ? array(
        'ready'=>'تشخیص کشور فعال است. سیاست دسترسی را در بخش فایروال تنظیم کنید.',
        'pending-reboot'=>'برای فعال شدن تشخیص کشور، سیستم را با کرنل نصب‌شده راه‌اندازی مجدد کنید.',
        'unavailable'=>'تشخیص کشور برای سیستم فعلی آماده نیست. وضعیت نصب را بررسی کنید.',
        'unknown'=>'آمادگی تشخیص کشور برای سیستم فعلی هنوز تأیید نشده است.') : array(
        'ready'=>'Country matching is available. Configure access rules in Firewall.',
        'pending-reboot'=>'Restart into the verified installed kernel to enable country matching.',
        'unavailable'=>'Country matching is unavailable for the current system. Check installation status.',
        'unknown'=>'Country matching for the current system has not been verified.');
    $html .= '<div role="status" data-geoip-consumer-state="' . $state . '"><strong>'
        . ($persian ? 'تشخیص کشور ترافیک' : 'Traffic country matching') . ': </strong>'
        . $labels[$state] . '<p>' . $details[$state] . '</p></div>';
    $html .= '<p>' . ($persian ? 'داده‌های کشور IP: ' : 'IP country data: ')
        . '<a href="https://db-ip.com" target="_blank" rel="noopener noreferrer">DB-IP Country Lite</a>'
        . ' · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>'
        . '</p></div></section>';
    return $html;
}

function mytellGeoipNativeEvidence($root = '/')
{
    // Read-only observations of vendor-owned files. Presence and module loading
    // are not a country-lookup test or proof that a firewall rule is enforced.
    $root = rtrim($root, '/');
    $present = function ($relative) use ($root) {
        $path = $root . '/' . $relative;
        return !is_link($path) && is_file($path) && @filesize($path) > 0;
    };
    $tables = 0;
    foreach (array('usr/share/xt_geoip', 'usr/share/xt_geoip/BE', 'usr/share/xt_geoip/LE') as $relative) {
        $directory = $root . '/' . $relative;
        if (is_link($directory) || !is_dir($directory)) continue;
        foreach (array('iv4', 'iv6') as $family) {
            $files = glob($directory . '/[A-Z][A-Z].' . $family);
            if (!is_array($files)) continue;
            foreach (array_slice($files, 0, 600) as $path) {
                if (!is_link($path) && is_file($path) && @filesize($path) > 0) $tables++;
            }
        }
    }
    return array('schema' => 'mytellpbx-native-geoip/1',
        'ipv4_present' => $present('usr/share/GeoIP/GeoIP.dat'),
        'ipv6_present' => $present('usr/share/GeoIP/GeoIPv6.dat'),
        'country_table_files' => $tables,
        'module_loaded' => is_dir($root . '/sys/module/xt_geoip'));
}

function mytellGeoipNativeRender($evidence, $persian)
{
    $valid = is_array($evidence) && count($evidence) === 5
        && isset($evidence['schema']) && $evidence['schema'] === 'mytellpbx-native-geoip/1'
        && isset($evidence['ipv4_present'], $evidence['ipv6_present'], $evidence['module_loaded'], $evidence['country_table_files'])
        && is_bool($evidence['ipv4_present']) && is_bool($evidence['ipv6_present'])
        && is_bool($evidence['module_loaded']) && is_int($evidence['country_table_files'])
        && $evidence['country_table_files'] >= 0 && $evidence['country_table_files'] <= 3600;
    $title = $persian ? 'پایگاه دادهٔ کشورها' : 'IP country database';
    $description = $persian ? 'داده‌ها و به‌روزرسانی GeoIP در اختیار نصب اصلی Issabel است. این صفحه فقط وضعیت قابل مشاهده را نمایش می‌دهد.'
        : 'The native Issabel installation owns GeoIP data and updates. This page reports read-only observations.';
    $html = '<section class="panel panel-default" data-geoip-source="native"><div class="panel-heading"><h2 class="panel-title">'
        . $title . '</h2></div><div class="panel-body"><p>' . $description . '</p>';
    if ($valid) {
        $yes = $persian ? 'موجود' : 'Present';
        $no = $persian ? 'مشاهده نشد' : 'Not observed';
        $labels = $persian ? array('فایل اصلی IPv4', 'فایل اصلی IPv6', 'تعداد فایل‌های جدول کشور', 'ماژول کرنل بارگذاری‌شده')
            : array('Native IPv4 file', 'Native IPv6 file', 'Country table files', 'Kernel module loaded');
        $values = array($evidence['ipv4_present'] ? $yes : $no, $evidence['ipv6_present'] ? $yes : $no,
            (string)$evidence['country_table_files'], $evidence['module_loaded'] ? $yes : $no);
        $html .= '<dl class="dl-horizontal">';
        foreach ($labels as $index => $label) {
            $html .= '<dt>' . $label . '</dt><dd>' . htmlspecialchars($values[$index], ENT_QUOTES, 'UTF-8') . '</dd>';
        }
        $html .= '</dl>';
    }
    $html .= '<p role="status" data-geoip-consumer-state="unknown">'
        . ($persian ? 'درستی تشخیص کشور و اعمال قوانین فایروال هنوز تأیید نشده است.'
            : 'Country lookup accuracy and firewall enforcement have not been verified.')
        . '</p></div></section>';
    return $html;
}

function _moduleContent(&$smarty, $module_name)
{
    $persian = !function_exists('get_language') || get_language() === 'fa';
    // Native install is the default. Historical custom receipts alone must not
    // silently switch the current product to an older updater or claim health.
    // Managed-source render helpers remain available to an explicit integration.
    return mytellGeoipNativeRender(mytellGeoipNativeEvidence(), $persian);
}
