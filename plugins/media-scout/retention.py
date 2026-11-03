"""Explicit, bounded cleanup of registered plugin-owned artifacts only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import secrets
import time

MAX_FILES = 100
MAX_BYTES = 50 * 1024 * 1024


def safe_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or len(relative) > 300 or "\\" in relative:
        raise ValueError("unsafe artifact path")
    parts = PurePosixPath(relative)
    if parts.is_absolute() or not parts.parts or parts.parts[0] not in {"cache", "evidence"} or any(p in {".", ".."} for p in parts.parts):
        raise ValueError("only contained cache/evidence artifacts are allowed")
    if root.is_symlink():
        raise ValueError("symlink data root rejected")
    target = root
    for part in parts.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError("symlink artifacts rejected")
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("artifact must be an existing contained regular file")
    return target


def fingerprint(path: Path):
    stat = path.stat()
    if stat.st_size > MAX_BYTES:
        raise ValueError("artifact exceeds bounded cleanup size")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return stat.st_size, digest.hexdigest()


def register_file(db, root, relative, media_id, kind, expires_at):
    if kind not in {"cache", "evidence"} or not relative.startswith(kind + "/"):
        raise ValueError("artifact kind/path mismatch")
    if type(expires_at) is not int or not db.execute("SELECT 1 FROM media WHERE media_id=?", (media_id,)).fetchone():
        raise ValueError("known media and explicit expiry required")
    size, digest = fingerprint(safe_file(root, relative))
    db.execute("INSERT OR REPLACE INTO cache_files(path,sha256,size,expires_at,media_id,kind) VALUES(?,?,?,?,?,?)", (relative, digest, size, expires_at, media_id, kind))
    db.commit()
    return {"registered": relative, "sha256": digest, "size": size}


def _eligible(db, root, row, now):
    relative, digest, size, expires, media = row
    if expires > now or size > MAX_BYTES:
        return False
    state = db.execute("SELECT pinned,claim_state FROM media WHERE media_id=?", (media,)).fetchone()
    if not state or state[0] or state[1] == "running":
        return False
    if db.execute("SELECT 1 FROM reviews WHERE media_id=? AND state NOT IN ('done','archived','cancelled')", (media,)).fetchone():
        return False
    try:
        return fingerprint(safe_file(root, relative)) == (size, digest)
    except (OSError, ValueError):
        return False


def _init(db):
    db.execute("CREATE TABLE IF NOT EXISTS cleanup_plans (id TEXT PRIMARY KEY, created_at INTEGER NOT NULL, candidates TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0)")
    db.commit()


def plan(db, root):
    _init(db)
    now = int(time.time()); selected = []; total = 0
    rows = db.execute("SELECT path,sha256,size,expires_at,media_id FROM cache_files WHERE expires_at<=? AND pinned=0 AND active=0 AND pending_review=0 ORDER BY expires_at,path LIMIT 100", (now,)).fetchall()
    for row in rows:
        if total + row[2] <= MAX_BYTES and _eligible(db, root, row, now):
            selected.append(list(row)); total += row[2]
    plan_id = secrets.token_hex(16)
    db.execute("INSERT INTO cleanup_plans(id,created_at,candidates) VALUES(?,?,?)", (plan_id, now, json.dumps(selected)))
    db.commit()
    return {"plan_id": plan_id, "candidates": [{"path": r[0], "sha256": r[1], "size": r[2], "expires_at": r[3]} for r in selected], "total_bytes": total, "max_files": MAX_FILES, "max_bytes": MAX_BYTES}


def apply(db, root, plan_id, *, enabled=False):
    if enabled is not True:
        return {"error": "cleanup requires separate operator enablement"}
    _init(db)
    db.execute("BEGIN IMMEDIATE")
    deleted = []
    try:
        entry = db.execute("SELECT created_at,candidates,applied FROM cleanup_plans WHERE id=?", (plan_id,)).fetchone()
        now = int(time.time())
        if not entry or entry[2] or now - entry[0] > 3600:
            db.rollback(); return {"error": "fresh unapplied exact plan required"}
        rows = json.loads(entry[1])
        if len(rows) > MAX_FILES or sum(r[2] for r in rows) > MAX_BYTES:
            db.rollback(); return {"error": "plan exceeds cleanup bounds"}
        # Validate the complete plan before any unlink; cooperative plugin writers are fenced.
        for row in rows:
            current = db.execute("SELECT path,sha256,size,expires_at,media_id FROM cache_files WHERE path=? AND pinned=0 AND active=0 AND pending_review=0", (row[0],)).fetchone()
            if current is None or tuple(row) != current or not _eligible(db, root, current, now):
                db.rollback(); return {"error": "plan drift or protected/unsafe artifact; nothing deleted"}
        for row in rows:
            safe_file(root, row[0]).unlink()
            deleted.append(row[0])
            db.execute("DELETE FROM cache_files WHERE path=?", (row[0],))
        db.execute("UPDATE cleanup_plans SET applied=1 WHERE id=?", (plan_id,))
        db.commit()
        return {"deleted": deleted, "summary_preserved": True}
    except (OSError, ValueError, TypeError) as error:
        # File deletion is not transactional. Retain explicit partial-effect evidence.
        db.commit()
        return {"error": type(error).__name__, "deleted": deleted, "partial_effect": bool(deleted)}
    except Exception as error:
        db.rollback()
        return {"error": type(error).__name__, "deleted": deleted, "partial_effect": bool(deleted)}
