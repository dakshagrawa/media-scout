"""Summary-first backlog reconciliation, native clarify batching, and resumable verified execution (#4)."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from .sources import parse_source_url, parse_web_identity

SCHEMA_VERSION = "1.0"
MAX_CLARIFY_QUESTIONS = 5
MAX_CLARIFY_CHOICES = 4

ALLOWED_ACTIONS = {
    "noop",
    "defer",
    "keep_summary_only",
    "retry_summary",
    "create_kanban_card",
    "link_existing_task",
    "mark_reviewed",
    "archive_local",
}

FORBIDDEN_EFFECTS: dict[str, set[str]] = {
    "noop": {"local_write", "kanban_write", "external_publish", "plugin_install", "history_mutate"},
    "defer": {"local_write", "kanban_write", "external_publish", "plugin_install", "history_mutate"},
    "keep_summary_only": {"kanban_write", "external_publish", "plugin_install", "history_mutate"},
    "retry_summary": {"kanban_write", "external_publish", "plugin_install", "history_mutate"},
    "create_kanban_card": {"external_publish", "plugin_install", "history_mutate"},
    "link_existing_task": {"external_publish", "plugin_install", "history_mutate"},
    "mark_reviewed": {"kanban_write", "external_publish", "plugin_install", "history_mutate"},
    "archive_local": {"kanban_write", "external_publish", "plugin_install", "history_mutate"},
}

PROVENANCE_SOURCES = {
    "fresh_readback",
    "local_snapshot",
    "historical_import",
    "author_mismatch",
    "source_mismatch",
    "starter_unavailable",
}

UNTRUSTED_PROVENANCE = {"author_mismatch", "source_mismatch", "starter_unavailable"}

INTAKE_OUTCOMES = {
    "succeeded",
    "blocked_auth",
    "blocked_access",
    "blocked_rate_limit",
    "failed_transient",
    "skipped_by_policy",
}

_AUTH_BLOCK_PATTERNS = (
    "configured owner identity required",
    "401 unauthorized",
    "403 forbidden",
    "login required",
    "login wall",
    "permission denied",
    "rate limit",
)
_ERROR_PATTERNS = (
    "error:",
    "failed to ",
    "exception:",
    "traceback",
    "timed out",
    "timeout",
)
_STUB_PATTERNS = (
    "todo",
    "tbd",
    "placeholder",
    "pending summary",
    "not yet summarized",
    "working on it",
    "queued for review",
)
_OPT_OUT_RE = re.compile(
    r"\b(no\s+review|skip\s+review|do\s+not\s+review|don't\s+review|keep\s+private|local\s+only|do\s+not\s+share|no\s+sharing|archive\s+only)\b",
    re.IGNORECASE,
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _norm(val: Any) -> str:
    return str(val or "").strip()


def _canonical_url(url: str) -> str:
    text = _norm(url)
    if not text:
        return ""
    parsed = parse_source_url(text) or parse_web_identity(text)
    candidate = parsed.canonical_url if parsed else text
    try:
        parts = urlsplit(candidate)
        if parts.scheme in {"http", "https"} and parts.netloc:
            path = parts.path.rstrip("/") or "/"
            return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))
    except ValueError:
        pass
    return candidate


def _connect(data_dir: Path) -> sqlite3.Connection:
    root = Path(data_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "reconcile.sqlite")
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS reconcile_runs (
        run_id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        schema_version TEXT NOT NULL,
        coverage_status TEXT NOT NULL,
        coverage_reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reconcile_items (
        run_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        media_id TEXT NOT NULL DEFAULT '',
        thread_id TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT '',
        canonical_url TEXT NOT NULL DEFAULT '',
        duplicate_of TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        summary_status TEXT NOT NULL,
        summary_findings_json TEXT NOT NULL DEFAULT '[]',
        discovery_source TEXT NOT NULL,
        discovery_status TEXT NOT NULL,
        discovery_reason TEXT NOT NULL DEFAULT '',
        opted_out INTEGER NOT NULL DEFAULT 0,
        intake_attempts INTEGER NOT NULL DEFAULT 0,
        intake_status TEXT NOT NULL DEFAULT '',
        intake_detail TEXT NOT NULL DEFAULT '',
        local_state TEXT NOT NULL DEFAULT 'open',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (run_id, item_id)
    );
    CREATE TABLE IF NOT EXISTS reconcile_decisions (
        decision_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        action TEXT NOT NULL,
        scope_json TEXT NOT NULL DEFAULT '{}',
        scope_hash TEXT NOT NULL,
        target_board TEXT NOT NULL DEFAULT '',
        target_tenant TEXT NOT NULL DEFAULT '',
        existing_task_id TEXT NOT NULL DEFAULT '',
        clarify_outcome TEXT NOT NULL,
        confirmed_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reconcile_executions (
        idempotency_key TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        decision_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        owner_id TEXT NOT NULL,
        action TEXT NOT NULL,
        status TEXT NOT NULL,
        verified_readback INTEGER NOT NULL DEFAULT 0,
        target_ref TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );
    """)
    return db


