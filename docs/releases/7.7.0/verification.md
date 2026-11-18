# MytelPBX 7.7.0 revision 2 verification

Status: **ACCEPTED_FOR_TESTED_INSTALLATION_MEDIA_SCOPE**.
Fresh R2 online installation/postboot, bounded media, independent cleanup/preservation
and the exact R4 cold installation plus one ordinary reboot are accepted within
the scope below. The online release is `v7.7.0-r2`; its three frozen assets passed
anonymous readback. The original cleanup browser failure and optional CEL limit
remain explicit. This record does not certify untested functions or a zero-defect product.

| Binding | Recorded value |
| --- | --- |
| Public reviewed source | `80198fbb2da73814393726e8a495e79b3e516330` |
| Payload producer source | `e65a0768c4ef6f3fec69d27cec3d7bff6a9dc55b` |
| Online tag | `v7.7.0-r2` |
| Bootstrap, 7652 bytes | `537e73ee095cece056623930bfe5ccec8f8c9ff6340e1339b03f70f72d1ae812` |
| Bundle, 2922861 bytes | `4b2903799e250f0351c6ad315bc1f87cc6a7c4b9ead13818116962d178fe9fe5` |
| Sealed media manifest | `e2227a5d6c18b4749d96b888a6af0136b7465086c2d28d0e85f073819fea3ec1` |
| Desk version/source | `1.1.3` / `b45e3394ee6da56f810b384f57996ab2203b49a4` |
| Desk tree/archive SHA256 | `8f0aa8200cba7437556281b8fddaed17a2d9ae89` / `b48f7ddc495c3f69cb6c53542550d7e8d6c19fe4e2e40061c1473bffc3bdb19e` |
| Original Issabel ISO SHA256 | `c63b7512d3ba05af645e144c58bf00c87353ddf2b3318e2fda8c262c057c07f9` |
| Private R4 ISO, 3821535232 bytes | `f931bc7a545b3f28ad215611f6246ebbcef5d9f292bea9051e4cf3156967005b` |
| Success-only completion drop-in | `d0393d8bc518223680f44e3b8f08d51e638b37067fd7555823f8839d91a2da36` |

The exact private artifact is
`/root/iso/MytelPBX-7.7.0-x86_64-native-r4.iso`. It is **not uploaded to GitHub**.
Pinned original vendor source bytes remain unchanged. Within **native repo metadata**, only
comps/group/environment records and their repository index change; the ISO also
contains Mytel boot/Anaconda branding, sealed add-ons and the firstboot hook.
The preserved original inventory contains 2192 native files; RPM bytes,
non-group records and embedded UEFI boot payload remain verified.

