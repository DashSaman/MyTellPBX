<?php
/** Keep the first-boot vendor API while keeping secrets out of outer OS argv. */
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
$program = '/usr/bin/issabel-admin-passwords';
$input = stream_get_contents(STDIN, 65537);
$parts = explode("\n", $input);
if (strlen($input) > 65536 || count($parts) !== 3 || $parts[2] !== ''
    || !preg_match('/\A[A-Za-z0-9 .@=_!-]+\z/', $parts[0])
    || !preg_match('/\A[A-Za-z0-9 .@=_!-]+\z/', $parts[1])) {
    fwrite(STDERR, "Invalid password initialization input.\n");
    exit(2);
}
if (!is_file($program) || !is_readable($program)) {
    fwrite(STDERR, "Vendor password initialization tool unavailable.\n");
    exit(1);
}
// Require in global scope: the vendor defines globals used by its functions and
// parses this array with Console_Getopt. No vendor source is patched or eval'd.
$argv = array($program, '--cli', 'init', $parts[0], $parts[1]);
$argc = count($argv);
$_SERVER['argv'] = $argv;
$_SERVER['argc'] = $argc;
unset($input, $parts);
require $program;
