# Acceptance, compatibility and rollback

This file defines the release gates. The GitHub release notes report the actual completed gates; this checklist is not a claim that every possible deployment passed. All automated fixtures are synthetic and run without credentials or real private media. Previous instruction-only workflow results do not qualify this new plugin automatically.

## Portable offline gates

- Existing repository skill/workflow contracts still pass; legacy package paths and inert defaults remain unchanged.
- Source URL validation preserves case and original intent, rejects hostile hosts/paths, and handles tracking variants as one canonical source.
- Admission captures only the configured actual owner/scope. Unknown senders, missing source fields, malformed/multiple sources and pasted identity claims do not manufacture receipts.
- Missing records are created; replay preserves original provenance, summary and state instead of resetting them.
- Two cooperating callers cannot acquire the same extraction claim. A reload retains claim/evidence/task state. An elapsed timer does not imply that a writer stopped.
- Save validates the current claim, bounded evidence and honest structured coverage. Summary-only input cannot become a complete audiovisual packet.
- Review is disabled without operator consent. Local-only/stop/defer/no-review overrides win. Source text never changes the owner, profile, task authority or approval state.
- Native bridge failures before/after creation, subscription, readback and release remain recoverable using stable identity. Repeated dispatch does not create a second task or redirect an existing task to a different thread.
- Cleanup defaults to planning only. Apply requires explicit enablement and the exact unchanged plan. Registered expired artifacts alone are eligible; summaries, unknown/symlink/active/pinned/review-protected content and changed files survive.
- Publication scan excludes private identities, credentials, actual media, receipts, logs, databases and machine paths.

## Actual native SDK gates

Use an isolated, immutable supported Hermes release and disposable `HERMES_HOME`, separate from the live gateway. Clear credentials and do not start a model, notifier, dispatcher or Discord client.

1. Run native Plugin Doctor and `hermes plugins validate --install-deps`. Check manifest parsing, real registration, capabilities, the bundled skill, compatibility and security scan. An accepted mock context is not this gate.
2. Discover/register the package through the real SDK and deliver a labeled synthetic `post_gateway_admission` payload with the documented actual source shape. Bind synthetic session identity using the host's public context helpers. This tests plugin handling, not Discord authentication itself.
3. Through the actual registered tool, capture/create/read/claim/save/reload and verify the stored evidence hash and source identity. These are synthetic evidence fixtures, not transcripts extracted from a real source.
4. Use a separately isolated native Kanban board to exercise real blocked task creation, source subscription, exact readback and release. No live dispatcher should observe that board. Verify one stable task across repeated attempts and immutable return routing.
5. Exercise a real native terminal bridge denial/malformed-result path without concealing the failure or bypassing approvals. Verify no work is released before source binding is known.
6. Qualify cleanup against disposable owned files and preservation controls; inspect exact before/after bytes and the unchanged durable summary.

## Deployment-specific gates

A real Discord/model/media acceptance is separate: configure an authorized test scope, send one genuine owner source, acquire actual media with admitted tools, save truthful coverage, complete the configured reviewer task and verify a real conclusion in its exact original thread. Do not reuse the working bot's token in a competing client or call synthetic SDK events a real Discord test.

This release does not automatically enable the plugin in an existing live Scout. Model/provider/Discord permissions, extraction dependencies, source availability and native notification delivery remain deployment-specific. Windows/macOS portable unit tests do not by themselves establish native media/terminal functionality on those platforms. Never advertise an untested OS as production-qualified.

## Safe rollback

1. Disable only this plugin in its configured intake profile through native `hermes plugins disable media-scout`; verify the setting with native plugin listing.
2. Inspect native tasks separately. Disabling a plugin does not cancel already released work or remove its subscriptions. Use native queue controls if cancellation is intended.
3. Preserve `plugin-data/media-scout/` and private backups. Do not delete a database or copy an older snapshot over newer evidence/task state. Updates/removal should not erase plugin-owned data.
4. Restore only the prior role/configuration entries if you explicitly changed them. Do not alter another profile, unrelated skills, provider routing, authentication or shared gateway state.
5. The earlier `media-library` workflow is not migrated or overwritten. Its instructions and artifacts remain independently usable.

For an interrupted extraction, stop the old native writer before using the narrow owner recovery path. For a review interrupted between native phases, retry the same saved item/packet key; verify existing task state and binding rather than creating or unblocking blindly.
