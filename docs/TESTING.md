# Verification and test scope — 7.7.0 revision 2

The current [verification record](releases/7.7.0/verification.md) binds
`v7.7.0-r2` to exact source and its three frozen assets. Public readback, the fresh
online installation/postboot, bounded core/media, independent cleanup/preservation
and ordinary R4 reboot checks passed. The decision is
**ACCEPTED_FOR_TESTED_INSTALLATION_MEDIA_SCOPE**, with the limits below.

For source changes, run the relevant existing tests in `tests/` on their supported
platform. Record skips. The Python suite entry point remains:

```bash
python3 -B -m unittest discover -s tests -v
```

Recorded evidence and limits:

- The focused Linux gate passed **54 tests, zero skips**: 33 native add-on cases
  including bounded startup readiness, and 21 ISO/drop-in cases. The recorded
  [CI run](https://github.com/DashSaman/MyTellPBX/actions/runs/44222184586)
  is source evidence; neither result is a SIP/RTP or fresh-install pass.
- Historical **R3 UEFI offline installation plus the reviewed d039 completion-guard
  migration passed**. The real systemd 239 parser and controlled post-migration
  reboot proved that native initialization and add-ons were not repeated. Services,
  Desk1.1.3/doctor, sealed media, recording-hook/PEM metadata, native HTTPS and
  served bytes were checked; no new UEFI media calls were made.
- Current **R4 ISO build/readback and cold UEFI installation baseline passed**,
  with the original 2192-file native inventory, RPM bytes, non-group native repo
  metadata and UEFI payload preserved. Native/password/add-on phases completed;
  four services, doctor, native Persian, normal IP TLS/panel and the automatically
  created root-owned mode-0600 success marker passed. One ordinary reboot changed
  the boot identity and skipped firstboot/add-on replay, retaining one completion
  receipt, services, credentials, keys/certificates and owned metadata. No repeated
  offline media suite is claimed. The ISO stays private in the owner's lab.
- Fresh public-default R2 online installation and postboot readiness passed.
  **Seven core cases**, including registration, decoded two-way audio, strict
  hold/resume, mute and both-direction BYE, passed. **Four speech cases** and
  **four same-call continuation cases** passed: native WAV/CDR proof, automatic
  CPU VAD with 12 segments, UI playback/pause and full download byte parity.
  Exact two-fixture deletion, one Apply and visible Close passed; separate final
  state checks verified zero calls/channels/contacts and zero native devices/users/
  trunks, Desk agent retirement, restored recording policy and retained WAV/CDR/VAD history.
- Three prior core/diagnostic runs and the first playback continuation remain
  failed receipts. The distinct successful runs corrected bounded QA hold/dialog
  preconditions and process-only Node certificate trust; public product/source
  payloads were unchanged. No failure was relabeled as a pass.
- Earlier BIOS20 media, Desk upgrade/retirement and ownership-hook results
  retain their original source/artifact scope. They do not certify the fresh R2 run.
- An earlier native pre-password startup emitted an Asterisk segmentation fault;
  its cause remains unproven. Preserve that historical failure separately from
  later configured-runtime results. Do not infer a final R7 runtime pass or failure
  from that pre-password observation alone.
- Both installation paths support **Asterisk 20 only**. Native language choice is
  retained; 16/18 are unsupported. The four native password
  screens remain MariaDB first/confirm, then panel admin first/confirm.
- Read-only page checks do not certify all writes, roles, external trunks, fax or
  integrations. CPU doctor/model inference is separate from VAD on a real recording.
  The media results cover two owned internal endpoints with synthetic microphones;
  PSTN and physical-phone acceptance is not asserted.

Two recorded limitations remain explicit:

- The original cleanup browser run remains **FAIL rc2** with one `Failed to fetch`
  page error after three blocked GETs. Its two-Delete/one-Apply/visible-Close case
  passed and `uncertainWrite` was false; independent final-state proof passed.
  One subsequent read-only discovery did not reproduce the page error. Its cause
  is unproven, and the failed report was not relabeled as passing.
- The native CEL schema lacks `extra`. Desk catches that optional enrichment
  query failure and falls back to CDR data; richer CEL hangup-cause/dialstatus/
  who-ended details are not established. Required CDR/WAV/VAD/playback checks
  passed separately. This is not an all-pages or zero-error claim.

The [7.6.0 record](releases/7.6.0/verification.md) and
[7.6.2 record](releases/7.6.2/verification.md) remain historical. Private credentials,
logs, sessions, backups and customer data are not release assets. Existing source
and all earlier evidence are preserved. The verification record binds the actual
completed receipts; publication does not expand their tested scope.
