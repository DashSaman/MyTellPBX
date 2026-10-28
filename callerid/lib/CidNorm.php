<?php
/**
 * MyTellPBX Caller-ID normalization library (Iranian profile).
 *
 * Single implementation shared by the AGI runtime, the panel preview
 * tester, and the test suite.  Behavior is an independent reimplementation
 * of the public "voipiran voiz-asterisk-callerid-formatter" concept
 * (https://github.com/voipiran/voiz-asterisk-callerid-formatter) — that
 * repository carries no license, so no code is copied from it; only the
 * behavior concept is referenced with attribution.
 *
 * Policy (mission 2026-10-28 §6, GPT decision 3 D1):
 *  - Bounded, validated rewrites only; ambiguous inputs pass through
 *    unchanged; foreign numbers, short/service numbers, empty/anonymous
 *    identities are preserved.
 *  - Idempotent by contract: normalize(normalize(x)) === normalize(x).
 *  - Provider quirks (leading 0000 / 002198 and the 21098 echo) are
 *    EXPLICIT profiles, disabled by default.
 *
 * PHP 7.4 compatible (no modern syntax beyond 7.4).
 *
 * @license GPL-2.0 (MyTellPBX project)
 */

namespace MyTellPBX\Cid;

final class CidNorm
{
    /** Iranian mobile: 10 digits starting with 9, or 11 starting 09x. */
    const RE_MOBILE_10 = '/^9\d{9}$/';
    const RE_MOBILE_11 = '/^09\d{9}$/';

    /** Tehran-family trunk rewrites (validated patterns, upstream concept). */
    const TEHRAN_RULES = array(
        13 => '210',   // 210XXXXXXXXX -> 0 + rest
        15 => '21098', // carrier echo 21098XXXXXXXXXX -> 0 + rest
    );

    /** Valid Iranian area-code prefixes (2-digit form, without leading 0). */
    const AREA_PREFIXES = array(
        '11','13','17','21','23','24','25','26','28','31','34','35','38',
        '41','44','45','51','54','56','58','61','66','71','74','76','77',
        '81','83','84','86','87',
    );

    /** Anonymous / privacy marker strings that must never be rewritten. */
    const ANON_WORDS = array(
        'anonymous','private','withheld','unavailable','unknown','blocked',
        'no caller id','cid withheld','restricted','',
    );

