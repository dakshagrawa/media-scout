# Summary-First Backlog Reconciliation Reference

## Purpose

This reference defines a bounded, resumable workflow for Media Scout backlog reconciliation. The workflow checks summary quality first, collects structured bulk decisions through native `clarify` batches, and runs only approved actions.

## State Storage

Reconciliation state persists in `reconcile.sqlite` inside the Media Scout data directory. It never lives inside replaceable plugin code directories. Imported v1 history records in `data.db` stay read-only.

## Offline Prototype

This module is not registered as a Media Scout tool. The tests use synthetic snapshots and injected callbacks; they do not verify Discord pagination, native `clarify` response binding, or live Kanban readback. Do not connect the prototype to a production account or treat a model-supplied answer or callback receipt as owner approval.

1. `create_inventory_run` records a snapshot and provenance labels. It does not discover remote threads. Mark incomplete enumeration as partial or blocked and record the reason.
2. `validate_summary_coverage` flags empty summaries, common placeholders and error replies. It is a heuristic, not proof that the summary is source-grounded.
3. `run_gap_intake` exercises bounded recovery with a synthetic fetcher; it does not dispatch Scout.
4. `build_clarify_spec` previews batches of up to five questions with up to four choices each. Native `clarify` remains the intended decision surface; its response is not bound to this ledger yet.
5. `record_decisions` stores local prototype choices. `execute_decisions` exercises local bookkeeping and a synthetic task boundary. A missing or mismatched callback readback is unconfirmed, never completion and never automatically redispatched.

## Before Live Use

Implement and test trusted pagination and starter validation, authenticated owner decisions tied to an exact inventory/evidence revision, scoped actions and real target readback, and recovery of unconfirmed operations. Qualify these boundaries offline, then run a separately authorized pilot. No live backlog processing or migration is part of this prototype.
