#!/usr/bin/env python3
"""Real SDK/queue with synthetic sources, evidence and a fake naming adapter.
No live Discord client, dispatcher, notifier, extraction or inference is started.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import sys
import tempfile
from unittest.mock import patch

CASES = {
    "instagram": "https://instagram.com/p/AbC123/",
    "youtube": "https://youtu.be/AbCdEf12345?t=7",
    "threads": "https://threads.com/@author/post/AbC123",
    "tiktok": "https://tiktok.com/@author/video/12345",
    "snapchat": "https://snapchat.com/spotlight/AbC123",
    "x": "https://x.com/author/status/12345",
    "reddit": "https://redd.it/abc123",
    "facebook": "https://facebook.com/reel/12345",
    "vimeo": "https://vimeo.com/12345",
    "bluesky": "https://bsky.app/profile/author.test/post/abc123",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--platforms", default="instagram")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    selected = args.platforms.split(",")
    assert len(selected) == len(set(selected)) and set(selected) <= set(CASES)
    sys.path.insert(0, str(args.sdk.resolve()))
    plugin = Path(__file__).resolve().parents[1] / "plugins/media-scout"
    with tempfile.TemporaryDirectory(prefix="scout-sdk-", dir=os.environ.get("TMPDIR")) as directory:
        home = Path(directory)
        os.environ.update(HERMES_HOME=str(home), HOME=str(home / "user"))
        (home / "user").mkdir()
        for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN"):
            os.environ.pop(key, None)
        shutil.copytree(plugin, home / "plugins/media-scout", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        settings = {"owner_id": "111", "guild_id": "222", "parent_channel_id": "333", "auto_review": True, "review_policy_reference": "SYNTHETIC SDK fixture only", "review_profile": "default", "review_board": "scout-fixture", "rename_threads": True, "allow_cleanup": False}
        # A test-only permission fixture, not a real user's consent record.
        (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["media-scout"], "entries": {"media-scout": {"settings": settings, "granted_capabilities": ["gateway.platform_actions"]}}}}))
        from hermes_cli.plugins import PluginManager
        from hermes_cli.platform_actions import PlatformActions
        from gateway.config import Platform
        from gateway.session import SessionSource
        from gateway.session_context import set_session_vars, clear_session_vars
        from tools.registry import registry
        import tools.terminal_tool
        launcher = shutil.which("hermes")
        assert launcher
        def terminal(command):
            raw = registry.dispatch("terminal", {"command": command, "timeout": 30})
            result = json.loads(raw) if isinstance(raw, str) else raw
            assert result.get("exit_code") == 0, result
            return result
        prefix = f"env HERMES_HOME={shlex.quote(str(home))} {shlex.quote(launcher)} kanban"
        terminal(prefix + " boards create scout-fixture")
        manager = PluginManager(); manager.discover_and_load()
        assert any(p.get("name") == "media-scout" and p.get("enabled") for p in manager.list_plugins())
        def call(**payload):
            raw = registry.dispatch("media_scout", payload, scope=manager.scope_key)
            result = json.loads(raw) if isinstance(raw, str) else raw
            assert isinstance(result, dict) and not result.get("error"), result
            return result
        class SyntheticAdapter:
            platform = Platform.DISCORD
            def __init__(self): self.titles = {}; self.expected_loop: asyncio.AbstractEventLoop | None = None
            async def rename_thread(self, thread, title):
                assert asyncio.get_running_loop() is self.expected_loop, "SDK naming must stay on caller event loop"
                self.titles[thread] = title
                return True
        adapter = SyntheticAdapter(); results = []
        for index, platform in enumerate(selected):
            thread, message = str(400 + index), str(500 + index)
            source = SessionSource(platform=Platform.DISCORD, chat_id=thread, chat_type="group", thread_id=thread, user_id="111", scope_id="222", parent_chat_id="333", message_id=message)
            session_key = "agent:fixture:discord:group:" + thread
            tokens = set_session_vars(platform="discord", source="discord", chat_id=thread, chat_type="group", thread_id=thread, user_id="111", scope_id="222", session_key=session_key, session_id="synthetic-scout-sdk", message_id=message, parent_chat_id="333")
            try:
                payload = dict(platform="discord", source=source.to_dict(), session_key=session_key, message_id=message, text="SYNTHETIC fixture, not real media: " + CASES[platform])
                async def admit():
                    adapter.expected_loop = asyncio.get_running_loop()
                    # Isolated adapter stand-in only. Production plugin never accesses or patches SDK internals.
                    with patch.object(PlatformActions, "_resolve_adapter", return_value=(adapter, None)):
                        await manager.ainvoke_hook("post_gateway_admission", **payload)
                asyncio.run(admit())
                recent = call(action="status")["recent"]
                item = next(call(action="get", media_id=row["media_id"]) for row in recent if call(action="get", media_id=row["media_id"])["source_platform"] == platform)
                media = item["media_id"]
                assert item["source_platform"] == platform
                assert adapter.titles[thread] == item["suggested_thread_title"]
                assert item["thread_names"][0]["state"] == "acknowledged"
                claim = call(action="claim", media_id=media)
                duplicate = registry.dispatch("media_scout", {"action": "claim", "media_id": media}, scope=manager.scope_key)
                assert "already claimed" in duplicate
                (Path(claim["cache_dir"]) / "fixture.bin").write_bytes(b"SYNTHETIC cache only")
                call(action="register_cache", media_id=media, claim_token=claim["claim_token"], path=f"cache/{media}/fixture.bin")
                text_only = platform in {"threads", "x", "reddit", "bluesky"}
                evidence = {"kind": "text" if text_only else "video", "audio": 0, "visual": 0 if text_only else 2, "pictures": 0, "times": [] if text_only else ["00:01", "00:02"], "visual_mode": "none" if text_only else "sampled", "observations": "SYNTHETIC SDK observations; no actual source content retrieved.", "limitations": "Synthetic fixture only; no real extraction.", "text_segments": 1 if text_only else 0, "has_media": not text_only}
                if text_only: evidence["text_content"] = ["SYNTHETIC captured post text; no actual creator content was retrieved."]
                call(action="save", media_id=media, claim_token=claim["claim_token"], summary="SYNTHETIC retained knowledge, not actual creator claims.", evidence=evidence, coverage="complete" if text_only else "partial")
                item = call(action="get", media_id=media)
                assert hashlib.sha256(Path(item["evidence_path"]).read_bytes()).hexdigest() == item["evidence_hash"]
                asyncio.run(admit())
                assert call(action="status")["items"] == index + 1
                review = call(action="review", media_id=media)
                assert review["source_verified"] and review["task_id"]
                assert call(action="review", media_id=media)["task_id"] == review["task_id"]
                assert call(action="review_status", media_id=media)["status"] == "ready"
                assert call(action="cleanup_plan")["candidates"] == []
                terminal(prefix + " --board scout-fixture complete " + shlex.quote(review["task_id"]) + " --summary 'SYNTHETIC operator completion, not actual model review.' --result 'SYNTHETIC only'")
                assert call(action="review_status", media_id=media)["status"] == "done"
                with closing(sqlite3.connect(home / "plugin-data/media-scout/data.db")) as db:
                    note = json.loads(db.execute("SELECT result FROM reviews WHERE media_id=?", (media,)).fetchone()[0])
                    assert "SYNTHETIC" in note["learning_note"] and "body" not in note
                results.append({"platform": platform, "capture_replay": True, "naming_sdk_ack": True, "same_event_loop": True, "evidence_hash_verified": True, "same_native_task_on_retry": True, "native_status": "done", "completion_note_retained": True})
                if args.report: args.report.write_text(json.dumps({"synthetic": True, "results": results}, indent=2))
            finally:
                clear_session_vars(tokens)
        assert len(results) == len(selected)
        print(json.dumps({"ok": True, "synthetic": True, "platform_count": len(results), "platforms": results, "live_discord_tested": False, "live_source_extraction_tested": False}))


if __name__ == "__main__": main()