    /**
     * Normalize a caller number string.
     *
     * @param string $raw
     * @param array  $opts  'quirks' => bool  enable provider-quirk profiles
     * @return array{num:string, changed:bool, note:string}
     */
    public static function normalize($raw, array $opts = array())
    {
        $quirks = !empty($opts['quirks']);
        $rawText = self::toAsciiDigits(trim((string)$raw));

        // Anonymous / privacy / empty: preserve untouched.
        $lower = strtolower($rawText);
        if (in_array($lower, self::ANON_WORDS, true) || $rawText === '') {
            return array('num' => (string)$raw, 'changed' => false,
                         'note' => 'preserved-anonymous');
        }

        // Non-numeric or SIP-ish identity: preserve.
        if (preg_match('/[^0-9+]/', $rawText)) {
            return array('num' => (string)$raw, 'changed' => false,
                         'note' => 'preserved-non-numeric');
        }

        // Work on pure digits from here on.
        $d = ltrim($rawText, '+');
        $orig = $d;

        // Optional provider-quirk profiles (explicit, default off). They
        // run BEFORE the foreign-preservation check because the quirk
        // strings (0000/002198) otherwise look like 00-CC foreign forms.
        // Bounded: only when a plausible national number remains.
        $quirkStripped = false;
        if ($quirks) {
            if (strpos($d, '0000') === 0 && strlen($d) - 4 >= 10) {
                $d = substr($d, 4);
                $quirkStripped = true;
            } elseif (strpos($d, '002198') === 0 && strlen($d) - 6 >= 10) {
                $d = substr($d, 6);
                $quirkStripped = true;
            }
        }

        // Foreign international (leading + or 00 with non-98 CC): preserve.
        // A quirk-stripped number is by definition domestic; skip the gate.
        if (!$quirkStripped) {
            $digits = ltrim($rawText, '+');
            if (strpos($rawText, '+') === 0 || strpos($digits, '00') === 0) {
                $ccPart = self::countryCodeOf($digits);
                if ($ccPart !== '98') {
                    return array('num' => (string)$raw, 'changed' => false,
                                 'note' => 'preserved-foreign');
                }
            }
        }

        // Iranian country-prefix strips, each bounded by validated length.
        if (strpos($d, '0098') === 0 && strlen($d) === 14) {
            $d = substr($d, 4);
        } elseif (strpos($d, '098') === 0 && strlen($d) === 13) {
            $d = substr($d, 3);
        } elseif (strpos($d, '98') === 0 && strlen($d) === 12) {
            $d = substr($d, 2);
        }

        // Already-normalized national forms: idempotence fast-path.
        if (preg_match(self::RE_MOBILE_11, $d)) {
            return self::result($raw, $d, $orig, 'mobile-11');
        }
        if (strlen($d) === 11 && $d[0] === '0'
            && in_array(substr($d, 0, 2), self::areaCodesWithZero(), true)) {
            return self::result($raw, $d, $orig, 'landline-11');
        }

        // Mobile: 10 digits starting 9 -> prepend 0.
        if (preg_match(self::RE_MOBILE_10, $d)) {
            $d = '0' . $d;
            return self::result($raw, $d, $orig, 'mobile-10');
        }

        // Tehran-family trunk rewrites (explicit validated patterns).
        foreach (self::TEHRAN_RULES as $len => $prefix) {
            if (strlen($d) === $len && strpos($d, $prefix) === 0) {
                $d = '0' . substr($d, strlen($prefix));
                return self::result($raw, $d, $orig, 'tehran-' . $prefix);
            }
        }

        // Landline without leading 0: 10 digits starting with a valid
        // area prefix -> prepend 0. Ambiguous tails stay untouched.
        if (strlen($d) === 10 && in_array(substr($d, 0, 2), self::AREA_PREFIXES, true)) {
            $d = '0' . $d;
            return self::result($raw, $d, $orig, 'landline-10');
        }

        // Everything else (short codes, 8-digit ambiguous tails, unknown
        // shapes, foreign that slipped prefix checks): unchanged.
        return self::result($raw, $orig, $orig, 'passthrough');
    }

    private static function result($raw, $num, $orig, $note)
    {
        return array(
            'num' => $num,
            'changed' => ((string)$raw !== $num) && ($orig !== $num || (string)$raw !== $num),
            'note' => $note,
        );
    }

    private static function countryCodeOf($digits)
    {
        // Minimal CC reader for the preserve-foreign decision: 00-prefixed
        // forms carry CC after "00"; "+" forms carry CC directly. Only the
        // Iran check matters here (98); any other CC preserves as foreign.
        if (strpos($digits, '00') === 0) {
            $digits = substr($digits, 2);
        }
        if (strpos($digits, '98') === 0) {
            return '98';
        }
        return 'other';
    }

    public static function areaCodesWithZero()
    {
        $out = array();
        foreach (self::AREA_PREFIXES as $p) {
            $out[] = '0' . $p;
        }
        return $out;
    }

    /** Persian/Arabic-Indic digits and common separators to ASCII digits. */
    public static function toAsciiDigits($s)
    {
        $fa = array('۰','۱','۲','۳','۴','۵','۶','۷','۸','۹');
        $ar = array('٠','١','٢','٣','٤','٥','٦','٧','٨','٩');
        $en = array('0','1','2','3','4','5','6','7','8','9');
        $s = str_replace($fa, $en, $s);
        $s = str_replace($ar, $en, $s);
        // separators are tolerated only between digits, never leading.
        return preg_replace('/(?<=\d)[ \-.()]+(?=\d)/', '', $s);
    }
}