| Acceptance item | Actual scope/status |
| --- | --- |
| Source/fixtures | 54 focused Linux tests PASS, zero skips; full CI: 667 Python cases (642 PASS, 25 explicit skips), 16 Node cases PASS plus shell/JS/PHP checks; [recorded CI run](https://github.com/DashSaman/MyTellPBX/actions/runs/44222184586) |
| Published online assets | PASS: anonymous HTTPS readback; exact header/bundle/SHA256SUMS and all 123 manifest files |
| Historical R3 UEFI native offline installation | PASS for the original R3 installation and the separately reviewed completion-guard migration |
| Historical R3 completion guard | PASS: real systemd 239 parsing and controlled post-migration reboot; condition skipped the unit, no repeated initializer/add-on or new recovery receipt |
| Current exact R4 ISO | Build/readback and cold UEFI installation baseline PASS: native/password/add-on phases completed, four services and Desk doctor, native Persian, normal CA/IP/date TLS and panel HTTP 200; real root-owned mode-0600 success marker created by the hook, without migration or a manual marker |
| Current R4 ordinary post-install reboot | PASS: changed boot identity; condition skipped native firstboot and ExecStartPost; one completed add-on receipt, no new workspace/receipt; four services, CPU Doctor, native configuration, credentials, keys/certificates, owned metadata and served assets preserved |
| Fresh R2 online install, four password screens, selected language and Asterisk20 | PASS: one public R2 run on fresh Rocky 8.10; Persian/native four password screens/PJSIP default, native completion footer and automatic reboot observed |
| Fresh R2 postboot services/doctor/CPU model, TLS/served bytes and hook/PEM ownership | PASS: new boot; Asterisk 20.12.0 and all four services, Desk 1.1.3 doctor and actual CPU-model analysis; native DB password over TCP; normal CA/IP/date TLS validation; served JS/CSS and seven native sources match disk |
| Fresh R2 SIP signaling and decoded two-way audio/hold/mute/BYE | PASS: seven core cases; matching hold re-INVITE/ACK and resume SDP, UI hold state, mute/unmute, two-way decoded audio and both-direction BYE; owned sessions ended |
| Fresh R2 native recording, automatic VAD and playback/download byte parity | PASS: four speech and four same-call continuation cases; native WAV 322604 bytes / 20.16 s, linked native CDR, stable canonical file descriptor, automatic CPU VAD 12 segments, authenticated full playback/pause and UI download matching the native SHA256 |
| Owned fixture cleanup, idle state and preservation | Actual state PASS: two native Deletes, one Apply and visible Close; zero owned/native test objects and idle calls/channels/contacts, Desk fixture retired, recording master restored with directions/retention unchanged, WAV/CDR/VAD retained. Original browser harness remains FAIL rc2; see limitation below |
| Scope decision | ACCEPTED_FOR_TESTED_INSTALLATION_MEDIA_SCOPE; no expansion to untested pages, roles or external calls |

Both install paths support **Asterisk 20 only**. Online sets it without a version
selection dialog; ISO Software Selection offers only the native20 environment.
Native language choice is retained. The four native password screens are MariaDB
root first/confirmation, then panel admin first/confirmation. MytelDesk1.1.3 VAD
uses its pinned CPU runtime; a doctor pass is not real recording/VAD acceptance.

The shared add-on waits at most 120 seconds for the Asterisk20 CLI and each native
MariaDB/httpd/Asterisk service, without restarting them or replaying initialization.
A different major or timeout fails closed. Offline completion is recorded only
after a successful add-on exit. The protected `offline-complete` marker and
systemd condition then prevent subsequent native initialization/add-on replay.

The R3 UEFI migration and actual postboot proof are bound by the owner-private
`acceptance-final-artifacts-r1.json`, SHA256
`6cf7a83efa81618e33562a6420dca90913256884a4973ee546d2c33b04112b21`.
It includes the parser, original completed installation, migration and final
postboot receipts. Current R7 artifact evidence IDs are
`native770-r7-bundle-receipt.json`, `native770-r7-public-readback.json`,
`native770-r7-media-receipt.json` and `native-iso770-r7-receipt.json`.
The actual online records are `native-online20-r7-core-final-report.json`,
`native-online20-r7-speech-final-report.json`, `native-online20-r7-native-recording-proof.json`,
`native-online20-r7-recording-final-report.json` and `native-online20-r7-node-trust-proof.json`.
These are private evidence identifiers, not downloadable release assets.

The completed R4 cold-install/reboot receipt is `native770-r4-final-cold-acceptance.json`
(9026 bytes), SHA256 `387a7a39e0a0be3e29f76c8f9fed182205ce2c67ad65024890398775b35cade6`.
The completed online pack is `native-online20-r7-final-receipt-pack.json`
(7919 bytes), SHA256 `bf690f5e315644aafd52de0e07c0f1237a07eb956ecd84387ca46aaf8f755456`; its final preservation receipt is
`native-online20-r7-final-preservation.json` (6105 bytes), SHA256 `26c7d360f9b0bfc4e8389d188f12073881027464b8c30abfdc329859ba18b3b8`.
The original cleanup browser report `native-online20-r7-cleanup-original-report.json`
(2745 bytes), SHA256 `64c2411d5719d1cd12b0d35b0c2232512a9e9629a46d84fb43b32c1cdfdbeeb2`, remains failed.

Three earlier core/diagnostic runs remain failed: the first lacked completed
hold-transaction/UI synchronization; the next lacked the observed native SIP self
alias in the bounded QA guard; the third deliberately retained that refusal while
collecting ingress evidence. A distinct reviewed harness required the matching
hold ACK/UI state and admitted only the proven same-guest self alias. The first
playback continuation failed because the QA Node fetch process lacked certificate
trust. Its separate same-call success used the current attested public leaf through
process-only `NODE_EXTRA_CA_CERTS`, with normal CA/IP/date validation and no global
trust change. The one-fetch guard stayed intact. All earlier reports are preserved;
the public installer, source and product payloads were unchanged by these QA corrections.

The cleanup browser run remains **FAIL rc2** with one `Failed to fetch` page error
after three blocked GETs. The exact two-Delete/one-Apply/visible-Close case passed
and `uncertainWrite` was false. Separate native/Desk/policy/recording preservation
checks passed; one read-only discovery did not reproduce the page error. Its cause
remains unproven. No failed run is relabeled as passing.

The native CEL schema lacks `extra`: Desk catches the optional enrichment query
failure and retains CDR-based history/status fallback. Richer CEL hangup-cause,
dialstatus and who-ended details were not established. Required CDR/WAV/VAD and
playback/download functions passed independently.

The native online reboot closed the wrapper/SSH transport (preserved HUP129/SSH255;
native child exit was not observed). Installation acceptance uses native completion,
the new boot and independent service/state evidence. Current-boot journal/kernel/
coredump checks are bounded; the installation boot is absent from retained journal.

Earlier BIOS20 media and Desk1.1.3 upgrade/retirement/hook evidence remain
historical and do not certify the fresh R2 install. An earlier pre-password native
Asterisk segmentation fault has no established cause; retain it separately from
final configured-runtime findings. The current call results come from their own
distinct receipts and do not establish the cause of that historical startup fault.

The core/speech evidence uses two owned internal endpoints and synthetic
microphones. It does not certify all pages, roles, writes, external trunks, PSTN or
physical phones. Host network/selected ICE and preserved-state checks retain their
independent receipt scope; a browser guard alone is not network-isolation proof.

The vendor PHP7.4 baseline and disabling of SELinux/firewalld are retained.
The imported original installer used HTTP sources. Derived Issabel base/key
**definitions** use HTTPS, but observed R6 native primary metadata contained
absolute HTTP RPM URLs; package payloads are not uniformly TLS-protected. The
GitHub bootstrap/bundle verified-HTTPS + SHA256 chain is separate. Each vendor
repository GPG policy is preserved, including `gpgcheck=0` on the two enabled
legacy Issabel4 repositories (source-repo definition disabled); global yum
`--nogpg` is removed. Bundle checksums do not establish universal native RPM
signature verification. Package/service/database names, legal notices and trademarks remain
intact. Historical release records and original artifacts are preserved.
