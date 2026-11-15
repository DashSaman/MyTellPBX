<?php
/* SPDX-License-Identifier: GPL-3.0-or-later
 * MyTellPBX Asternic CDR direction policy.
 * Copyright (C) 2026 MyTellPBX contributors.
 * Asternic CDR Reports is Copyright Nicolas Gudino and contributors.
 * Distributed WITHOUT ANY WARRANTY; see admin-fixes/licenses/GPL-3.0.txt
 * and https://www.gnu.org/licenses/gpl-3.0.html.
 * Reporting only: no CDR, dialplan, trunk or account changes are performed.
 */

function asternic_mytel_direction_literal($value) {
    return "X'" . bin2hex($value) . "'";
}

function asternic_mytel_direction_metadata($value) {
    if (!is_string($value) || $value === '' || strlen($value) > 255
        || preg_match('/[\x00-\x1f\x7f]/', $value)) {
        throw new InvalidArgumentException('Invalid CDR direction metadata');
    }
    return $value;
}

function asternic_mytel_direction_record_pattern($dial) {
    $dial = asternic_mytel_direction_metadata($dial);
    if (preg_match('~^Local/(.+)@([^/]+)(/[njb]+)?$~D', $dial, $match)) {
        return '^' . preg_quote('Local/'.$match[1].'@'.$match[2], '~') . '-[0-9a-fA-F]{8};[12]$';
    }
    if (!preg_match('~^(SIP|PJSIP|IAX2|DAHDI|Zap)/([^/&,;]+)$~D', $dial, $match)) {
        throw new InvalidArgumentException('Unsupported CDR device dial identity');
    }
    $suffix = in_array($match[1], array('SIP','PJSIP'), true) ? '[0-9a-fA-F]{8}' : '[0-9a-fA-F]+';
    return '^' . preg_quote($dial, '~') . '(-' . $suffix . ')?$';
}

function asternic_mytel_direction_regexp($field, $patterns) {
    if (!$patterns) return '(0=1)';
    return '(CAST(COALESCE(' . $field . ",'') AS BINARY) REGEXP "
        . asternic_mytel_direction_literal(implode('|', array_unique($patterns))) . ')';
}

