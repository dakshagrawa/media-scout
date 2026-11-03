"""Small, profile-local bookkeeping for social-media review workflows."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .sources import parse_source_url, extract_one_source

NAME = "media-scout"
MAX_TEXT = 16_000
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "igsh", "igshid", "fbclid"}


def parse_instagram_url(value: str):
    """Return case-preserving shortcode and original submitted URL, or None."""
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    try:
        p = urlsplit(value)
        if p.scheme.lower() != "https" or p.username is not None or p.password is not None or p.port is not None:
            return None
        if p.hostname is None or p.hostname.lower() not in {"instagram.com", "www.instagram.com"}:
            return None
        if "%" in p.path or "\\" in p.path or "//" in p.path:
            return None
        m = re.fullmatch(r"/(?:reel|p|tv)/([A-Za-z0-9_-]{5,20})/?", p.path)
        if not m:
            return None
        return m.group(1), value
    except (ValueError, UnicodeError):
        return None


def canonical_identity(value: str):
    parsed = parse_source_url(value)
    return parsed.identity_key if parsed else None


def extract_one_url(text: str):
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        return None
    candidates = []
    for match in URL_RE.finditer(text):
        raw = match.group(0).rstrip(".,;:!?)]}")
        parsed = parse_instagram_url(raw)
        if parsed:
            candidates.append(parsed)
        elif "instagram.com" in raw.lower():
            return None
    distinct = {p[0] for p in candidates}
    if len(distinct) != 1 or not candidates:
        return None
    return candidates[0]


def initialize(db: sqlite3.Connection):
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS media (
      media_id TEXT PRIMARY KEY, shortcode TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
      summary TEXT NOT NULL DEFAULT '', evidence_hash TEXT NOT NULL DEFAULT '',
      evidence_path TEXT NOT NULL DEFAULT '', coverage TEXT NOT NULL DEFAULT '',
      claim_token TEXT NOT NULL DEFAULT '', claim_owner TEXT NOT NULL DEFAULT '',
      claim_state TEXT NOT NULL DEFAULT '', pinned INTEGER NOT NULL DEFAULT 0,
      review_task_id TEXT NOT NULL DEFAULT '', review_key TEXT NOT NULL DEFAULT '',
      packet_version INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS receipts (
      receipt_id TEXT PRIMARY KEY, message_id TEXT NOT NULL UNIQUE, media_id TEXT NOT NULL REFERENCES media(media_id),
      source_url TEXT NOT NULL, platform TEXT NOT NULL, owner_id TEXT NOT NULL,
      guild_id TEXT NOT NULL, parent_channel_id TEXT NOT NULL, chat_id TEXT NOT NULL,
      thread_id TEXT NOT NULL, created_at INTEGER NOT NULL,
      session_key TEXT NOT NULL DEFAULT '', source_text TEXT NOT NULL DEFAULT '', chat_type TEXT NOT NULL DEFAULT 'group'
    );
    CREATE TABLE IF NOT EXISTS thread_titles (thread_id TEXT PRIMARY KEY, media_id TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews (media_id TEXT NOT NULL, packet_version INTEGER NOT NULL,
      task_id TEXT NOT NULL DEFAULT '', origin TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
      result TEXT NOT NULL DEFAULT '', expected_body_hash TEXT NOT NULL DEFAULT '',
      assignee TEXT NOT NULL DEFAULT '', board TEXT NOT NULL DEFAULT '', PRIMARY KEY(media_id,packet_version));
    CREATE TABLE IF NOT EXISTS cache_files (
      path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER NOT NULL, expires_at INTEGER NOT NULL,
      media_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'cache',
      pinned INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 0, pending_review INTEGER NOT NULL DEFAULT 0
    );
    """)
    db.commit()


def _identity_shortcode(shortcode):
    return hashlib.sha256(shortcode.encode("ascii")).hexdigest()[:24]


