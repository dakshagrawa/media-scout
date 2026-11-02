# Media Scout: native media-to-knowledge workflow

A portable reference deployment for Hermes, not a turnkey product, auto-installer or new hosted service. It combines the reusable [media-evidence-library skill](../../media-evidence-library/SKILL.md) with native profile isolation, Discord threads, local/admitted media tools, reviewer tasks and an explicit retention policy. The owner's deployment uses automatic review and qualified deletion; public templates deliberately start inert.

## Flow
Owner sends one media item per top-level intake message -> Scout thread and canonical lookup -> reuse or actual audiovisual evidence -> non-blocking preview -> automatic reviewer task under explicitly enabled standing consent -> Default understanding/learning and optional proposals -> same-thread result + retained knowledge. Only a consequential proposal reaches a separate action-approval gate.

Open the self-contained [workflow diagram](workflow.html). Default owns all personalized reasoning, not just skill recommendations. “Just learn this” is valid. Source-linked learning is searchable but is not automatic memory injection into every existing chat.

## Files
- [Scout role](templates/scout-SOUL.md) and [Default task contract](templates/default-review-contract.md).
- [Inert library policy](templates/policy.example.json), [synthetic record shape](templates/library-record.example.json), [disabled Discord excerpt](templates/discord.example.yaml) and [retention prompt](templates/retention-job.md).
- [Acceptance record and checklist](acceptance.md).
- [Optional native naming patch](../../patches/media-thread-naming/README.md); default-off and base-version-specific.

## Configure deliberately
1. Read the current official [profile](https://hermes-agent.nousresearch.com/docs/user-guide/features/profiles), [Discord](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord), [skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills), [Kanban](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban) and [cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron) docs plus the installed CLI help. Verify paths/settings against your Hermes revision.
2. Create an isolated intake profile with native `hermes profile` commands. Do not copy a live profile, its auth files, private memories or channel credentials. Install/review the reusable skill with Hermes's supported skill workflow and scanner; this repository is not the official Hermes skill catalog and must not bypass an official-source-only policy.
3. Adapt only the templates. Keep real owner/channel/thread/guild identifiers and secrets in your private local setup. Configure settings through native `hermes -p PROFILE config set` / setup tools, not by overwriting a live config.yaml with this excerpt. Configure owner allowlists before connecting the bot. Do not grant Administrator or share broad browser logins just for this flow.
4. Use admitted upstream acquisition, transcription and image tools. This package does not install yt-dlp, ffmpeg, OCR, Whisper, third-party skills, models or provider credentials. Verify actual timestamped speech and visuals; direct video support depends on provider. Ask for uploads on source-access failure.
5. Adapt the Scout role into that profile's SOUL and store the reviewer contract privately. Configure a native review board, assignee and source notify+wake subscription. Test blocked -> subscribe -> readback -> unblock and real return delivery. Supply the FULL contract in each task body. Do not add another conversational bot to the intake channel.
6. Explicitly decide standing authorization: after the operator explicitly authorizes cross-profile review, set automatic_forwarding=true in the local library policy and retain the actual authorization reference plus review-only scope. This is an instruction policy, not a built-in Hermes config key. New submissions then do not need a forwarding button; item opt-outs override it. Do not retroactively dispatch old records. Public defaults are false; cloning alone grants no cross-profile forwarding.
7. Keep cleanup report-only until disposable fixture tests and explicit deletion approval pass. Test actual deletion and protected hashes for recent/pinned/active/queued, nested fresh, unknown-date, malformed, symlink and traversal cases. Only then set the local policy to delete-expired and create/edit the existing native cleanup job. No new cleanup service or script is required. Read the [retention procedure](../../media-evidence-library/references/retention.md).
8. Complete your own acceptance checklist and preserve local rollback snapshots before enabling production automation. Do not copy this deployment's test counts as proof of your setup.

## Limits
Instruction-based coordination is not atomic locking or a hard filesystem sandbox. Quota/restart recovery is bounded; no model-independent all-history guarantee exists. Multiple simultaneous duplicate submissions and several media items in one thread need further qualification. Prefer one item per top-level message and use its thread for follow-ups. Photos/carousels require actual ordered image inspection; the owner's real reel pilot is not a real-carousel test. Browser-history discovery is optional and was left paused in the reviewed deployment. Native naming needs upstream support or the explicitly reviewed version-specific patch; it is not guaranteed by SOUL alone.

## Stop and rollback
Pause the exact configured native cron to stop cleanup. Keep policy, role, skill/reference and job prompt consistent when returning to report-only; flipping just one document creates contradictions. Preserve private settings snapshots but do not overwrite newer media or approvals when restoring configuration. Deleted content is not recovered by a settings rollback. After Hermes updates recheck tools, naming, consent and return delivery rather than blindly reapplying an old patch.
