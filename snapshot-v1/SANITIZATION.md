# Sanitization and publication boundary

## Reviewed allowlist

Only local role instructions, the two local skill packages, review/response templates, policy specifications, selected credential-free behavior settings, disabled cron definitions, dependency/skill identities and restoration documentation are exported. These are setup definitions, not user evidence.

Do not recursively publish a live Hermes profile or use a generic `hermes backup` archive as a release asset: native full backups can contain `.env`, auth and other confidential state.

## Transformations

- Machine home paths become `$HERMES_HOME`, `$DEFAULT_HERMES_HOME` or `$HOME`; operators must resolve these for their selected CLI/command-provider version.
- Real source message/thread/server/channel/owner/task/cron identifiers become named placeholders. Personal project bindings become `<github-owner>/<checklist-repository>` and `<github-owner>/<media-scout-repository>`. Repository identities must be verified afresh before writes.
- Personal address/name references in instructions become owner-role wording. Original contributor authorship and upstream licenses are preserved rather than anonymizing authors' credit.
- Source-specific media URLs and deployed Discord links are removed from setup examples. No actual captions, transcripts, reviews or evidence files are selected.
- Cron runtime IDs, histories, delivery/subscription state and original trigger times are excluded. Public cron definitions are disabled; `source_enabled_at_capture` describes the old state, not import consent.
- Historical enabled policies remain explicitly archival. The safe overlay disables forwarding/recovery and deletion; it must be applied before any imported role can act.

## Never included publicly

Credential stores, `.env`, OAuth grants, vault access, cookies, browser profiles, pairing stores, owner allowlists with real IDs, private proposals/approvals, task databases, sessions/logs, media/transcripts/images, records/receipts, wiki content, existing watchlist entries and local private backup locators. Cryptographic file digests, upstream revisions and intentional contributor credit are not secret material.

## Validation boundaries

Automated pattern checks are a defense in depth, not proof that arbitrary text contains no sensitive semantics. The explicit file allowlist, source-to-template review and independent read-only audit are also required. Every public file is bound by SHA-256 in `MANIFEST.json`; the public ZIP is separately checksummed after generation. The private archive is tested separately and is never included in Git, the public ZIP or release assets.

Sanitized source and test assertions describe behavior; they are not a filesystem sandbox, a scanner bypass, credential migration or a guarantee of live restore. Existing upstream/native patches keep their license and are not silently rewritten to pass admission.
