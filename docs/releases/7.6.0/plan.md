# MyTellPBX 7.6.0: complete panel review and integrated Desk

The owner requested a page-by-page review of the installed contact-center panel,
practical verification, and inclusion of the released MytelDesk with automatic
CPU VAD in the main installer. Existing customer data and telephony configuration
must be preserved. This plan derives directly from that request.

## Product contract

- The Persian shell remains RTL; the embedded PBX technical console remains LTR.
  Addresses, codecs, SIP values, native form serialization and validation retain
  their existing meaning and order.
- Improve the existing navy/blue visual system through reproducible defects:
  readable selected controls, contrast, search fields, consistent spacing, focus,
  responsive layout and localized scrolling for genuinely wide technical tables.
- Preserve native Save and Apply execution. Feedback must identify loading,
  success, failure and unknown outcomes; navigation must not orphan handlers.
- Install the same independently released Desk and automatic CPU VAD using exact
  verified release pins. Do not apply legacy source patchers over immutable Desk
  releases, reset administrator credentials, or invent an unsupported SSO path.
- A fresh-OS installer is not a production UI updater. Existing/partial state
  must have a clear ownership/resume contract; no old marker may falsely certify
  the new presentation or Desk version.

## Verification journeys

1. Inventory every available panel menu and PBX display from the actual installed
   system. Review light/dark at desktop/mobile sizes, recording unavailable
   modules separately rather than counting an HTTP200 error page as success.
2. Reproduce each meaningful defect with an executed RED test. Commit the
   checkpoint, make a focused fix, rerun to GREEN and retain the evidence index.
3. Check keyboard access, visible focus, selected choices, long labels, dialogs,
   loading/error/empty states and fixed toolbars. Test candidate assets with local
   browser response overrides before deployment.
4. Exercise installer integration with sandboxed filesystem and command fixtures:
   pinned integrity, progress/failure, same-release retry, preserved credentials,
   unknown/legacy ownership rejection and modern native-panel sign-in entry.
5. Run Python/Node/PHP/shell checks appropriate to the touched code. Execute
   isolated PHP tests without PBX or database access. Separate these from an
   actual fresh-OS install; never run OS setup/teardown against an existing PBX.
6. Build a scoped, hash-bound UI artifact from current installed snapshots; take
   backups and require an independent READY bound to its exact manifest/tree.
   Deploy only reviewed paths, verify actual rendered pages and service health,
   and preserve unrelated files, identities and Asterisk state.
7. Publish a source-complete release with checksums, factual acceptance notes and
   explicit limitations. Test the public delivery path without credentials.

## Boundaries

Unconfigured SMTP/fax/CRM or absent optional modules are conditional capabilities,
not passing end-to-end business integrations. Read-only production sweeps do not
submit configuration, originate calls or reload telephony. Any necessary bounded
write journey needs its own baseline, ownership, restoration and reconciliation
evidence before being reported as tested. A successful local check or publication
does not establish a successful production rollout.