def check_action_effect(action: str, effect: str) -> tuple[bool, str | None]:
    if action not in ALLOWED_ACTIONS:
        return False, f"unknown action: {action}"
    if effect in FORBIDDEN_EFFECTS.get(action, set()):
        return False, f"action '{action}' forbids effect '{effect}'"
    return True, None


def validate_summary_coverage(
    summary: str | None,
    *,
    min_chars: int = 60,
    min_words: int = 10,
) -> tuple[str, list[str]]:
    text = _norm(summary)
    if not text:
        return "missing", ["empty_summary"]
    low = text.casefold()
    for pat in _AUTH_BLOCK_PATTERNS:
        if pat in low:
            return "blocked", [f"blocked_marker:{pat}"]
    for pat in _ERROR_PATTERNS:
        if pat in low:
            return "failed", [f"error_marker:{pat}"]
    findings: list[str] = []
    for pat in _STUB_PATTERNS:
        if pat in low:
            findings.append(f"stub_marker:{pat}")
    compact_len = len(re.sub(r"\s+", " ", text))
    words = [w for w in re.split(r"\s+", text) if w]
    if compact_len < min_chars:
        findings.append("too_short")
    if len(words) < min_words:
        findings.append("too_few_words")
    if findings:
        return "partial_or_stub", findings
    return "complete", []


