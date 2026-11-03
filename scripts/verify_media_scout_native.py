#!/usr/bin/env python3
"""Offline real-SDK qualification; all sources and evidence are labeled synthetic.

Run with a PM-prepared Hermes Python environment, not the ordinary unit-test venv.
No dispatcher, notifier, Discord client or inference provider is started.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.sdk.resolve()))
    plugin = Path(__file__).resolve().parents[1] / "plugins/media-scout"
    with tempfile.TemporaryDirectory(prefix="scout-sdk-", dir=os.environ.get("TMPDIR")) as directory:
        home = Path(directory)
        os.environ["HERMES_HOME"] = str(home)
        os.environ["HOME"] = str(home / "user")
        (home / "user").mkdir()
        for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN"):
            os.environ.pop(key, None)
        shutil.copytree(plugin, home / "plugins/media-scout", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        settings = {"owner_id": "111", "guild_id": "222", "parent_channel_id": "333", "auto_review": True, "review_policy_reference": "SYNTHETIC isolated SDK fixture only", "review_profile": "default", "review_board": "scout-fixture", "allow_cleanup": False}
        (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["media-scout"], "entries": {"media-scout": {"settings": settings}}}}), encoding="utf-8")
        from hermes_cli.plugins import PluginManager
        from gateway.config import Platform
        from gateway.session import SessionSource
        from gateway.session_context import set_session_vars, clear_session_vars
        from tools.registry import registry
        import tools.terminal_tool  # native registration, no custom command runner
        import shlex
        launcher = shutil.which("hermes")
        assert launcher
        setup = json.loads(registry.dispatch("terminal", {"command": f"env HERMES_HOME={shlex.quote(str(home))} {shlex.quote(launcher)} kanban boards create scout-fixture", "timeout": 30}))
        assert setup.get("exit_code") == 0, setup
        manager = PluginManager()
        manager.discover_and_load()
        loaded = [p for p in manager.list_plugins() if p.get("name") == "media-scout"]
        assert loaded and loaded[0].get("enabled"), loaded
        source = SessionSource(platform=Platform.DISCORD, chat_id="444", chat_type="group", thread_id="444", user_id="111", scope_id="222", parent_chat_id="333", message_id="555")
        snapshot = source.to_dict()
        session_key = "agent:fixture:discord:group:444"
        tokens = set_session_vars(platform="discord", source="discord", chat_id="444", chat_type="group", thread_id="444", user_id="111", scope_id="222", session_key=session_key, session_id="synthetic-scout-sdk", message_id="555", parent_chat_id="333")
        try:
            def call(**payload):
                raw = registry.dispatch("media_scout", payload, scope=manager.scope_key)
                result = json.loads(raw) if isinstance(raw, str) else raw
                assert isinstance(result, dict) and not result.get("error"), result
                return result
            manager.invoke_hook("post_gateway_admission", platform="discord", source=snapshot, session_key=session_key, message_id="555", text="SYNTHETIC SDK source, not real media: https://instagram.com/p/TestMedia1/")
            status = call(action="status")
            assert status["items"] == 1, status
            media = status["recent"][0]["media_id"]
            claim = call(action="claim", media_id=media)
            replay = registry.dispatch("media_scout", {"action": "claim", "media_id": media}, scope=manager.scope_key)
            assert "already claimed" in replay, replay
            (Path(claim["cache_dir"]) / "fixture.bin").write_bytes(b"SYNTHETIC cache only")
            call(action="register_cache", media_id=media, claim_token=claim["claim_token"], path=f"cache/{media}/fixture.bin")
            evidence = {"audio": 0, "visual": 2, "pictures": 0, "times": ["00:01", "00:02"], "visual_mode": "sampled", "observations": "SYNTHETIC SDK fixture observations; no real media was retrieved.", "limitations": "Synthetic sampled frames only; no real extraction."}
            call(action="save", media_id=media, claim_token=claim["claim_token"], summary="SYNTHETIC fixture retained knowledge, not a creator claim.", evidence=evidence, coverage="partial")
            item = call(action="get", media_id=media)
            assert hashlib.sha256(Path(item["evidence_path"]).read_bytes()).hexdigest() == item["evidence_hash"]
            manager.invoke_hook("post_gateway_admission", platform="discord", source=snapshot, session_key=session_key, message_id="555", text="https://instagram.com/p/TestMedia1/?utm_source=replay")
            assert call(action="status")["items"] == 1
            review = call(action="review", media_id=media)
            assert review["source_verified"] is True and review["task_id"]
            repeated = call(action="review", media_id=media)
            assert repeated["task_id"] == review["task_id"], (review, repeated)
            native = call(action="review_status", media_id=media)
            assert native.get("status") in {"ready", "todo", "running"}, native
            assert call(action="get", media_id=media)["review_task_id"] == review["task_id"]
            # Protect current packets while review is pending; never deliver fixture messages.
            plan = call(action="cleanup_plan")
            assert plan["candidates"] == [], plan
            complete = json.loads(registry.dispatch("terminal", {"command": f"env HERMES_HOME={shlex.quote(str(home))} {shlex.quote(launcher)} kanban --board scout-fixture complete {shlex.quote(review['task_id'])} --summary 'SYNTHETIC operator completion, not an actual model review.' --result 'SYNTHETIC fixture only'", "timeout": 30}, scope=manager.scope_key))
            assert complete.get("exit_code") == 0, complete
            finished = call(action="review_status", media_id=media)
            assert finished["status"] == "done", finished
            with sqlite3.connect(home / "plugin-data/media-scout/data.db") as stored:
                note = json.loads(stored.execute("SELECT result FROM reviews WHERE media_id=?", (media,)).fetchone()[0])
                assert "SYNTHETIC" in note["learning_note"] and "body" not in note
            print(json.dumps({"ok": True, "synthetic": True, "native_registration": True, "capture_replay": True, "exclusive_claim": True, "actual_saved_hash_verified": True, "native_review_replay_same_task": True, "native_review_status": finished.get("status"), "synthetic_completion_note_retained": True, "pending_review_retention_protected": True, "live_discord_tested": False}))
        finally:
            clear_session_vars(tokens)


if __name__ == "__main__":
    main()
