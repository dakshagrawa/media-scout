# Restore / migration runbook

## Scope

This preserves a versioned setup, not a turnkey image of an authenticated machine. Use the release's exact tag and verify every file against `MANIFEST.json`. The tag identifies the snapshot; a moving branch is not the rollback authority. Keep the old profile, private backup and admitted media runtime intact until all acceptance gates pass. Do not overwrite Default or a currently served profile as a test.

## Rebuild in isolation

1. Acquire Hermes through its official installation path. Consult current official documentation for supported profile creation/install/skill/cron commands; commands and plugin SDKs can change across releases. The observed Hermes revision and Python/media package versions are in `dependencies.json`. Do not downgrade the entire shared installation or replace rotating OAuth grants merely to match a snapshot.
2. Create a separate test profile using native profile controls. It must be disconnected from Discord and cron. Do not use `--force`, clone channel credentials, or serve both old/new profiles with the same bot connection.
3. Install the two included local skill packages through supported native skill management in the target profile, with the full reference/template closure and admission intact. Acquire bundled and third-party dependencies from original authorized sources using `skills-inventory.json`; scan/review those sources under current policy. Do not execute quarantined packages or use raw copying to bypass skill admission.
4. Configure the general role from the snapshot. Before any session can act, apply the safe policy and recovery overlays and keep cron disabled. The historical role/SKILL text mentions authorized automatic work; the imported policy does not supply that consent. Review those instructions together so no model can infer source-deployment permission is transferable.
5. Configure your own model/provider and secrets using native secure authentication and the password manager. Never copy `.env`, token/OAuth files, browser cookies, pairing stores or shell environment dumps from another profile. Fill owner/channel/server/project bindings privately and verify the allowlist before connecting.
6. Resolve profile-home placeholders and review the recorded STT command's shell quoting and native command-provider contract for the selected version. Build/admit the isolated local transcription environment from observed packages, fetch the appropriate model through its original source and configure profile-local OCR. Resolve downloader/ffmpeg/ffprobe through approved package sources. Do not assume inventory means every OS binary, wheel or model is pinned or available forever.
7. Provision a separate Default review worker/board and native source notify+wake routing. Preserve Default's own existing authorized context and isolation; this snapshot does not export Default's memories, credentials or unrelated projects. Use synthetic no-write packets first. Do not manufacture approvals or mark queued work complete.
8. If restoring existing private data, restore into the disconnected test profile only. The private archive has sensitive conversations, source evidence and bindings: never attach it to a public issue/release or load its entire database into unrelated profile memory. Validate archive checksums, file paths and database integrity first. Review-board state is a shared resource: inspect and selectively restore only relevant records with native tooling after collision analysis, never overwrite a live global board database. Reconcile records, receipts and task references; expired/deleted artifacts are not reconstructed by guesses.
9. Enable exactly one source connection only after the owner approves activation and isolation tests pass. Reauthorize credentials rather than transplanting grants. Real acceptance needs an owner submission and actual source-thread conclusion; a cold file read or synthetic worker is not enough.
10. Recreate cron through native scheduler controls from the disabled definitions. Test retention against disposable fixtures in report-only mode first, including protected/pinned/active/recent/malformed/symlink cases. Enable bounded deletion only with matching authorization and verified limits. Leave browser reconciliation disabled unless its access/isolation prerequisites are separately resolved.

## Acceptance gates

- [ ] Release manifest identity and archive extraction verified; no credentials/private state in public payload.
- [ ] Target profile has no duplicate channel ownership, all secrets are separately provisioned, and source allowlist verified.
- [ ] Installed local skill/reference/template hashes match the admitted candidate; fresh runtime discovers both skills.
- [ ] Explicit local-only/stop and untrusted-source-instruction fixtures produce no dispatch/publication.
- [ ] Actual speech plus sampled visual evidence is saved, with honest coverage and reuse on repeat submission.
- [ ] One real authorized submission creates/reuses a separate Default review, returns a concise regular conclusion to the exact source thread and retains useful attributed learning.
- [ ] Project-fit recommendation and issue-vs-PR drafting work without manual relay; exact action approval remains separate.
- [ ] Watchlist add/update/readback/deduplicate fixture succeeds without installing anything or leaving fixture entries.
- [ ] Naming behavior and no-redundant-review-consent behavior checked independently.
- [ ] Cleanup fixture passes before deletion activation; paused reconciliation remains paused.
- [ ] Pending/blocked old tasks reconciled against latest decisions; no unapproved replay or duplicate publication.

## Rollback

First stop new task admission and pause only the migrating profile's affected schedules/connection through supported controls. Preserve post-migration records and pending decisions; do not discard new work to restore an older database. Compare source manifests and compatibility, then re-enable the retained old profile/runtime after reviewing duplicate bot ownership and task state. A real cutover/rollback requires separate authorization and live acceptance; this release performs neither. Private SQLite backups are internally consistent, not a transactionally atomic snapshot spanning all processes and files.

## Backup limits

The private archive intentionally excludes credential stores, browser state, volatile locks, cached execution logs, virtual environments and model/OS binary installations. It includes the local setup, source data, skill instructions and SQLite backups; runtime dependencies remain in the old deployment and are identified separately. No off-device encrypted copy is configured. File permissions protect against other local users, not disk loss or an account/host compromise.
