# Verification scope

- Explicit setup allowlist and deterministic sanitization; privacy-pattern checks and independent read-only review.
- Both complete local skill packages received native skills-guard-v10 SAFE verdicts, allowed as agent-created, zero findings; this does not waive future admission.
- Full cron prompts were compared against their source after sanitization, with whitespace-only wrapping for review. Long-line tool display truncation was independently distinguished from persisted truncation; no missing prompt text was invented.
- Public manifest and ZIP extraction/hash roundtrip; JSON/YAML syntax and linked skill reference closure; original offline plugin/skill contracts plus snapshot-specific contracts.
- Private archive: every entry extracted into disconnected scratch and checked against its SHA-256 manifest; three SQLite online backups passed integrity checks. No private archive or locator is included publicly.

## Platform qualification boundary

The original full workflow-dispatch run exposed the preexisting native bridge's intentional Windows rejection and an existing plugin replay/byte expectation failure on Windows. No plugin implementation or original tests were changed or skipped to disguise this. A new snapshot-specific test also used host path separators; that test was corrected to canonical POSIX manifest paths. The dedicated setup qualification runs the full original-plus-snapshot suite on Linux/macOS, and only the archive/sanitization contracts on Windows. Windows archive success is not Windows plugin or restored-profile support. The captured workflow and local skill metadata remain Linux-scoped.

No live cutover, rollback, credential migration, model/provider call or Discord submission was performed by the release process. Historical live acceptance is not automatically acceptance of a rebuilt deployment. Keep the original runtime and private backup until separate real acceptance passes. Offline test counts and exact source revision are recorded in release notes after execution, not invented here.
