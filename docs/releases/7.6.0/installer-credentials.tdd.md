# First-boot credential transport

This work keeps the base installer's existing initialization semantics. It does
not run against, reset or migrate the production PBX's passwords.

`tests/test_installer_credentials.py` executes the real Bash functions/call sites
with recording clients and disposable files. The original source produced four
runtime failures at `3f9ec17`: root authentication, temporary-password SQL, admin
SQL and the vendor initializer exposed the fixture credentials in client argv.
`b51074b` added an executed reproducer for the old regex password check accepting
a different value at a dot and duplicate keys. The subsequent five-case target
passed with environment authentication, SQL stdin and exact read-only checking.

The fixed vendor API is PHP using `Console_Getopt::getopt($argv)`. Its source was
inspected read-only, never executed. The new `installer/password-init.php` adapter
receives two validated stdin lines, establishes the equivalent global PHP argv,
argc and server argv, then requires that fixed vendor file in global scope.
Neither password is an argument of the outer operating-system process.

The PHP fixture first executed RED for the missing new adapter. GREEN uses only
an owned fake vendor with the fixed target substituted in a private test copy.
It checks exact arguments, spaces/punctuation, `/proc/self/cmdline`, error exit
propagation and rejection of malformed input. The real vendor, databases and
services are not executed by this fixture. Final Linux/PHP counts are retained
in the release verification record.

Independent PHP 7.4 execution of tree
`0362b2dd52795f3f6097e24b24fd6850702c9dce` passed all 62 checks: the existing
54 guards plus all eight credential transport checks. The runner used uid 65534,
private networking and no access to PBX application files or databases. The
realistic executable vendor fixture emits its shebang when required; only that
known preamble is removed before decoding the fixture's JSON. The production
adapter is unchanged. The five Bash recording-client cases also passed locally,
as did Bash syntax checking; neither check connects to a real database.

## Explicit remaining boundary

The unmodified distribution vendor itself contains internal `exec()` calls using
MySQL passwords in child process arguments. This adapter removes the main
installer's outer argument exposure; it does not claim to remove every vendor
internal exposure or certify the full vendor initialization flow. Rewriting that
package's credential-changing internals without a disposable first-boot system
would alter the provisioning contract and is outside this tested transport fix.
No corresponding operations were run on an existing PBX.
