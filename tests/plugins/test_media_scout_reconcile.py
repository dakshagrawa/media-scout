"""Offline synthetic contract tests for summary-first backlog reconciliation (#4)."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "media-scout"

GOOD_SUMMARY = (
    "Substantive source-grounded summary covering architecture, measured tradeoffs, "
    "benchmark numbers, and concrete follow-up steps verified from primary evidence."
)


def _load_pkg():
    pkg_name = "ms_reconcile_pkg"
    if pkg_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg_name,
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg_name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[pkg_name], importlib.import_module(f"{pkg_name}.reconcile")


def test_substantive_summary_validator():
    _, rec = _load_pkg()
    assert rec.validate_summary_coverage("")[0] == "missing"
    assert rec.validate_summary_coverage("TODO: fill in later")[0] == "partial_or_stub"
    assert rec.validate_summary_coverage("Short stub")[0] == "partial_or_stub"
    assert rec.validate_summary_coverage("configured owner identity required")[0] == "blocked"
    assert rec.validate_summary_coverage("Error: failed to summarize video")[0] == "failed"
    status, findings = rec.validate_summary_coverage(GOOD_SUMMARY)
    assert status == "complete" and findings == []


def test_inventory_provenance_dedup_and_readonly_history(tmp_path: Path):
    pkg, rec = _load_pkg()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "data.db"
    db = sqlite3.connect(db_path)
    pkg.initialize(db)
    rec_json = json.dumps({"media_id": "hist-1", "title": "Old Item", "summary": GOOD_SUMMARY})
    sha = hashlib.sha256(rec_json.encode()).hexdigest()
    db.execute("INSERT INTO history_imports VALUES('b1','owner-1','{}',datetime('now'))")
    db.execute(
        "INSERT INTO history_records VALUES('rk1','b1','owner-1','hist-1','https://example.com/old','https://example.com/old',?,'records/old.json',?,?, '', 'old', '[]', '{}')",
        (rec_json, sha, sha),
    )
    db.commit()
    db.close()
    before_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()

    run = rec.create_inventory_run(
        data_dir,
        "owner-1",
        items=[
            {
                "item_id": "t-1",
                "thread_id": "thr-1",
                "source_url": "https://example.com/post/42",
                "title": "Ready Thread",
                "summary": GOOD_SUMMARY,
                "discovery_source": "fresh_readback",
                "discovery_status": "complete",
            },
            {
                "item_id": "t-2",
                "thread_id": "thr-2",
                "source_url": "https://example.com/post/42/",
                "title": "Duplicate Thread",
                "summary": GOOD_SUMMARY,
                "discovery_source": "local_snapshot",
                "discovery_status": "partial",
                "discovery_reason": "pagination limit reached",
            },
            {
                "item_id": "t-3",
                "thread_id": "thr-3",
                "source_url": "https://example.com/post/99",
                "title": "Author Mismatch",
                "summary": GOOD_SUMMARY,
                "discovery_source": "author_mismatch",
                "discovery_status": "complete",
            },
        ],
        include_history=True,
    )
    assert run["ok"] is True
    assert run["coverage_status"] == "partial"
    assert "pagination limit reached" in run["coverage_reason"]
    by_id = {it["item_id"]: it for it in run["items"]}
    assert by_id["t-1"]["summary_status"] == "complete"
    assert by_id["t-2"]["duplicate_of"] == "t-1"
    assert by_id["t-2"]["thread_id"] == "thr-2"
    assert by_id["t-3"]["summary_status"] == "blocked"
    assert "hist:hist-1" in by_id and by_id["hist:hist-1"]["discovery_source"] == "historical_import"
    # data.db (including v1 history) was strictly untouched
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before_hash
    assert (data_dir / "reconcile.sqlite").exists()


def test_bounded_resumable_gap_intake_and_blocker_stop(tmp_path: Path):
    _, rec = _load_pkg()
    data_dir = tmp_path / "data"
    run = rec.create_inventory_run(
        data_dir,
        "owner-1",
        items=[
            {"item_id": "i1", "title": "Gap 1", "summary": ""},
            {"item_id": "i2", "title": "Gap 2", "summary": "TODO"},
            {"item_id": "i3", "title": "Gap 3", "summary": ""},
            {"item_id": "i4", "title": "Opted Out", "summary": "", "opted_out": True},
        ],
        include_live_db=False,
    )
    run_id = run["run_id"]

    def fake_fetcher(item):
        if item["item_id"] == "i1":
            return {"outcome": "succeeded", "summary": GOOD_SUMMARY}
        if item["item_id"] == "i2":
            return {"outcome": "blocked_rate_limit", "detail": "429 retry after 60s"}
        return {"outcome": "succeeded", "summary": GOOD_SUMMARY}

    res = rec.run_gap_intake(data_dir, "owner-1", run_id, fetcher=fake_fetcher, max_items=5, max_attempts=1)
    assert res["ok"] is True
    assert res["stopped_reason"] == "blocked_rate_limit"
    outcomes = {r["item_id"]: r["outcome"] for r in res["results"]}
    assert outcomes["i1"] == "succeeded"
    assert outcomes["i2"] == "blocked_rate_limit"
    assert "i3" not in outcomes

    # Resume skips i2 (at max_attempts with no state change), completes i3, skips i4 by policy
    res2 = rec.run_gap_intake(data_dir, "owner-1", run_id, fetcher=fake_fetcher, max_items=5, max_attempts=1)
    outcomes2 = {r["item_id"]: r["outcome"] for r in res2["results"]}
    assert outcomes2["i2"] == "skipped_by_policy"
    assert outcomes2["i3"] == "succeeded"
    assert outcomes2["i4"] == "skipped_by_policy"


def test_clarify_batches_decisions_idempotency_and_readback(tmp_path: Path):
    _, rec = _load_pkg()
    data_dir = tmp_path / "data"
    items = [
        {"item_id": f"item-{i}", "thread_id": f"thr-{i}", "title": f"Item {i}", "summary": GOOD_SUMMARY}
        for i in range(1, 8)
    ]
    items.append({"item_id": "item-optout", "thread_id": "thr-opt", "title": "Private", "summary": GOOD_SUMMARY, "opted_out": True})
    run = rec.create_inventory_run(data_dir, "owner-1", items=items, include_live_db=False)
    run_id = run["run_id"]

    spec = rec.build_clarify_spec(data_dir, "owner-1", run_id)
    assert spec["ok"] is True
    assert spec["batch_count"] == 2
    assert all(len(b) <= 5 for b in spec["batches"])
    assert all(len(q["choices"]) <= 4 for b in spec["batches"] for q in b)

    # Cancel resolves fail-closed to noop
    cancel_res = rec.record_decisions(data_dir, "owner-1", run_id, decisions=[], clarify_outcome="cancelled")
    assert cancel_res["ok"] is True
    assert all(d["action"] == "noop" for d in cancel_res["recorded"])

    # Submit explicit decisions; opted-out external action is rejected
    dec_res = rec.record_decisions(
        data_dir,
        "owner-1",
        run_id,
        decisions=[
            {"item_id": "item-1", "action": "keep_summary_only"},
            {"item_id": "item-2", "action": "create_kanban_card", "target_board": "media-review", "target_tenant": "owner-1"},
            {"item_id": "item-3", "action": "create_kanban_card", "target_board": "wrong-board", "target_tenant": "owner-1"},
            {"item_id": "item-4", "action": "create_kanban_card", "target_board": "media-review", "target_tenant": "owner-1"},
            {"item_id": "item-optout", "action": "create_kanban_card", "target_board": "media-review"},
        ],
    )
    assert len(dec_res["rejected"]) == 1 and dec_res["rejected"][0]["item_id"] == "item-optout"

    calls = []

    def fake_kanban(req):
        calls.append(req["item"]["item_id"])
        if req["item"]["item_id"] == "item-4":
            # Missing readback must fail verification
            return {"task_id": "task-unverified", "readback": None}
        return {"task_id": "task-100", "readback": {"id": "task-100", "board": req["board"], "tenant": req["tenant"]}}

    exec1 = rec.execute_decisions(
        data_dir,
        "owner-1",
        run_id,
        kanban_executor=fake_kanban,
        allowed_boards={"media-review"},
        expected_tenant="owner-1",
    )
    assert exec1["ok"] is True
    assert "item-1" in exec1["grouped"]["verified"]
    assert "item-2" in exec1["grouped"]["verified"]
    assert "item-3" in exec1["grouped"]["blocked"]
    assert "item-4" in exec1["grouped"]["unconfirmed"]
    assert calls == ["item-2", "item-4"]

    # Re-running execute_decisions reuses verified idempotency keys without duplicate Kanban creation
    exec2 = rec.execute_decisions(
        data_dir,
        "owner-1",
        run_id,
        kanban_executor=fake_kanban,
        allowed_boards={"media-review"},
        expected_tenant="owner-1",
    )
    assert "item-1" in exec2["grouped"]["reused_verified"]
    assert "item-2" in exec2["grouped"]["reused_verified"]
    assert "item-4" in exec2["grouped"]["unconfirmed"]
    assert calls == ["item-2", "item-4"]

    # Action-effect matrix forbids kanban_write on keep_summary_only
    ok_eff, _ = rec.check_action_effect("keep_summary_only", "kanban_write")
    assert ok_eff is False


def test_missing_catalog_is_not_complete(tmp_path: Path):
    _, rec = _load_pkg()
    run = rec.create_inventory_run(tmp_path, "owner-1")
    assert run["coverage_status"] == "blocked"
    assert run["item_count"] == 0
    assert "catalog unavailable" in run["coverage_reason"]
    assert not (tmp_path / "data.db").exists()


def test_ambiguous_callback_exception_survives_restart(tmp_path: Path):
    _, rec = _load_pkg()
    run = rec.create_inventory_run(tmp_path, "owner-1", items=[{"item_id": "one", "summary": GOOD_SUMMARY}], include_live_db=False)
    run_id = run["run_id"]
    result = rec.record_decisions(tmp_path, "owner-1", run_id, decisions=[
        {"item_id": "one", "action": "create_kanban_card", "target_board": "media-review", "target_tenant": "test"}
    ])
    assert len(result["recorded"]) == 1
    calls = []

    def fake_dispatch(request):
        calls.append(request["idempotency_key"])
        raise TimeoutError("response lost after dispatch")

    args = (tmp_path, "owner-1", run_id)
    assert rec.execute_decisions(*args, kanban_executor=fake_dispatch)["grouped"]["blocked"] == ["one"]
    assert not calls
    for _ in range(2):
        result = rec.execute_decisions(*args, kanban_executor=fake_dispatch, allowed_boards={"media-review"}, expected_tenant="test")
        assert result["grouped"]["unconfirmed"] == ["one"]
    assert len(calls) == 1
    assert rec.get_run_status(*args)["executions"][0]["status"] == "unconfirmed"
