"""Opt-in thread names through the public, capability-gated SDK facade."""
from __future__ import annotations

import asyncio
import re


async def rename_captured_thread(ctx, source, title, media_id, db_factory):
    """Naming failure never invalidates a captured source or blocks its review."""
    if ctx.get_config("rename_threads", False) is not True:
        return
    if not isinstance(title, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", title):
        return
    if (not isinstance(source, dict) or source.get("platform") != "discord"
            or source.get("user_id") != ctx.get_config("owner_id", "")
            or source.get("scope_id", source.get("guild_id")) != ctx.get_config("guild_id", "")
            or source.get("parent_chat_id") != ctx.get_config("parent_channel_id", "")):
        return
    thread, chat = source.get("thread_id"), source.get("chat_id")
    if not isinstance(thread, str) or not thread or not isinstance(chat, str) or not chat:
        return
    db = db_factory()
    try:
        receipt = db.execute("SELECT 1 FROM receipts WHERE thread_id=? AND media_id=? AND owner_id=? AND guild_id=? AND parent_channel_id=? AND chat_id=?", (thread, media_id, source["user_id"], ctx.get_config("guild_id", ""), source["parent_chat_id"], chat)).fetchone()
        if not receipt:
            return
        previous = db.execute("SELECT media_id,title,state FROM thread_titles WHERE thread_id=?", (thread,)).fetchone()
        if previous == (media_id, title, "acknowledged"):
            return
        if previous and previous[0] != media_id:
            return  # never retitle another item's existing thread
        db.execute("INSERT OR REPLACE INTO thread_titles VALUES(?,?,?,'requested','')", (thread, media_id, title))
        db.commit()
    finally:
        db.close()
    try:
        result = await asyncio.wait_for(ctx.platform_actions.set_thread_title("discord", chat, thread, title), timeout=8)
        if not isinstance(result, dict):
            result = {"ok": False, "error": "invalid_sdk_response"}
    except asyncio.TimeoutError:
        result = {"ok": False, "error": "naming_timeout"}
    except Exception:
        result = {"ok": False, "error": "naming_failed"}
    state = "acknowledged" if result.get("ok") is True else "failed"
    # This is an SDK acknowledgement, not independent proof of the current remote title.
    detail = "" if state == "acknowledged" else str(result.get("error", "naming_failed"))[:128]
    db = db_factory()
    try:
        db.execute("UPDATE thread_titles SET state=?,detail=? WHERE thread_id=? AND media_id=? AND title=?", (state, detail, thread, media_id, title))
        db.commit()
    finally:
        db.close()