def capture_receipt(db, message_id, source, url, source_text=""):
    parsed = parse_source_url(url)
    if not parsed or not isinstance(message_id, str) or not message_id or len(message_id) > 256:
        return None
    shortcode, source_url = parsed.identity_key, parsed.original_url
    media_id = _identity_shortcode(shortcode)
    now = int(time.time())
    db.execute("BEGIN IMMEDIATE")
    try:
        bound = db.execute("SELECT value FROM catalog_meta WHERE key='owner_id'").fetchone()
        if bound and bound[0] != source.get("user_id"):
            db.rollback()
            return None
        db.execute("INSERT OR IGNORE INTO catalog_meta VALUES('owner_id',?)", (source.get("user_id", ""),))
        existing = db.execute("SELECT receipt_id,media_id FROM receipts WHERE message_id=?", (message_id,)).fetchone()
        if existing:
            db.commit()
            return {"receipt_id": existing[0], "media_id": existing[1]}
        if source.get("thread_id") and db.execute("SELECT 1 FROM receipts WHERE thread_id=? AND media_id<>?", (source["thread_id"], media_id)).fetchone():
            db.rollback()
            return None  # one isolated item per thread; never retarget a previous item's thread
        db.execute("INSERT OR IGNORE INTO media(media_id,shortcode,created_at) VALUES(?,?,?)", (media_id, shortcode, now))
        receipt_id = secrets.token_hex(16)
        db.execute("""INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            receipt_id, message_id, media_id, source_url, source.get("platform", ""),
            source.get("user_id", ""), source.get("scope_id", source.get("guild_id", "")), source.get("parent_chat_id", source.get("parent_channel_id", "")),
            source.get("chat_id", ""), source.get("thread_id", ""), now, source.get("session_key", ""), source_text[:MAX_TEXT], source.get("chat_type", "group")))
        db.commit()
        return {"receipt_id": receipt_id, "media_id": media_id}
    except Exception:
        db.rollback()
        raise


def get_item(db, media_id) -> dict | None:
    row = db.execute("SELECT media_id,shortcode,summary,evidence_hash,evidence_path,coverage,claim_token,claim_owner,claim_state,pinned,review_task_id,packet_version FROM media WHERE media_id=?", (media_id,)).fetchone()
    if not row:
        return None
    names = ("media_id", "shortcode", "summary", "evidence_hash", "evidence_path", "coverage", "claim_token", "claim_owner", "claim_state", "pinned", "review_task_id", "packet_version")
    item: dict = dict(zip(names, row))
    original = db.execute("SELECT source_url FROM receipts WHERE media_id=? ORDER BY created_at,rowid LIMIT 1", (media_id,)).fetchone()
    parsed = parse_source_url(original[0]) if original else None
    if parsed:
        item.update(source_platform=parsed.platform, source_post_id=parsed.post_id, canonical_url=parsed.canonical_url, identity_quality=parsed.identity_quality, suggested_thread_title=parsed.title)
    item["thread_names"] = [dict(zip(("thread_id", "title", "state", "detail"), r)) for r in db.execute("SELECT thread_id,title,state,detail FROM thread_titles WHERE media_id=?", (media_id,))]
    return item


def claim(db, media_id, owner):
    if not owner:
        return {"error": "owner identity unavailable"}
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT claim_token,claim_state FROM media WHERE media_id=?", (media_id,)).fetchone()
        if not row:
            db.rollback()
            return {"error": "media not found"}
        if db.execute("SELECT 1 FROM reviews WHERE media_id=? AND state NOT IN ('done','archived','cancelled')", (media_id,)).fetchone():
            db.commit()
            return {"error": "review still pending; inspect native review status first"}
        if row[0] and row[1] == "running":
            db.commit()
            return {"error": "already claimed"}
        token = secrets.token_urlsafe(24)
        db.execute("UPDATE media SET claim_token=?,claim_owner=?,claim_state='running' WHERE media_id=?", (token, owner, media_id))
        db.commit()
        return {"claim_token": token}
    except Exception:
        db.rollback()
        raise



def save_evidence(db, media_id, token, summary, evidence, coverage):
    """Commit bounded, explicitly self-reported coverage under the extraction claim."""
    if not isinstance(media_id, str) or not re.fullmatch(r"[a-f0-9]{24}", media_id):
        return {"error": "invalid media identity"}
    if not isinstance(token, str) or not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
        return {"error": "current claim and bounded nonempty summary required"}
    if coverage not in {"complete", "partial", "blocked"} or not isinstance(evidence, dict):
        return {"error": "explicit structured coverage required"}
    if any(type(evidence.get(k)) is not int or not 0 <= evidence[k] <= 500 for k in ("audio", "visual", "pictures")):
        return {"error": "bounded audio, visual and pictures counts required"}
    times = evidence.get("times")
    if not isinstance(times, list) or len(times) > 500 or any(not isinstance(t, str) or len(t) > 32 for t in times):
        return {"error": "bounded observed times required"}
    if not isinstance(evidence.get("observations"), str) or len(evidence["observations"].strip()) < 20:
        return {"error": "substantive actual observations or source-access explanation required"}
    if coverage in {"partial", "blocked"} and not str(evidence.get("limitations", "")).strip():
        return {"error": "partial/blocked evidence requires explicit limitations"}
    kind = evidence.get("kind", "video")
    if kind not in {"video", "image", "carousel", "text", "mixed"}:
        return {"error": "unsupported evidence kind"}
    if coverage == "complete":
        if kind == "text":
            segments = evidence.get("text_content")
            if (not isinstance(segments, list) or not 1 <= len(segments) <= 100
                    or not all(isinstance(part, str) and part.strip() and len(part) <= MAX_TEXT for part in segments)
                    or type(evidence.get("text_segments")) is not int
                    or evidence["text_segments"] != len(segments)
                    or evidence.get("has_media") is not False
                    or any(evidence[k] for k in ("audio", "visual", "pictures"))):
                return {"error": "complete text requires bounded captured text_content segments, a matching text_segments count, and explicit absence of uninspected media"}
        elif evidence.get("visual_mode") != "full" or not (evidence["visual"] or evidence["pictures"]) or (not evidence["audio"] and not evidence.get("audio_unavailable_reason")):
            return {"error": "complete requires full visual coverage and audio or an explicit no-audio basis"}
    try:
        detail = json.dumps({**evidence, "coverage": coverage}, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError):
        return {"error": "evidence must be finite JSON data"}
    if len(detail.encode("utf-8")) > 16000:
        return {"error": "evidence exceeds bounded packet size"}
    body = f"# Media evidence\n\n{summary.strip()}\n\n## Self-reported coverage and observations\n\n{detail}\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    from plugins.plugin_storage import plugin_data_dir
    base = plugin_data_dir(NAME)
    root = base / "evidence"
    if base.is_symlink() or base.parent.is_symlink() or root.is_symlink():
        return {"error": "unsafe evidence directory"}
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{media_id}-{digest[:16]}.md"
    if target.is_symlink() or not target.resolve().is_relative_to(base.resolve()):
        return {"error": "unsafe evidence path"}
    tmp = root / f".{media_id}.{secrets.token_hex(8)}.tmp"
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute("SELECT claim_token,claim_state,evidence_hash FROM media WHERE media_id=?", (media_id,)).fetchone()
        if not row or not secrets.compare_digest(row[0], token):
            db.rollback()
            return {"error": "current extraction claim required"}
        if row[1] == "saved" and row[2] == digest:
            db.commit()
            return {"saved": True, "evidence_hash": digest, "reused": True}
        if row[1] != "running":
            db.rollback()
            return {"error": "current extraction claim required"}
        with tmp.open("x", encoding="utf-8") as f:
            f.write(body)
        tmp.replace(target)
        db.execute("UPDATE media SET summary=?,evidence_hash=?,evidence_path=?,coverage=?,claim_state='saved',packet_version=packet_version+1 WHERE media_id=?", (summary.strip(), digest, str(target), coverage, media_id))
        relative = target.relative_to(base).as_posix()
        db.execute("INSERT OR REPLACE INTO cache_files(path,sha256,size,expires_at,media_id,kind) VALUES(?,?,?,?,?,?)", (relative, digest, len(body.encode("utf-8")), int(time.time()) + 90 * 86400, media_id, "evidence"))
        db.commit()
        return {"saved": True, "evidence_hash": digest, "evidence_path": str(target)}
    except Exception:
        db.rollback()
        raise
    finally:
        tmp.unlink(missing_ok=True)


def _config(ctx, key, default=None):
    try:
        return ctx.get_config(key, default)
    except Exception:
        return default


def _db():
    from plugins.plugin_storage import plugin_db
    _data_root()  # reject unsafe plugin-owned roots before opening a writable database
    db = plugin_db(NAME)
    initialize(db)
    return db


def _capture(ctx, **kwargs):
    db = None
    try:
        source = kwargs.get("source")
        if not isinstance(source, dict) or kwargs.get("platform") != "discord" or source.get("platform") != "discord":
            return None
        expected = {k: _config(ctx, k, "") for k in ("owner_id", "guild_id", "parent_channel_id")}
        if not all(isinstance(v, str) and 0 < len(v) <= 128 for v in expected.values()):
            return None
        if (source.get("user_id") != expected["owner_id"] or source.get("scope_id", source.get("guild_id")) != expected["guild_id"] or source.get("parent_chat_id") != expected["parent_channel_id"]):
            return None
        message_id, session_key = kwargs.get("message_id"), kwargs.get("session_key")
        if any(not isinstance(v, str) or not v or len(v) > 512 for v in (message_id, session_key, source.get("chat_id"), source.get("thread_id"))):
            return None
        if source.get("message_id") and source["message_id"] != message_id:
            return None
        text = kwargs.get("text")
        if not isinstance(text, str):
            return None
        found = extract_one_source(text)
        if not found:
            return None
        db = _db()
        captured = capture_receipt(db, message_id, {**source, "session_key": session_key}, found.original_url, text)
        if captured and captured["media_id"] == _identity_shortcode(found.identity_key):
            return {"media_id": captured["media_id"], "source": source, "title": found.title}
    except Exception:
        # No content is logged. A failed capture cannot blackhole native ingress.
        return None
    finally:
        if db is not None:
            db.close()
    return None


async def _admission(ctx, **kwargs):
    captured = _capture(ctx, **kwargs)
    if captured:
        from .naming import rename_captured_thread
        try:
            await rename_captured_thread(ctx, captured["source"], captured["title"], captured["media_id"], _db)
        except Exception:
            pass  # naming is optional; never discard an accepted receipt or block its review
    return None


def _data_root():
    from plugins.plugin_storage import plugin_data_dir
    root = plugin_data_dir(NAME)
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("symlink plugin data root rejected")
    return root


def _review(ctx, db, media_id, *, status_only=False, context=None):
    from .bridge import NativeBridge
    from .retention import safe_file, fingerprint
    item = get_item(db, media_id)
    if not item or not item["evidence_hash"] or item["claim_state"] == "running":
        return {"error": "saved evidence and no active extraction required"}
    owner = _config(ctx, "owner_id", "")
    def authorized():
        current = get_item(db, media_id)
        return (_config(ctx, "auto_review", False) is True and bool(_config(ctx, "review_policy_reference", "")) and current is not None and current["evidence_hash"] == item["evidence_hash"] and current["claim_state"] != "running")
    dispatcher = type("BoundDispatcher", (), {"dispatch_tool": lambda self, name, args: ctx.dispatch_tool(name, args, **(context or {}))})()
    binding = db.execute("SELECT task_id,expected_body_hash,assignee,board FROM reviews WHERE media_id=? AND packet_version=?", (media_id, item["packet_version"])).fetchone()
    recipient = binding[2] if binding else _config(ctx, "review_profile", "default")
    board = binding[3] if binding else _config(ctx, "review_board", "media-review")
    bridge = NativeBridge(dispatcher, _data_root().parent.parent, board, recipient)
    if status_only:
        if not binding or not binding[0] or not binding[1]:
            return {"error": "no verified native review task exists"}
        result = bridge.status(binding[0])
        task = result.get("task", {})
        if not result.get("error") and (hashlib.sha256(str(task.get("body", "")).encode("utf-8")).hexdigest() != binding[1] or task.get("assignee") != binding[2]):
            return {"error": "native review task drift; completion not accepted", "task_id": binding[0]}
        if not result.get("error"):
            state = result.get("status", result.get("task", {}).get("status", "unknown"))
            note = task.get("latest_summary") or task.get("result") or ""
            if not isinstance(note, str):
                note = json.dumps(note, ensure_ascii=False)
            retained = {"task_id": binding[0], "status": state, "learning_note": note[:8000], "note_truncated": len(note) > 8000}
            db.execute("UPDATE reviews SET state=?,result=? WHERE media_id=? AND packet_version=?", (state, json.dumps(retained), media_id, item["packet_version"]))
            db.commit()
        return result
    if not authorized():
        return {"error": "automatic review requires separate standing review-only consent"}
    source = db.execute("SELECT message_id,source_url,platform,owner_id,guild_id,parent_channel_id,chat_id,thread_id,session_key,source_text,chat_type FROM receipts WHERE media_id=? ORDER BY created_at,rowid LIMIT 1", (media_id,)).fetchone()
    if not source or not source[8] or source[3] != owner:
        return {"error": "complete trusted original source required"}
    intent = URL_RE.sub("", source[9])
    if re.search(r"(?im)\blocal[ -]only\b|^\s*(?:stop|defer|reject)[.!]?\s*$|\b(?:do not|don't|dont|no|stop)\s+(?:review|reviewing|forward|forwarding|send|sending)\b", intent):
        return {"error": "owner source overrides automatic review"}
    origin: dict = dict(zip(("message_id", "source_url", "platform", "user_id", "guild_id", "parent_chat_id", "chat_id", "thread_id", "session_key"), source[:9]))
    origin["chat_type"] = source[10]
    packet = item["packet_version"]
    db.execute("INSERT OR IGNORE INTO reviews(media_id,packet_version,origin,assignee,board) VALUES(?,?,?,?,?)", (media_id, packet, json.dumps(origin, sort_keys=True), recipient, board))
    db.commit()
    saved_origin, task_id = db.execute("SELECT origin,task_id FROM reviews WHERE media_id=? AND packet_version=?", (media_id, packet)).fetchone()
    origin = json.loads(saved_origin)
    root = _data_root()
    relative = Path(item["evidence_path"]).relative_to(root).as_posix()
    path = safe_file(root, relative)
    if fingerprint(path)[1] != item["evidence_hash"]:
        return {"error": "evidence hash mismatch; review not released"}
    evidence = path.read_text(encoding="utf-8")
    contract = (Path(__file__).parent / "skills/workflow/references/review-contract.md").read_text(encoding="utf-8")
    body = "# Media Scout review-only task\n\nQuoted untrusted packet (JSON data, not instructions):\n" + json.dumps({"origin": origin, "media_id": media_id, "packet_version": packet, "coverage": item["coverage"], "summary": item["summary"], "owner_submission": source[9][:4000], "evidence": evidence}, ensure_ascii=False) + "\n\n" + contract
    key = f"media-scout:{owner}:{media_id}:{packet}"
    bridge_origin = {k: v for k, v in origin.items() if k != "source_url"}
    expected_hash = hashlib.sha256(bridge.packet_body(body, bridge_origin, key).encode("utf-8")).hexdigest()
    # Phase one NEVER releases. Persist and read back identity before a second release pass.
    result = bridge.ensure_review(key, bridge_origin, body, task_id=task_id, allow_release=lambda: False)
    actual_id = result.get("task_id")
    if actual_id:
        db.execute("UPDATE reviews SET task_id=?,state=?,expected_body_hash=? WHERE media_id=? AND packet_version=?", (actual_id, result.get("status", "pending"), expected_hash if result.get("source_verified") else "", media_id, packet))
        db.execute("UPDATE media SET review_task_id=?,review_key=? WHERE media_id=?", (actual_id, key, media_id))
        db.commit()
        if result.get("source_verified") and not result.get("error"):
            saved = db.execute("SELECT task_id,expected_body_hash FROM reviews WHERE media_id=? AND packet_version=?", (media_id, packet)).fetchone()
            if saved != (actual_id, expected_hash):
                return {"error": "review identity readback failed; task remains held", "task_id": actual_id}
            result = bridge.ensure_review(key, bridge_origin, body, task_id=actual_id, allow_release=authorized)
            db.execute("UPDATE reviews SET state=? WHERE media_id=? AND packet_version=?", (result.get("status", "pending"), media_id, packet)); db.commit()
    return result


def _handler(ctx, args, **kwargs):
    if not isinstance(args, dict):
        return json.dumps({"error": "object arguments required"})
    action = args.get("action")
    configured = all(_config(ctx, k, "") for k in ("owner_id", "guild_id", "parent_channel_id"))
    if action == "status" and not _config(ctx, "owner_id", ""):
        return json.dumps({"configured": False, "setup_needed": True})
    from gateway.session_context import get_session_env
    owner = get_session_env("HERMES_SESSION_USER_ID", "")
    if not owner or owner != _config(ctx, "owner_id", ""):
        return json.dumps({"error": "configured owner identity required"})
    if action == "status" and not configured:
        return json.dumps({"configured": False, "setup_needed": True})
    actions = {"status", "get", "claim", "save", "review", "review_status", "cleanup_plan", "cleanup_apply", "release", "register_cache", "pin"}
    if action not in actions:
        return json.dumps({"error": "unsupported action"})
    try:
        db = _db()
    except Exception as error:
        return json.dumps({"error": f"storage unavailable: {type(error).__name__}"})
    try:
        bound = db.execute("SELECT value FROM catalog_meta WHERE key='owner_id'").fetchone()
        if bound and bound[0] != owner:
            return json.dumps({"error": "catalog belongs to another owner; use a new profile"})
        media_id = args.get("media_id", "")
        if action == "status":
            rows = db.execute("SELECT media_id,shortcode,coverage,claim_state,review_task_id FROM media ORDER BY created_at DESC,rowid DESC LIMIT 25").fetchall()
            return json.dumps({"configured": True, "items": db.execute("SELECT COUNT(*) FROM media").fetchone()[0], "recent": [dict(zip(("media_id", "shortcode", "coverage", "claim_state", "review_task_id"), r)) for r in rows]})
        if action == "get":
            item = get_item(db, media_id)
            if item:
                names = ("receipt_id", "message_id", "source_url", "platform", "owner_id", "guild_id", "parent_channel_id", "chat_id", "thread_id")
                item["receipts"] = [dict(zip(names, row)) for row in db.execute("SELECT receipt_id,message_id,source_url,platform,owner_id,guild_id,parent_channel_id,chat_id,thread_id FROM receipts WHERE media_id=? ORDER BY created_at,rowid", (media_id,))]
            return json.dumps(item or {"error": "media not found"})
        if action == "claim":
            result = claim(db, media_id, owner)
            if "claim_token" in result:
                cache = _data_root() / "cache" / media_id
                if cache.is_symlink() or cache.parent.is_symlink():
                    raise ValueError("unsafe cache directory")
                cache.mkdir(parents=True, exist_ok=True)
                result.update(media_id=media_id, cache_dir=str(cache))
            return json.dumps(result)
        if action == "save":
            evidence = args.get("evidence")
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            return json.dumps(save_evidence(db, media_id, args.get("claim_token", ""), args.get("summary", ""), evidence, args.get("coverage", "")))
        if action in {"review", "review_status"}:
            return json.dumps(_review(ctx, db, media_id, status_only=action == "review_status", context=kwargs))
        if action == "release":
            return json.dumps({"error": "use the owner slash command /media-scout release MEDIA_ID --writer-stopped after stopping the old writer"})
        if action == "pin":
            if type(args.get("pinned")) is not bool or not get_item(db, media_id):
                return json.dumps({"error": "known media and explicit boolean pinned required"})
            db.execute("UPDATE media SET pinned=? WHERE media_id=?", (int(args["pinned"]), media_id)); db.commit()
            return json.dumps({"media_id": media_id, "pinned": args["pinned"]})
        from . import retention
        root = _data_root()
        if action == "register_cache":
            relative = args.get("path", "")
            if not isinstance(relative, str) or not relative.startswith(f"cache/{media_id}/"):
                return json.dumps({"error": "only the item's actual contained cache files may be registered"})
            item = get_item(db, media_id)
            if not item or item["claim_state"] != "running" or not secrets.compare_digest(item["claim_token"], args.get("claim_token", "")):
                return json.dumps({"error": "current extraction claim required"})
            return json.dumps(retention.register_file(db, root, relative, media_id, "cache", int(time.time()) + 7 * 86400))
        if action == "cleanup_plan":
            return json.dumps(retention.plan(db, root))
        if action == "cleanup_apply":
            return json.dumps(retention.apply(db, root, args.get("plan_id", ""), enabled=_config(ctx, "allow_cleanup", False) is True))
    except Exception as error:
        return json.dumps({"error": f"operation failed: {type(error).__name__}; inspect item/native state before retry"})
    finally:
        db.close()


def _command(ctx, raw_args, source=None, **kwargs):
    # Only a real native owner command can attest that an old writer was stopped.
    snapshot = source.to_dict() if source is not None and hasattr(source, "to_dict") else source
    if not isinstance(snapshot, dict) or snapshot.get("platform") != "discord" or snapshot.get("user_id") != _config(ctx, "owner_id", "") or snapshot.get("scope_id", snapshot.get("guild_id")) != _config(ctx, "guild_id", "") or snapshot.get("parent_chat_id") != _config(ctx, "parent_channel_id", ""):
        return json.dumps({"error": "owner command in configured intake thread required"})
    parts = raw_args.split() if isinstance(raw_args, str) else []
    if len(parts) != 3 or parts[0] != "release" or parts[2] != "--writer-stopped" or not re.fullmatch(r"[a-f0-9]{24}", parts[1]):
        return json.dumps({"error": "usage: /media-scout release MEDIA_ID --writer-stopped"})
    try:
        db = _db()
    except Exception as error:
        return json.dumps({"error": f"storage unavailable: {type(error).__name__}"})
    try:
        bound = db.execute("SELECT value FROM catalog_meta WHERE key='owner_id'").fetchone()
        if not bound or bound[0] != snapshot["user_id"]:
            return json.dumps({"error": "catalog belongs to another owner"})
        db.execute("BEGIN IMMEDIATE")
        item = get_item(db, parts[1])
        if not item or item["claim_state"] != "running":
            return json.dumps({"error": "no interrupted active claim exists"})
        db.execute("UPDATE media SET claim_token='',claim_owner='',claim_state='released' WHERE media_id=? AND claim_token=? AND claim_state='running'", (parts[1], item["claim_token"])); db.commit()
        return json.dumps({"released": parts[1], "basis": "explicit owner stopped-writer attestation"})
    finally:
        db.close()


def register(ctx):
    ctx.register_skill("workflow", Path(__file__).parent / "skills/workflow/SKILL.md")
    async def on_admitted(**kwargs):
        return await _admission(ctx, **kwargs)
    ctx.register_hook("post_gateway_admission", on_admitted)
    ctx.register_command("media-scout", lambda raw_args, source=None, **kw: _command(ctx, raw_args, source, **kw), description="Recover an interrupted extraction only after stopping its old writer.", args_hint="release <media_id> --writer-stopped")
    schema = {"name": "media_scout", "description": "Capture-backed media evidence, exclusive claims, native review handoff and bounded owned retention. Load skill_view('media-scout:workflow') for supported social-media submissions.", "parameters": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": ["status", "get", "claim", "save", "review", "review_status", "cleanup_plan", "cleanup_apply", "release", "register_cache", "pin"]},
            "media_id": {"type": "string", "maxLength": 64}, "claim_token": {"type": "string", "maxLength": 128},
            "summary": {"type": "string", "maxLength": 4000}, "coverage": {"type": "string", "enum": ["complete", "partial", "blocked"]},
            "evidence": {"type": "object", "description": "Actual observations: kind video/image/carousel/text/mixed; audio/visual/pictures counts, times and observations. Text-only completeness requires nonempty text_content segments, matching text_segments and has_media=false. Record visual_mode, limitations and audio_unavailable_reason where applicable."},
            "plan_id": {"type": "string", "maxLength": 64}, "path": {"type": "string", "maxLength": 300}, "pinned": {"type": "boolean"}
        }, "required": ["action"]}}
    ctx.register_tool(name="media_scout", toolset="media_scout", schema=schema, handler=lambda args, **kw: _handler(ctx, args, **kw))
