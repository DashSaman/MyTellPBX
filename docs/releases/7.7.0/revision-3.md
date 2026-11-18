# MytelPBX 7.7.0 revision 3

The online entry point uses the [revision 3 release](https://github.com/DashSaman/MyTellPBX/releases/tag/v7.7.0-r3). The image for air-gapped installation remains on the owner's lab server. Both installers retain the native language and password setup and install Asterisk 20.

## Changes

- The native add-on checks that CEL is enabled, tracks `HANGUP`, and writes through ODBC. It adds the nullable `asteriskcdrdb.cel.extra` column when needed, records the prior schema, and reloads `cel_odbc.so`. Asterisk keeps running and existing CEL rows are preserved.
- The pinned [MytelDesk 1.1.4](https://github.com/DashSaman/MytelDesk/releases/tag/v1.1.4) reads the standard CEL payload and accepts older `eventextra` payloads when they carry usable details. Historical calls without recorded CEL metadata use CDR data for their outcome. Installations cannot infer a historical hangup source from blank records.
- The native notification used by extension deletion and Apply is consumed once. The fix preserves the backend results and lets users close the success notification.

## Verified results

| Check | Evidence |
| --- | --- |
| Live CEL capture and Desk attribution | Two answered internal WSS/PJSIP calls on the R2 lab guest upgraded to Desk 1.1.4. The caller sent BYE on the first call and the callee sent BYE on the second. Both produced Asterisk cause `16` and dial status `ANSWER`. The compiled Desk reader, authenticated Call History and call journey agreed on the source extension in both cases. Asterisk's process identity stayed the same. |
| Native cleanup | The same lab guest recorded two native Delete submissions, one Apply and one Close with the corrected PHP flash renderer and browser dismissal. The browser recorded zero page errors. Native database and CLI checks found zero fixture extensions, active calls and contacts afterward. Historical call rows were preserved. The final installer also guards the no-output component path. A fixture using the native PHP 7.4 code reproduced premature consumption and verified the correction. |
| MytelDesk 1.1.4 | All 1,070 backend tests passed on Linux. TypeScript, the canonical Linux archive build, the scoped R2 upgrade and Doctor passed. |
| Installer regression suite | Linux ran 669 Python cases with 634 passing and 35 skipped by their environment requirements. All 16 chart and calendar Node tests passed. |
| Fresh offline ISO install | The exact R6 image completed a cold UEFI installation to a blank disk on the lab host. Native first boot completed with Persian and PJSIP, all four services were active, the installer completion marker was present, and the MytelPBX panel returned HTTP 200 over verified HTTPS. Asterisk reported 20.12.0 and the installed Desk reported 1.1.4. |
| Fresh online script install | The exact revision 3 script completed on fresh Rocky 8.10 Minimal with vendor packages fetched online. The script used the final checksum-verified PBX bundle and Desk archive staged locally before publication. The native wizard accepted four password entries and PJSIP. The installer passed its Doctor gate and rebooted automatically. All four services were active and the branded panel returned HTTP 200 over verified HTTPS. Asterisk reported 20.12.0, Desk reported 1.1.4, and all three cleanup files matched the reviewed version. |

The private offline file is `/root/iso/MytelPBX-7.7.0-x86_64-native-r6.iso` on the lab server. It is 3,821,535,232 bytes with SHA256 `1f71b9161d1d7aa9fea1591b5d69e5165656148642ab86dc64114d42b77c5e94`.

A local hostname entry was needed on the online test guest after its name lookup exceeded eight seconds. The installer proceeded after that lab configuration fix. An early native RPM helper logged a PDO driver warning before initialization. The installed PHP exposed the `mysql` and `sqlite` PDO drivers after reboot, and panel startup succeeded. The offline test continued after a transient virtual CD read timeout and verified all 1,138 packages.

| Tested online asset | SHA256 |
| --- | --- |
| `install-mytellpbx.sh` | `3ad6ffd46805c3764ccc92fe69d6f6160a848a00932c2ff7fdf1fbc22803f5e8` |
| `mytelpbx-bundle-7.7.0.tgz` | `4e2cc4deb590ac56b7dd8420e07c451415cec9d80ff434b556ca23953f833334` |
| `myteldesk-1.1.4.tar.gz` | `8bd8687507d106365357a47decc575f60ba371c5d0a812e4af59f36c90a0d998` |

The two live calls cover normal disconnect attribution. The [revision 2 verification record](verification.md) covers the previous online release and its own ISO, media and reboot checks.
