# MytelPBX 7.7.0 candidate verification

Status: **CANDIDATE — final release receipt pending**.

This record does not authorize a claim that `v7.7.0` is published or that the
current installer, ISO or real call paths have passed final acceptance. Replace
pending entries with exact receipts from the final reviewed source and assets.

| Acceptance item | Final receipt status |
|-----------------|----------------------|
| Reviewed commit, native-source pins and bundle checksum | Pending |
| Published online installer and release-asset readback | Pending |
| Fresh Rocky Linux 8.10 Minimal online installation | Pending |
| Native Asterisk version actually installed and password-wizard result | Pending |
| Mytel UI, Desk 1.1.2 and CPU model/doctor checks | Pending |
| Real SIP registration/signaling and two-way audio | Pending |
| Automatic VAD on a recorded call | Pending |
| Native ISO build/readback and BIOS/UEFI offline installation | Pending; owner-lab artifact only |

The online installer retains the native Asterisk 16/18/20 selector, default 18.
The native ISO retains its original Asterisk 20 package profile. Availability is
separate from acceptance of every version and telephony scenario.

Local deterministic checks, a successful bundle/ISO build, an open port, a web
response or a running process do not establish a completed fresh install or call
acceptance. The ISO binary is not uploaded to GitHub. Historical release records
retain their original scope and do not certify this candidate.