function asternic_mytel_direction_predicates($trunks, $devices) {
    if (!is_array($trunks) || !is_array($devices) || count($trunks) > 4096 || count($devices) > 16384) {
        throw new InvalidArgumentException('Invalid CDR direction catalog');
    }
    $internal = array(); $internalIdentities = array();
    foreach ($devices as $device) {
        if (!is_array($device) || !isset($device['dial'])) throw new InvalidArgumentException('Invalid CDR device row');
        foreach (explode('&', asternic_mytel_direction_metadata($device['dial'])) as $dial) {
            $dial = trim($dial); $internalIdentities[$dial] = true;
            $internal[] = asternic_mytel_direction_record_pattern($dial);
        }
    }
    $records = array(); $targets = array();
    $technologies = array('sip'=>'SIP','pjsip'=>'PJSIP','iax'=>'IAX2','iax2'=>'IAX2','dahdi'=>'DAHDI','zap'=>'Zap');
    foreach ($trunks as $trunk) {
        if (!is_array($trunk) || !isset($trunk['tech'], $trunk['channelid'])) throw new InvalidArgumentException('Invalid CDR trunk row');
        $technology = strtolower(asternic_mytel_direction_metadata($trunk['tech']));
        $identity = asternic_mytel_direction_metadata($trunk['channelid']);
        if ($technology === 'custom') {
            // FreePBX custom trunks replace the documented $OUTNUM$ token.
            // Other executable/dynamic expressions cannot prove a destination.
            if (substr_count($identity, '$OUTNUM$') > 1 || preg_match('/[$\{\}]/', str_replace('$OUTNUM$', '', $identity)))
                throw new InvalidArgumentException('Unsupported dynamic custom trunk');
            $custom = implode('[^/@&,;]+', array_map(function ($part) { return preg_quote($part, '~'); }, explode('$OUTNUM$', $identity)));
            if (preg_match('~^Local/([^@]+)@([^/&,;]+)(/[njb]+)?$~D', $identity, $parts)) {
                if (strpos($parts[2], '$') !== false) throw new InvalidArgumentException('Dynamic custom context cannot prove a trunk');
                $number = implode('[^/@&,;]+', array_map(function ($part) { return preg_quote($part, '~'); }, explode('$OUTNUM$', $parts[1])));
                $base = 'Local/' . $number . '@' . preg_quote($parts[2], '~');
                $records[] = '^' . $base . '-[0-9a-fA-F]{8};[12]$';
            } else {
                if (preg_match('~^(SIP|PJSIP|IAX2|DAHDI|Zap)/([^/&,;@]+)/([^&,;]+)$~D', $identity, $parts)) {
                    $name = $parts[1]; $endpoint = $parts[2];
                } elseif (preg_match('~^(SIP|PJSIP|IAX2)/[^/@&,;]+@([^/&,;]+)(/[^&,;]+)?$~D', $identity, $parts)) {
                    $name = $parts[1]; $endpoint = $parts[2];
                } else throw new InvalidArgumentException('Unsupported custom trunk dial identity');
                if (strpos($endpoint, '$') !== false) throw new InvalidArgumentException('Dynamic endpoint cannot prove a trunk');
                $base = $name . '/' . $endpoint;
                if (isset($internalIdentities[$base])) continue;
                if (!in_array($name, array('DAHDI','Zap'), true) || ctype_digit($endpoint))
                    $records[] = asternic_mytel_direction_record_pattern($base);
            }
            $targets[] = '(^|&)' . $custom . '(&|$)';
            continue;
        }
        if (!isset($technologies[$technology]) || preg_match('~[/&,;@]~', $identity))
            throw new InvalidArgumentException('Unsupported trunk technology or identity');
        $name = $technologies[$technology]; $base = $name . '/' . $identity;
        if (isset($internalIdentities[$base])) continue;
        // DAHDI group selectors identify Dial attempts, not physical channels.
        if (!in_array($name, array('DAHDI','Zap'), true) || ctype_digit($identity))
            $records[] = asternic_mytel_direction_record_pattern($base);
        $targets[] = '(^|&)' . preg_quote($base, '~') . '(/[^&]+)?(&|$)';
        if (in_array($name, array('SIP','PJSIP','IAX2'), true))
            $targets[] = '(^|&)' . preg_quote($name, '~') . '/[^&@/]+@' . preg_quote($identity, '~') . '(/[^&]+)?(&|$)';
    }
    // All configured devices are separate from checkRange()/selected canals.
    // An unauthorized internal or a peer-name collision is never external.
    $sourceInternal = asternic_mytel_direction_regexp('channel', $internal);
    $destinationInternal = asternic_mytel_direction_regexp('dstchannel', $internal);
    $sourceTrunk = asternic_mytel_direction_regexp('channel', $records);
    $destinationTrunk = asternic_mytel_direction_regexp('dstchannel', $records);
    $dialTarget = asternic_mytel_direction_regexp("SUBSTRING_INDEX(lastdata,',',1)", $targets);
    $outgoing = '(NOT ' . $destinationInternal . ' AND (' . $destinationTrunk
        . " OR (COALESCE(lastapp,'')='Dial' AND " . $dialTarget . ')))';
    // Outbound forwarding wins when both sides are trunks; rows are not merged.
    $incoming = '(NOT ' . $outgoing . ' AND NOT ' . $sourceInternal . ' AND ' . $sourceTrunk . ')';
    $local = '(' . $sourceInternal . ' AND ' . $destinationInternal . ' AND NOT ' . $outgoing . ')';
    return array('outgoing'=>$outgoing,'incoming'=>$incoming,'internal'=>$local,
                 'external'=>'(' . $outgoing . ' OR ' . $incoming . ')');
}

function asternic_mytel_direction_sql($db, $direction) {
    static $catalogs;
    if ($catalogs === null) $catalogs = new SplObjectStorage();
    if (!in_array($direction, array('outgoing','incoming','internal','external'), true))
        throw new InvalidArgumentException('Unknown CDR direction');
    if (!is_object($db) || !method_exists($db, 'getAll')) throw new InvalidArgumentException('CDR metadata connection required');
    if (!$catalogs->contains($db)) {
        try {
            $mode = defined('DB_FETCHMODE_ASSOC') ? DB_FETCHMODE_ASSOC : 2;
            $trunks = $db->getAll('SELECT tech,channelid FROM asterisk.trunks', $mode);
            $devices = $db->getAll('SELECT dial FROM asterisk.devices', $mode);
            $catalogs[$db] = asternic_mytel_direction_predicates($trunks, $devices);
        } catch (Exception $error) {
            if (PHP_SAPI === 'cli') throw $error;
            error_log('Asternic CDR direction metadata unavailable');
            if (!headers_sent()) http_response_code(500);
            exit('خواندن اطلاعات مسیر تماس ناموفق بود؛ مدیر سامانه باید تنظیمات ترانک را بررسی کند.');
        }
    }
    return $catalogs[$db][$direction];
}
