# Delegated Retries for Existing Media Submissions (Issue #11)

## Scope

This document records the verified authorization path in `plugins/media-scout` and proposes a bounded, owner-authorized retry mechanism for existing media submissions, including those in [backlog reconciliation (#4)](https://github.com/dakshagrawa/media-scout/issues/4). It does not change production permissions, weaken owner-only Discord admission, or authorize rollout.

## Verified Enforcement Chain

1. **Post-admission receipt capture (`_admission` and `_capture` in `plugins/media-scout/__init__.py`)**:
   - Incoming Discord events are checked against configured `owner_id`, `guild_id`, and `parent_channel_id` (plus optional `intake_thread_id`).
   - Only messages authored by `owner_id` in the configured scope create a `receipts` row and a `media` record.
2. **Tool execution (`_handler` and `native_handler` in `plugins/media-scout/__init__.py`)**:
   - Every `media_scout` tool action reads `HERMES_SESSION_USER_ID` from trusted session context.
   - If `HERMES_SESSION_USER_ID` does not equal the configured `owner_id`, the tool fails closed with `{"error": "configured owner identity required"}`.
   - Catalog isolation checks `catalog_meta.owner_id` against the session actor.
3. **Owner command (`_command` in `plugins/media-scout/__init__.py`)**:
   - `/media-scout release <media_id> --writer-stopped` requires a Discord command from `owner_id` in the configured guild and parent channel.

When `discord.allow_bots: mentions` is enabled, a separate assistant bot can mention Media Scout inside an existing thread. Gateway delivery succeeds, but the tool call fails closed because `HERMES_SESSION_USER_ID` is the assistant bot ID, not `owner_id`.

## Why Discord Bot Mentions Must Stay Blocked

- A Discord mention from another bot cannot cryptographically prove that the owner authorized that specific retry.
- Trusting a configured bot ID or spoofing `HERMES_SESSION_USER_ID` would grant broad owner authority to any prompt reaching that bot.
- If the original owner submission failed before capture, no saved receipt exists in SQLite; a bot message cannot prove the original owner URL or thread provenance.

## Proposed Design: Host-Authenticated Native Kanban Handoff

Keep Discord bot mentions fail-closed. No currently verified Media Scout interface accepts a delegated retry grant. `NativeBridge.ensure_review` routes and verifies an already-authorized review; it does not grant extraction authority. Hermes Kanban can carry an opaque request reference, but board membership and task contents are not proof of the owner's consent. Native clarification can collect a choice; its forwarded text is not an authorization credential. A future implementation needs an authenticated grant channel and must fail closed if the supported interfaces cannot provide one.

Until then, the owner should resend the original link in the configured intake thread if no receipt exists, or request a retry directly under their own identity if it does. If a stale exclusive claim blocks the retry, the owner must first confirm the old writer has stopped and use the documented owner-only release command.

A proposal for an authenticated grant and Kanban transport follows:

1. **Existing Receipt Prerequisite**:
   - A delegated retry may target only a `media_id` that already has a saved owner `receipts` row in the configured `guild_id`, `parent_channel_id`, and `thread_id`.
   - If no saved receipt exists, fail closed and return an actionable owner-resend instruction.
2. **Bound Retry Payload**:
   - A trusted service must record an expiring, revocable grant from the authenticated owner. Bind it to the exact receipt and source, original guild/channel/thread, delegate principal, operation, consent scope, and attempt cap.
   - Pass only the opaque grant reference through native Kanban. Require the dispatcher to obtain delegate identity from trusted runtime context and match it to the stored grant. A caller-supplied timestamp, identity, or task body is not proof of consent.
   - Reserve attempts atomically against the grant and operation. On an ambiguous dispatch, verify the existing claim or review task before allowing another attempt.
3. **Admission and Safeguards**:
   - Verify `media_id`, `owner_id`, `source_url`, and `thread_id` against the local `receipts` table.
   - Preserve `_owner_intent_overrides_review` and opt-out rules.
   - Record `submitted_by = owner_id` separately from `retry_requested_by = requested_by_profile`.
   - Enforce idempotency and bounded attempt counts so duplicate requests do not create duplicate claims, duplicate review tasks, or bot reply loops.
   - A retry never authorizes tool installs, repository edits, merges, publication, or deployment.

## Threat Model Summary

| Threat | Control |
| --- | --- |
| Untrusted bot or user mentions Scout in Discord | Fails closed at `HERMES_SESSION_USER_ID != owner_id` |
| Mismatched source URL, media ID, or thread | Rejected against saved `receipts` row |
| Replay or duplicate retry dispatch | Deduplicated by `idempotency_key`; distinct pending/blocked/completed states |
| Missing or revoked owner consent / opt-out | Fails closed before extraction or review dispatch |
| Uncaptured initial owner message | Fails closed with owner-resend fallback |

## Next Steps

1. Owner sign-off on the native Kanban retry handoff contract.
2. Offline synthetic positive/negative tests at the admission and dispatch boundary.
3. Separately authorized bounded live pilot in a single thread after offline and security review.