def _read_live_and_history(data_dir: Path, owner_id: str, *, include_live: bool, include_history: bool, history_limit: int) -> list[dict[str, Any]]:
    db_path = Path(data_dir).expanduser() / "data.db"
    if not db_path.exists():
        return []
    out: list[dict[str, Any]] = []
    conn = sqlite3.connect(db_path.absolute().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if include_live and {"media", "receipts"}.issubset(tables):
            rows = conn.execute(
                """
                SELECT m.media_id, m.summary, m.coverage, m.evidence_hash, m.evidence_path,
                       r.thread_id, r.source_url, r.source_text
                FROM media m
                JOIN receipts r ON r.media_id = m.media_id
                WHERE r.owner_id = ?
                ORDER BY r.created_at, r.rowid
                """,
                (owner_id,),
            ).fetchall()
            seen_threads: set[tuple[str, str]] = set()
            for row in rows:
                mid = row["media_id"]
                thread = row["thread_id"] or ""
                key = (mid, thread)
                if key in seen_threads:
                    continue
                seen_threads.add(key)
                opted = bool(_OPT_OUT_RE.search(row["source_text"] or ""))
                src_url = row["source_url"] or ""
                out.append({
                    "item_id": f"live:{mid}:{thread}",
                    "media_id": mid,
                    "thread_id": thread,
                    "source_url": src_url,
                    "canonical_url": _canonical_url(src_url),
                    "title": mid,
                    "summary": row["summary"] or "",
                    "discovery_source": "local_snapshot",
                    "discovery_status": "complete",
                    "opted_out": opted,
                })
        if include_history and "history_records" in tables:
            hrows = conn.execute(
                "SELECT media_id, source_url, record_json FROM history_records WHERE owner_id = ? ORDER BY rowid LIMIT ?",
                (owner_id, history_limit + 1),
            ).fetchall()
            for hrow in hrows:
                rec = json.loads(hrow["record_json"]) if hrow["record_json"] else {}
                out.append({
                    "item_id": f"hist:{hrow['media_id']}",
                    "media_id": hrow["media_id"],
                    "thread_id": _norm(rec.get("thread_id")),
                    "source_url": hrow["source_url"] or "",
                    "canonical_url": _canonical_url(hrow["source_url"] or ""),
                    "title": _norm(rec.get("title")) or hrow["media_id"],
                    "summary": _norm(rec.get("summary")),
                    "discovery_source": "historical_import",
                    "discovery_status": "complete",
                    "opted_out": False,
                })
    finally:
        conn.close()
    return out


def create_inventory_run(
    data_dir: Path | str,
    owner_id: str,
    *,
    items: list[dict[str, Any]] | None = None,
    include_live_db: bool = True,
    include_history: bool = False,
    history_limit: int = 50,
    discovery_status: str | None = None,
    discovery_reason: str = "",
) -> dict[str, Any]:
    owner = _norm(owner_id)
    if not owner:
        return {"ok": False, "error": "owner_id required"}
    root = Path(data_dir).expanduser()
    combined: list[dict[str, Any]] = []
    if items:
        combined.extend(items)
    if include_live_db or include_history:
        history_limit = max(1, min(int(history_limit or 50), 200))
        snapshot = _read_live_and_history(root, owner, include_live=include_live_db, include_history=include_history, history_limit=history_limit)
        if not (root / "data.db").is_file():
            discovery_status = "partial" if items else "blocked"
            discovery_reason = "; ".join(filter(None, [discovery_reason, "local catalog unavailable"]))
        elif include_history and sum(row["discovery_source"] == "historical_import" for row in snapshot) > history_limit:
            snapshot = [row for i, row in enumerate(snapshot) if i < len(snapshot) - 1]
            if discovery_status != "blocked":
                discovery_status = "partial"
            discovery_reason = "; ".join(filter(None, [discovery_reason, "history enumeration limit reached"]))
        existing_ids = {_norm(it.get("item_id")) for it in combined}
        for row in snapshot:
            if row["item_id"] not in existing_ids:
                combined.append(row)
                existing_ids.add(row["item_id"])

    if discovery_status not in {None, "complete", "partial", "blocked"}:
        return {"ok": False, "error": "invalid run discovery status"}
    run_id = f"rec-{uuid.uuid4().hex[:12]}"
    now = _now()
    statuses: set[str] = set()
    reasons: list[str] = []
    if discovery_status:
        statuses.add(_norm(discovery_status))
    if _norm(discovery_reason):
        reasons.append(_norm(discovery_reason))

    seen_canonical: dict[str, str] = {}
    saved_items: list[dict[str, Any]] = []
    db = _connect(root)
    try:
        for idx, raw in enumerate(combined, 1):
            item_id = _norm(raw.get("item_id")) or f"item-{idx}"
            source_url = _norm(raw.get("source_url") or raw.get("url"))
            canon = _canonical_url(_norm(raw.get("canonical_url")) or source_url)
            duplicate_of = ""
            if canon:
                if canon in seen_canonical:
                    duplicate_of = seen_canonical[canon]
                else:
                    seen_canonical[canon] = item_id
            disc_src = _norm(raw.get("discovery_source") or "local_snapshot")
            if disc_src not in PROVENANCE_SOURCES:
                return {"ok": False, "error": f"invalid discovery_source: {disc_src}"}
            disc_stat = _norm(raw.get("discovery_status") or "complete")
            if disc_stat not in {"complete", "partial", "blocked"}:
                return {"ok": False, "error": f"invalid discovery_status: {disc_stat}"}
            disc_reason = _norm(raw.get("discovery_reason"))
            if disc_stat != "complete":
                statuses.add(disc_stat)
                if disc_reason and disc_reason not in reasons:
                    reasons.append(disc_reason)
            summary = _norm(raw.get("summary"))
            sum_status, findings = validate_summary_coverage(summary)
            if disc_src in UNTRUSTED_PROVENANCE:
                findings.append(f"provenance:{disc_src}")
                if sum_status == "complete":
                    sum_status = "blocked"
            opted_out = bool(raw.get("opted_out", False)) or bool(_OPT_OUT_RE.search(_norm(raw.get("source_text"))))
            rec = {
                "item_id": item_id,
                "media_id": _norm(raw.get("media_id")),
                "thread_id": _norm(raw.get("thread_id")),
                "source_url": source_url,
                "canonical_url": canon,
                "duplicate_of": duplicate_of,
                "title": _norm(raw.get("title")) or item_id,
                "summary": summary,
                "summary_status": sum_status,
                "summary_findings": findings,
                "discovery_source": disc_src,
                "discovery_status": disc_stat,
                "discovery_reason": disc_reason,
                "opted_out": opted_out,
                "intake_attempts": 0,
                "intake_status": "",
                "intake_detail": "",
                "local_state": "open",
            }
            db.execute(
                """
                INSERT INTO reconcile_items(
                    run_id, item_id, owner_id, media_id, thread_id, source_url, canonical_url,
                    duplicate_of, title, summary, summary_status, summary_findings_json,
                    discovery_source, discovery_status, discovery_reason, opted_out,
                    intake_attempts, intake_status, intake_detail, local_state, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, item_id, owner, rec["media_id"], rec["thread_id"], source_url, canon,
                    duplicate_of, rec["title"], summary, sum_status, json.dumps(findings),
                    disc_src, disc_stat, disc_reason, 1 if opted_out else 0,
                    0, "", "", "open", now, now,
                ),
            )
            saved_items.append(rec)

        if "blocked" in statuses:
            cov_status = "blocked"
        elif "partial" in statuses:
            cov_status = "partial"
        else:
            cov_status = "complete"
        cov_reason = "; ".join(reasons)
        db.execute(
            "INSERT INTO reconcile_runs VALUES (?,?,?,?,?,?,?)",
            (run_id, owner, SCHEMA_VERSION, cov_status, cov_reason, now, now),
        )
        db.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "schema_version": SCHEMA_VERSION,
            "coverage_status": cov_status,
            "coverage_reason": cov_reason,
            "item_count": len(saved_items),
            "items": saved_items,
        }
    finally:
        db.close()


def get_run_status(data_dir: Path | str, owner_id: str, run_id: str) -> dict[str, Any]:
    db = _connect(Path(data_dir))
    try:
        run = db.execute("SELECT * FROM reconcile_runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if not run:
            return {"ok": False, "error": "reconciliation run not found"}
        items = [dict(r) for r in db.execute("SELECT * FROM reconcile_items WHERE run_id=? AND owner_id=? ORDER BY rowid", (run_id, owner_id))]
        decisions = [dict(r) for r in db.execute("SELECT * FROM reconcile_decisions WHERE run_id=? AND owner_id=? ORDER BY rowid", (run_id, owner_id))]
        execs = [dict(r) for r in db.execute("SELECT * FROM reconcile_executions WHERE run_id=? AND owner_id=? ORDER BY rowid", (run_id, owner_id))]
        return {
            "ok": True,
            "run": dict(run),
            "items": items,
            "decisions": decisions,
            "executions": execs,
        }
    finally:
        db.close()


def run_gap_intake(
    data_dir: Path | str,
    owner_id: str,
    run_id: str,
    *,
    fetcher: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    item_ids: list[str] | None = None,
    max_items: int = 10,
    max_attempts: int = 2,
    state_changed_items: set[str] | None = None,
) -> dict[str, Any]:
    if max_items <= 0 or max_attempts <= 0:
        return {"ok": False, "error": "max_items and max_attempts must be positive"}
    db = _connect(Path(data_dir))
    try:
        run = db.execute("SELECT * FROM reconcile_runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if not run:
            return {"ok": False, "error": "reconciliation run not found"}
        rows = db.execute(
            "SELECT * FROM reconcile_items WHERE run_id=? AND owner_id=? ORDER BY rowid",
            (run_id, owner_id),
        ).fetchall()
        target_set = set(item_ids) if item_ids is not None else None
        changed = state_changed_items or set()
        processed = 0
        stopped_reason = ""
        results: list[dict[str, Any]] = []
        now = _now()

        for row in rows:
            item = dict(row)
            iid = item["item_id"]
            if target_set is not None and iid not in target_set:
                continue
            if item["summary_status"] == "complete":
                continue
            if processed >= max_items:
                stopped_reason = "max_items_reached"
                break
            if item["opted_out"]:
                db.execute(
                    "UPDATE reconcile_items SET intake_status='skipped_by_policy', intake_detail='opted_out', updated_at=? WHERE run_id=? AND item_id=?",
                    (now, run_id, iid),
                )
                results.append({"item_id": iid, "outcome": "skipped_by_policy", "detail": "opted_out"})
                continue
            if item["discovery_source"] in UNTRUSTED_PROVENANCE:
                db.execute(
                    "UPDATE reconcile_items SET intake_status='skipped_by_policy', intake_detail=?, updated_at=? WHERE run_id=? AND item_id=?",
                    (f"untrusted_provenance:{item['discovery_source']}", now, run_id, iid),
                )
                results.append({"item_id": iid, "outcome": "skipped_by_policy", "detail": item["discovery_source"]})
                continue
            if item["intake_attempts"] >= max_attempts and iid not in changed:
                results.append({"item_id": iid, "outcome": "skipped_by_policy", "detail": "max_attempts_reached_no_state_change"})
                continue
            if fetcher is None:
                results.append({"item_id": iid, "outcome": "skipped_by_policy", "detail": "no_fetcher_configured"})
                continue

            processed += 1
            attempts = item["intake_attempts"] + 1
            fetched = fetcher(item) or {}
            outcome = _norm(fetched.get("outcome") or "failed_transient")
            if outcome not in INTAKE_OUTCOMES:
                outcome = "failed_transient"
            detail = _norm(fetched.get("detail"))
            new_summary = _norm(fetched.get("summary"))
            new_sum_status = item["summary_status"]
            new_findings = json.loads(item["summary_findings_json"] or "[]")

            if outcome == "succeeded":
                v_stat, v_find = validate_summary_coverage(new_summary)
                if v_stat == "complete":
                    new_sum_status, new_findings = v_stat, v_find
                else:
                    outcome = "failed_transient"
                    detail = detail or f"fetched_summary_invalid:{v_stat}"
                    new_sum_status, new_findings = v_stat, v_find

            db.execute(
                """
                UPDATE reconcile_items
                SET summary=?, summary_status=?, summary_findings_json=?,
                    intake_attempts=?, intake_status=?, intake_detail=?, updated_at=?
                WHERE run_id=? AND item_id=?
                """,
                (
                    new_summary or item["summary"], new_sum_status, json.dumps(new_findings),
                    attempts, outcome, detail, now, run_id, iid,
                ),
            )
            results.append({"item_id": iid, "outcome": outcome, "summary_status": new_sum_status, "detail": detail})
            if outcome in {"blocked_rate_limit", "blocked_auth"}:
                stopped_reason = outcome
                break

        db.execute("UPDATE reconcile_runs SET updated_at=? WHERE run_id=?", (now, run_id))
        db.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "processed": processed,
            "stopped_reason": stopped_reason or None,
            "results": results,
        }
    finally:
        db.close()


def build_clarify_spec(
    data_dir: Path | str,
    owner_id: str,
    run_id: str,
    *,
    max_questions_per_batch: int = MAX_CLARIFY_QUESTIONS,
) -> dict[str, Any]:
    batch_size = max(1, min(int(max_questions_per_batch or MAX_CLARIFY_QUESTIONS), MAX_CLARIFY_QUESTIONS))
    db = _connect(Path(data_dir))
    try:
        run = db.execute("SELECT * FROM reconcile_runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if not run:
            return {"ok": False, "error": "reconciliation run not found"}
        items = [dict(r) for r in db.execute("SELECT * FROM reconcile_items WHERE run_id=? AND owner_id=? ORDER BY rowid", (run_id, owner_id))]
        digest = {
            "complete": [],
            "needs_summary": [],
            "blocked": [],
            "opted_out": [],
            "duplicates": [],
        }
        questions: list[dict[str, Any]] = []
        for it in items:
            iid = it["item_id"]
            if it["duplicate_of"]:
                digest["duplicates"].append({"item_id": iid, "duplicate_of": it["duplicate_of"], "thread_id": it["thread_id"]})
                continue
            if it["opted_out"]:
                digest["opted_out"].append(iid)
                continue
            st = it["summary_status"]
            if st == "complete":
                digest["complete"].append(iid)
                choices = ["keep_summary_only", "create_kanban_card", "mark_reviewed", "defer"]
            elif st == "blocked":
                digest["blocked"].append(iid)
                choices = ["defer", "keep_summary_only", "archive_local", "noop"]
            else:
                digest["needs_summary"].append(iid)
                choices = ["retry_summary", "defer", "keep_summary_only", "archive_local"]
            questions.append({
                "item_id": iid,
                "question": f"Choose action for {it['title']} ({iid}, summary={st})",
                "choices": choices[:MAX_CLARIFY_CHOICES],
            })
        batches = [questions[i:i + batch_size] for i in range(0, len(questions), batch_size)]
        return {
            "ok": True,
            "run_id": run_id,
            "coverage_status": run["coverage_status"],
            "coverage_reason": run["coverage_reason"],
            "digest": digest,
            "batch_count": len(batches),
            "batches": batches,
        }
    finally:
        db.close()


def _scope_hash(action: str, scope: dict[str, Any], target_board: str, target_tenant: str, existing_task_id: str) -> str:
    payload = json.dumps(
        {"action": action, "scope": scope, "target_board": target_board, "target_tenant": target_tenant, "existing_task_id": existing_task_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def record_decisions(
    data_dir: Path | str,
    owner_id: str,
    run_id: str,
    *,
    decisions: list[dict[str, Any]],
    clarify_outcome: str = "submitted",
) -> dict[str, Any]:
    outcome = _norm(clarify_outcome) or "submitted"
    if outcome not in {"submitted", "cancelled", "timed_out", "undelivered"}:
        return {"ok": False, "error": f"invalid clarify_outcome: {outcome}"}
    db = _connect(Path(data_dir))
    try:
        run = db.execute("SELECT * FROM reconcile_runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if not run:
            return {"ok": False, "error": "reconciliation run not found"}
        items_by_id = {
            r["item_id"]: dict(r)
            for r in db.execute("SELECT * FROM reconcile_items WHERE run_id=? AND owner_id=?", (run_id, owner_id))
        }
        now = _now()
        recorded: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        if outcome != "submitted":
            for iid in items_by_id:
                did = f"dec-{uuid.uuid4().hex[:12]}"
                sh = _scope_hash("noop", {}, "", "", "")
                db.execute(
                    "INSERT INTO reconcile_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (did, run_id, iid, owner_id, "noop", "{}", sh, "", "", "", outcome, now),
                )
                recorded.append({"decision_id": did, "item_id": iid, "action": "noop", "clarify_outcome": outcome})
            db.commit()
            return {"ok": True, "run_id": run_id, "clarify_outcome": outcome, "recorded": recorded, "rejected": rejected}

        for entry in decisions:
            iid = _norm(entry.get("item_id"))
            action = _norm(entry.get("action"))
            if iid not in items_by_id:
                rejected.append({"item_id": iid, "error": "unknown item_id"})
                continue
            if action not in ALLOWED_ACTIONS:
                rejected.append({"item_id": iid, "error": f"disallowed action: {action}"})
                continue
            item = items_by_id[iid]
            if action in {"create_kanban_card", "link_existing_task", "retry_summary"} and (
                item["opted_out"] or item["duplicate_of"] or item["discovery_source"] in UNTRUSTED_PROVENANCE
            ):
                rejected.append({"item_id": iid, "error": "item is opted out, duplicated, or lacks trusted provenance"})
                continue
            target_board = _norm(entry.get("target_board"))
            target_tenant = _norm(entry.get("target_tenant"))
            existing_task_id = _norm(entry.get("existing_task_id"))
            if action in {"create_kanban_card", "link_existing_task"} and not target_board:
                rejected.append({"item_id": iid, "error": "target_board required for Kanban action"})
                continue
            if action == "link_existing_task" and not existing_task_id:
                rejected.append({"item_id": iid, "error": "existing_task_id required for link_existing_task"})
                continue
            scope = entry.get("scope") if isinstance(entry.get("scope"), dict) else {}
            sh = _scope_hash(action, scope, target_board, target_tenant, existing_task_id)
            did = f"dec-{uuid.uuid4().hex[:12]}"
            db.execute(
                "INSERT INTO reconcile_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (did, run_id, iid, owner_id, action, json.dumps(scope, sort_keys=True), sh, target_board, target_tenant, existing_task_id, outcome, now),
            )
            recorded.append({
                "decision_id": did,
                "item_id": iid,
                "action": action,
                "scope_hash": sh,
                "target_board": target_board,
            })
        db.commit()
        return {"ok": True, "run_id": run_id, "clarify_outcome": outcome, "recorded": recorded, "rejected": rejected}
    finally:
        db.close()


def _idempotency_key(owner_id: str, run_id: str, item_id: str, action: str, scope_hash: str) -> str:
    raw = f"{owner_id}:{run_id}:{item_id}:{action}:{scope_hash}".encode("utf-8")
    return "exec-" + hashlib.sha256(raw).hexdigest()[:24]


def execute_decisions(
    data_dir: Path | str,
    owner_id: str,
    run_id: str,
    *,
    kanban_executor: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    allowed_boards: set[str] | None = None,
    expected_tenant: str | None = None,
) -> dict[str, Any]:
    db = _connect(Path(data_dir))
    try:
        run = db.execute("SELECT * FROM reconcile_runs WHERE run_id=? AND owner_id=?", (run_id, owner_id)).fetchone()
        if not run:
            return {"ok": False, "error": "reconciliation run not found"}
        items_by_id = {
            r["item_id"]: dict(r)
            for r in db.execute("SELECT * FROM reconcile_items WHERE run_id=? AND owner_id=?", (run_id, owner_id))
        }
        # Use latest decision per item_id so scope changes supersede old decisions cleanly.
        latest_decisions: dict[str, dict[str, Any]] = {}
        for row in db.execute("SELECT * FROM reconcile_decisions WHERE run_id=? AND owner_id=? ORDER BY rowid", (run_id, owner_id)):
            latest_decisions[row["item_id"]] = dict(row)

        now = _now()
        ledger: list[dict[str, Any]] = []
        grouped: dict[str, list[str]] = {
            "verified": [],
            "reused_verified": [],
            "unconfirmed": [],
            "blocked": [],
            "failed": [],
            "noop_or_deferred": [],
        }

        for iid, dec in latest_decisions.items():
            item = items_by_id.get(iid)
            if not item:
                continue
            action = dec["action"]
            ikey = _idempotency_key(owner_id, run_id, iid, action, dec["scope_hash"])
            prior = db.execute("SELECT * FROM reconcile_executions WHERE idempotency_key=?", (ikey,)).fetchone()
            if prior and prior["verified_readback"] == 1:
                ledger.append({
                    "item_id": iid,
                    "thread_id": item["thread_id"],
                    "action": action,
                    "status": "reused_verified",
                    "target_ref": prior["target_ref"],
                    "idempotency_key": ikey,
                })
                grouped["reused_verified"].append(iid)
                continue

            if action in {"noop", "defer"}:
                _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, action, 1, "", "no side effects", now)
                ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": action, "idempotency_key": ikey})
                grouped["noop_or_deferred"].append(iid)
                continue

            if action in {"keep_summary_only", "mark_reviewed", "archive_local", "retry_summary"}:
                ok_eff, eff_err = check_action_effect(action, "local_write")
                if not ok_eff:
                    _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, "blocked", 0, "", eff_err or "", now)
                    grouped["blocked"].append(iid)
                    continue
                new_state = {
                    "keep_summary_only": "summary_only",
                    "mark_reviewed": "reviewed",
                    "archive_local": "archived_local",
                    "retry_summary": "retry_queued",
                }[action]
                db.execute(
                    "UPDATE reconcile_items SET local_state=?, updated_at=? WHERE run_id=? AND item_id=?",
                    (new_state, now, run_id, iid),
                )
                rb = db.execute(
                    "SELECT local_state FROM reconcile_items WHERE run_id=? AND item_id=?",
                    (run_id, iid),
                ).fetchone()
                verified = bool(rb and rb["local_state"] == new_state)
                status = "verified" if verified else "failed"
                _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, status, 1 if verified else 0, new_state, "local readback verified" if verified else "local readback mismatch", now)
                ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": status, "target_ref": new_state, "idempotency_key": ikey})
                grouped["verified" if verified else "failed"].append(iid)
                continue

            if action in {"create_kanban_card", "link_existing_task"}:
                if prior and prior["status"] == "unconfirmed":
                    ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": "unconfirmed", "target_ref": prior["target_ref"]})
                    grouped["unconfirmed"].append(iid)
                    continue
                board = dec["target_board"]
                tenant = dec["target_tenant"]
                if item["opted_out"]:
                    _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, "blocked", 0, "", "opted-out item blocked", now)
                    ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": "blocked", "detail": "opted-out item blocked"})
                    grouped["blocked"].append(iid)
                    continue
                if allowed_boards is None or board not in allowed_boards:
                    _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, "blocked", 0, "", f"board not allowed: {board}", now)
                    ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": "blocked", "detail": f"board not allowed: {board}"})
                    grouped["blocked"].append(iid)
                    continue
                if expected_tenant is None or tenant != expected_tenant:
                    _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, "blocked", 0, "", f"tenant mismatch: {tenant}", now)
                    ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": "blocked", "detail": f"tenant mismatch: {tenant}"})
                    grouped["blocked"].append(iid)
                    continue
                if kanban_executor is None:
                    _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, "blocked", 0, "", "no kanban_executor configured", now)
                    ledger.append({"item_id": iid, "thread_id": item["thread_id"], "action": action, "status": "blocked", "detail": "no kanban_executor configured"})
                    grouped["blocked"].append(iid)
                    continue
                reservation = db.execute(
                    "INSERT INTO reconcile_executions VALUES (?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(idempotency_key) DO UPDATE SET status='unconfirmed',updated_at=excluded.updated_at "
                    "WHERE reconcile_executions.status='blocked'",
                    (ikey, run_id, dec["decision_id"], iid, owner_id, action, "unconfirmed", 0, "", "dispatch reserved", now),
                )
                db.commit()
                if reservation.rowcount != 1:
                    ledger.append({"item_id": iid, "action": action, "status": "unconfirmed", "detail": "prior dispatch requires exact target readback"})
                    grouped["unconfirmed"].append(iid)
                    continue
                try:
                    res = kanban_executor({
                        "action": action, "item": item, "decision": dec, "idempotency_key": ikey,
                        "board": board, "tenant": tenant, "existing_task_id": dec["existing_task_id"],
                    }) or {}
                except Exception as exc:
                    res = {"error": f"dispatch result unknown: {type(exc).__name__}"}
                task_id = _norm(res.get("task_id"))
                rb = res.get("readback")
                verified = bool(task_id and isinstance(rb, dict) and rb.get("id") == task_id
                                and rb.get("board") == board and rb.get("tenant") == tenant
                                and (action != "link_existing_task" or task_id == dec["existing_task_id"]))
                status = "verified" if verified else "unconfirmed"
                detail = "exact readback verified" if verified else _norm(res.get("error") or "missing or mismatched target readback")
                _upsert_exec(db, ikey, run_id, dec["decision_id"], iid, owner_id, action, status, 1 if verified else 0, task_id, detail, now)
                db.commit()
                ledger.append({
                    "item_id": iid,
                    "thread_id": item["thread_id"],
                    "action": action,
                    "status": status,
                    "target_ref": task_id,
                    "detail": detail,
                    "idempotency_key": ikey,
                })
                grouped[status].append(iid)

        db.execute("UPDATE reconcile_runs SET updated_at=? WHERE run_id=?", (now, run_id))
        db.commit()
        return {
            "ok": True,
            "run_id": run_id,
            "report": {k: len(v) for k, v in grouped.items()},
            "grouped": grouped,
            "ledger": ledger,
        }
    finally:
        db.close()


def _upsert_exec(
    db: sqlite3.Connection,
    ikey: str,
    run_id: str,
    decision_id: str,
    item_id: str,
    owner_id: str,
    action: str,
    status: str,
    verified_readback: int,
    target_ref: str,
    detail: str,
    updated_at: str,
) -> None:
    db.execute(
        """
        INSERT INTO reconcile_executions VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(idempotency_key) DO UPDATE SET
            status=excluded.status,
            verified_readback=excluded.verified_readback,
            target_ref=excluded.target_ref,
            detail=excluded.detail,
            updated_at=excluded.updated_at
        WHERE excluded.status <> 'blocked' OR reconcile_executions.status = 'blocked'
        """,
        (ikey, run_id, decision_id, item_id, owner_id, action, status, verified_readback, target_ref, detail, updated_at),
    )
