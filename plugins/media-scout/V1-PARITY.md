# v1 information parity and retained boundaries

| v1 information or behavior | Current Media Scout equivalent | Boundary / remaining gap |
|---|---|---|
| Saved source URLs, media IDs, titles, summaries, topics, entities, creator claims, coverage and extraction states | Owner-scoped historical `search` and `history_get`; original record JSON retained | Imported as historical facts, not current native authority |
| Evidence, review, proposal, preview, wiki, template, receipt and test files; five named root policy/report files | Copied byte-for-byte with source-relative paths, SHA-256 and provenance; per-record artifacts are bounded | Unassociated files are discoverable using bounded `history_files` and retrievable via `history_artifact`; raw video cache intentionally excluded |
| Source thread and review-task references | Retained verbatim in raw record and provenance | No receipt, task, review result, approval or dispatch is recreated |
| Historical approvals, authorization fields, policy files and receipts | Available as historical record/file information | Context only; cannot grant current permission or authorize consequential action, execute policy, or create native admission |
| Supported-source canonical identity and unsupported URLs | Parser identity indexed at import; unsupported records retain exact URL and raw data | Unsupported platforms do not gain extraction support |
| Partial, blocked or missing evidence | Status and missing-reference metadata preserved; missing evidence requires explicit importer opt-in | Missing files are not synthesized or treated as complete |
| Existing latest native catalog | Additive history tables and separate storage; current native receipt, claim, task and owner state remain native | Parent must validate against protected real data before any live import |
| Retrieval before new work | Main workflow requires cache-first search and on-demand detail | Source changes, explicit revisit, or incomplete/stale coverage can warrant incremental work; no automatic reacquisition |

The importer is explicit-root, stdlib-only, dry-run by default, and does not access the legacy library at runtime. This parity describes retained information, not a promise of universal acquisition or exact behavioral equivalence.
