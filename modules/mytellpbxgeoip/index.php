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

function mytellGeoipReadStatus($path)
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
    return mytellGeoipValidStatus($value) ? $value : null;
}

function mytellGeoipRender($status, $persian)
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
    $html .= '<p>' . ($persian ? 'داده‌های کشور IP: ' : 'IP country data: ')
        . '<a href="https://db-ip.com" target="_blank" rel="noopener noreferrer">DB-IP Country Lite</a>'
        . ' · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>'
        . '</p></div></section>';
    return $html;
}

function _moduleContent(&$smarty, $module_name)
{
    $persian = !function_exists('get_language') || get_language() === 'fa';
    return mytellGeoipRender(mytellGeoipReadStatus('/usr/share/mytellpbx-geoip/status.json'), $persian);
}
