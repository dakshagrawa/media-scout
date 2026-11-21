# Date-Bounded Source Discovery Contract

## Purpose

This reference defines an optional, standalone provenance contract for finding recent posts in a fixed date window across multiple platforms. It stays separate from saved-item intake and from bulk backlog reconciliation.

## Required Inputs

Every discovery packet requires four inputs:

1. A named research question.
2. A date window with ISO start and end dates (`start <= end`).
3. An explicit list of target platforms.
4. A bounded acquisition budget (`max_items`, `max_requests_per_platform`, and `max_cost_usd`).

## Provenance and Deduplication Rules

- Record both `original_url` and `canonical_url` for every source.
- Distinguish publication dates with `published_at_provenance`: `observed`, `estimated`, or `unavailable`. Never present an estimate or retrieval timestamp as an observed publication date.
- Deduplicate exact `canonical_url` matches into one entry and list the extra URLs under `duplicate_urls`.
- Keep distinct posts about the same product or topic as separate entries. Share a `related_topic` label instead of merging them.
- Record per-platform coverage as `covered`, `partial`, `blocked`, or `unavailable`, with a required `reason` whenever coverage is not `covered`.
- Set `full_coverage` to `true` only when every requested platform is `covered` for the full requested date window.
- Track `unverified_claims` and `stop_conditions` explicitly.

## Authorization Boundary

This contract enables no credentials, paid APIs, sign-in sessions, tool installs, or automatic media intake. It ends at a structured discovery packet.
