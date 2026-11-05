# Version-one deployment snapshot

This directory preserves a **sanitized instruction-driven Media Scout setup**, captured for migration and rollback reference. It is not an automatic installer, a copy of private state, or a production-readiness certification. It is distinct from the experimental native plugin elsewhere in this repository, which was not installed in the captured deployment. Do not silently switch between the two implementations.

## What is preserved

- Scout role instructions; canonical source identity; evidence/reuse and deduplication procedures.
- Automatic separate Default review, source-thread return, project-fit recommendations and private knowledge capture.
- The complete local `media-to-github` skill, two references and issue/PR templates, including exact-approval and Default publishing boundaries.
- Response format with recap, clear final-result separation and concise Done/Proposed/Rejected/Your action sections.
- Seven-day raw-cache / ninety-day evidence retention, permanent summaries, bounded cleanup and protected-item rules.
- Native recovery and quota handling; optional browser reconciliation remains disabled.
- Central deferred-skill watchlist contract and local knowledge/wiki instructions.
- Selected configuration, cron definitions, enabled/disabled skill inventory, media Python package versions and naming-patch dependency.

See [feature inventory](FEATURES.md), [restoration procedure](RESTORE.md), [dependencies](dependencies.json) and [sanitization boundaries](SANITIZATION.md).

## Read this before using any file

**`profile/` records the historical behavior, not safe import defaults.** It includes rules describing already-authorized forwarding and deletion in the source deployment. Do not bulk-copy or serve it as a fresh live profile.

1. Create an isolated, initially disconnected profile using native Hermes controls.
2. Review and adapt `config.example.yaml`. Keep Discord disabled; placeholders are deliberately nonfunctional. Shell paths in the STT command are examples requiring explicit resolution/quoting and test on the target runtime.
3. Before loading the role/skills or any cron, replace the profile's policy with `policy.safe-defaults.json` and recovery policy with `recovery.safe-defaults.json`. Both disable automatic review/recovery and use report-only cleanup.
4. Explicitly authorize and separately test owner allowlisting, review routing and bounded retention before re-enabling source behavior. All public cron definitions are disabled. The original browser reconciliation job stays disabled unless its real access prerequisite is independently resolved.
5. No credentials, accounts, consent, admission decisions or pending task approvals transfer with this snapshot.

No custom executable helper, daemon or installer is added. Native scanner and host gates apply to the complete candidate skills when installed; public availability does not make this an official Hermes skill source.

## Layout

- `profile/SOUL.md`: generalized source role instructions.
- `profile/skills/media/`: complete sanitized local skill packages with their linked support files.
- `profile/media-library/`: policy and response/review contracts only. **No media records, evidence, submissions or conversations.**
- `config.example.yaml`: selected configuration, not credentials or a complete replacement for independently configured Default.
- `cron.definitions.json`: documentation-only definitions with disabled schedules and historical enabled-state indicators.
- `skills-inventory.json`: acquired skills must be restored from original sources with appropriate licensing/admission. Third-party code is not copied into this public snapshot.
- `dependencies.json`: observed versions, not a fully portable lockfile.
- `MANIFEST.json`: SHA-256 identity of public snapshot files, excluding itself.

## Qualification

The public payload is checked for reviewed privacy patterns, valid JSON/YAML, linked skill support files, feature contracts and archive extraction/hash integrity. The repository's original offline suite is also run unchanged. These checks do **not** establish new live Discord/provider operation, cross-platform compatibility, or successful production rollback.

A separate private local archive preserves deployment bindings and existing data. It is not part of this repository or release assets. Keep it confidential; local file permissions are not encryption or off-device disaster recovery. A live multi-process setup cannot be made a perfectly atomic snapshot by copying files without pausing its writers; SQLite databases use their online backup API, while other files are hashed as read. Retain the working deployment until isolated real acceptance passes.
