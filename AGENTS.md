# MyTellPBX working contract

## Owner direction (2026-11-04)

- Redesign the panel, operator desk and standalone phone as one polished product.
- Inspect the real installed pages in light and dark themes, desktop and mobile.
- **Keep the PBX/call-center settings console LTR.** Do not mirror its forms,
  table columns, navigation structure or technical values. Persian panel and desk
  navigation remain RTL.
- The owner authorizes scoped implementation, GitHub publication and deployment
  of the tested UI release without routine permission questions.
- Save the implementation, reproducible checks and honest results in this repo.
  Never commit the private handoff, credentials, tokens, sessions or customer data.

## Production boundary

- Only the host identified by the owner's private handoff is authorized.
- UI assets/templates only: no trunks, dialplan, AMI permissions, call control,
  account resets, database migrations, real calls or telephony reloads.
- Use verified SSH host keys. Keep credentials in the existing private source.
- Compare live assets with GitHub before replacing them. Preserve unrelated work.
- Back up every changed live path; document and verify a scoped rollback.
- Test candidate assets with browser-local response overrides before deployment.
- Read-only browser audits must not submit configuration or call-control actions.
- Independent review must return READY before publication/deployment. A local
  provisional gate receipt is not an authoritative production approval.
- Do not claim that untested paths or unavailable modules passed. Record failures,
  infrastructure limitations and pre-existing defects separately from regressions.
