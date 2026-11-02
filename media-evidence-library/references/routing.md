# Native reviewer routing

The intake profile owns the user-facing thread; the reviewer runs as a separate native Kanban worker session. Do not add a second conversational bot or claim injection into an arbitrary existing Desktop chat. Use the configured review board and reviewer profile, never assume another installation has the same IDs.

1. Read actual source/owner/thread metadata, current packet, local consent policy and matching task/result references. Standing review authorization must be configured by the owner; otherwise ask before dispatch. Local-only/stop/defer/reject overrides it. Fixtures and historical records do not acquire consent automatically.
2. Include the full review contract, concise evidence, coverage/gaps, source references, purpose, packet identity and REVIEW / PRIVATE KNOWLEDGE CAPTURE ONLY boundary in the task body. Do not forward unrelated history, credentials or private memories.
3. Use visible native `kanban_create`/`kanban_show` tools. A toolset called kanban is not itself callable; an empty deferred search is not proof the native CLI is missing.
4. Use a stable media+packet idempotency key, finite runtime, reviewer assignee and local-only completion contract. Where source subscription is not exposed in a model tool, use the installed native CLI: create initially blocked, `notify-subscribe`, `notify-list`, `show`, then `unblock`. Inspect `hermes kanban --help` and relevant subcommand help first; do not invent flags or use raw SQL.
5. Verify exact task, owner, source thread/parent/guild, notifier profile, notify+wake delivery mode, evidence attachments and assignee before release. Persist the actual task ID and authorization basis before unblock. Missing routing is a blocker, not successful delivery.
6. Only the reviewer completes its review. Native completion wakes intake to read the actual report, save retained learning and relay in the same thread. Read back task completion and independently observe delivery before claiming the whole loop passed.

Quota recovery reuses the native same-task cooldown path; do not create replacements or claim model-independent all-history discovery. A requested proposal is not approval to execute it. Informational results do not need a blocking choice prompt.
