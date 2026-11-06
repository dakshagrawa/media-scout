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


def dependency_cache_path(value: str) -> Path:
    """Validate an explicitly supplied private cache before native imports."""
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("dependency cache path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"dependency cache must exist: {exc}") from exc
    if not resolved.is_dir():
        raise argparse.ArgumentTypeError("dependency cache must be an existing directory")
    return resolved


def dependency_state_path(value: str, sdk: Path) -> Path:
    """Validate an explicit private copy of the SDK's committed dependency state."""
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("dependency state path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"dependency state must exist: {exc}") from exc
    if not resolved.is_dir():
        raise argparse.ArgumentTypeError("dependency state must be an existing directory")
    expected_key = hashlib.sha256(str(sdk.resolve()).encode()).hexdigest()[:16]
    if resolved.name != expected_key:
        raise argparse.ArgumentTypeError(f"dependency state directory must be named for SDK install key {expected_key}")
    facts_path = resolved / "facts.json"
    try:
        facts = json.loads(facts_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"dependency state facts.json must be readable JSON: {exc}") from exc
    packages = facts.get("packages") if isinstance(facts, dict) else None
    venv = packages.get("venv") if isinstance(packages, dict) else None
    environment = venv.get("environment") if isinstance(venv, dict) else None
    if not isinstance(environment, str) or not Path(environment).is_absolute():
        raise argparse.ArgumentTypeError("dependency state facts.json must contain an absolute packages.venv.environment")
    environment_path = Path(environment)
    if not environment_path.is_dir():
        raise argparse.ArgumentTypeError("committed dependency environment must exist")
    if not any(site.is_dir() for site in environment_path.glob("lib/python*/site-packages")):
        raise argparse.ArgumentTypeError("committed dependency environment must contain an existing site-packages directory")
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--platforms", default="instagram")
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--dependency-cache",
        type=dependency_cache_path,
        help="existing writable private copy of the native SDK dependency cache",
    )
    parser.add_argument(
        "--dependency-state",
        type=Path,
        help="existing private copy of the SDK's committed dependency state; native runtime may write locks/leases there",
    )
    args = parser.parse_args()
    if args.dependency_state is not None:
        try:
            args.dependency_state = dependency_state_path(str(args.dependency_state), args.sdk)
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
    selected = args.platforms.split(",")
    assert len(selected) == len(set(selected)) and set(selected) <= set(CASES)
    sys.path.insert(0, str(args.sdk.resolve()))
    plugin = Path(__file__).resolve().parents[1] / "plugins/media-scout"
    with tempfile.TemporaryDirectory(prefix="scout-sdk-", dir=os.environ.get("TMPDIR")) as directory:
        home = Path(directory)
        os.environ.update(HERMES_HOME=str(home), HOME=str(home / "user"))
        (home / "user").mkdir()
        if args.dependency_cache is not None:
            cache_link = home / "cache/uv"
            cache_link.parent.mkdir(parents=True, exist_ok=True)
            cache_link.symlink_to(args.dependency_cache, target_is_directory=True)
        if args.dependency_state is not None:
            # Caller must supply a private copy: native runtime writes locks/leases.
            state_link = home / "installs" / args.dependency_state.name
            state_link.parent.mkdir(parents=True, exist_ok=True)
            state_link.symlink_to(args.dependency_state, target_is_directory=True)
        for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_TASK", "HERMES_KANBAN_RUN"):
            os.environ.pop(key, None)
        shutil.copytree(plugin, home / "plugins/media-scout", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        settings = {"owner_id": "111", "guild_id": "222", "parent_channel_id": "333", "auto_review": True, "review_policy_reference": "SYNTHETIC SDK fixture only", "review_profile": "default", "review_board": "scout-fixture", "rename_threads": True, "allow_cleanup": False}
        # A test-only permission fixture, not a real user's consent record.
        (home / "config.yaml").write_text(json.dumps({"plugins": {"enabled": ["media-scout"], "entries": {"media-scout": {"settings": settings, "granted_capabilities": ["gateway.platform_actions"]}}}}))
        from hermes_cli.plugins import PluginManager
        from hermes_cli.plugins import PluginContext
        from hermes_cli.plugins_manifest import parse_manifest_file
        from hermes_cli.platform_actions import PlatformActions
        from gateway.config import Platform
        from gateway.session import SessionSource
        from gateway.session_context import set_session_vars, clear_session_vars
        from tools.registry import registry
        import tools.terminal_tool
        launcher = shutil.which("hermes")
        assert launcher
        def terminal(command, timeout=30):
            raw = registry.dispatch("terminal", {"command": command, "timeout": timeout})
            result = json.loads(raw) if isinstance(raw, str) else raw
            assert result.get("exit_code") == 0, result
            return result
        prefix = f"env HERMES_HOME={shlex.quote(str(home))} {shlex.quote(launcher)} kanban"
        terminal(prefix + " boards create scout-fixture", timeout=180)
        manager = PluginManager(); manager.discover_and_load()
        assert any(p.get("name") == "media-scout" and p.get("enabled") for p in manager.list_plugins())
        # Use the supported SDK config writer to exercise the already-bound hook's
        # live config read. This is still isolated synthetic profile data.
        plugin_dir = home / "plugins/media-scout"
        manifest = parse_manifest_file(plugin_dir / "plugin.yaml", plugin_dir, "user", "")
        assert manifest is not None, f"failed to parse synthetic media-scout manifest: {plugin_dir / 'plugin.yaml'}"
        sdk_context = PluginContext(manifest, manager)
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
                async def admit(admission_payload=payload):
                    adapter.expected_loop = asyncio.get_running_loop()
                    # Isolated adapter stand-in only. Production plugin never accesses or patches SDK internals.
                    with patch.object(PlatformActions, "_resolve_adapter", return_value=(adapter, None)):
                        await manager.ainvoke_hook("post_gateway_admission", **admission_payload)
                asyncio.run(admit())
                recent = call(action="status")["recent"]
                item = next(call(action="get", media_id=row["media_id"]) for row in recent if call(action="get", media_id=row["media_id"])["source_platform"] == platform)
                media = item["media_id"]
                assert item["source_platform"] == platform
                assert adapter.titles[thread] == item["suggested_thread_title"]
                assert item["thread_names"][0]["state"] == "acknowledged"
                # Verify owner shutdown against persistent state and the fake adapter.
                db_path = home / "plugin-data/media-scout/data.db"
                with closing(sqlite3.connect(db_path)) as db:
                    media_before = db.execute("SELECT * FROM media ORDER BY rowid").fetchall()
                    receipts_before = db.execute("SELECT * FROM receipts ORDER BY rowid").fetchall()
                titles_before = dict(adapter.titles)
                shutdown_payload = dict(payload)
                shutdown_payload["message_id"] = "shutdown-" + message
                shutdown_payload["source"] = dict(payload["source"], message_id=shutdown_payload["message_id"])
                shutdown_payload["text"] = "SYNTHETIC shutdown probe: https://instagram.com/p/ShutdownCase" + str(index) + "/"
                try:
                    sdk_context.set_config("owner_id", "")
                    asyncio.run(admit(shutdown_payload))
                    with closing(sqlite3.connect(db_path)) as db:
                        assert db.execute("SELECT * FROM media ORDER BY rowid").fetchall() == media_before
                        assert db.execute("SELECT * FROM receipts ORDER BY rowid").fetchall() == receipts_before
                    assert adapter.titles == titles_before
                    rejected = registry.dispatch("media_scout", {"action": "claim", "media_id": media}, scope=manager.scope_key)
                    assert "error" in rejected.lower() or "owner" in rejected.lower(), rejected
                finally:
                    sdk_context.set_config("owner_id", "111")
                with closing(sqlite3.connect(db_path)) as db:
                    assert db.execute("SELECT * FROM media ORDER BY rowid").fetchall() == media_before
                    assert db.execute("SELECT * FROM receipts ORDER BY rowid").fetchall() == receipts_before
                assert adapter.titles == titles_before
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
                completed = call(action="review_status", media_id=media)
                assert completed["status"] == "done"
                assert completed["review_verification"] == "unverified" and completed["accepted_learning"] is False
                with closing(sqlite3.connect(home / "plugin-data/media-scout/data.db")) as db:
                    stored = db.execute("SELECT result FROM reviews WHERE media_id=?", (media,)).fetchone()[0]
                    note = json.loads(stored) if stored else {}
                    assert not note or not note.get("learning_note")
                results.append({"platform": platform, "capture_replay": True, "naming_sdk_ack": True, "same_event_loop": True, "owner_shutdown_verified": True, "evidence_hash_verified": True, "same_native_task_on_retry": True, "native_status": "done", "review_verification": "unverified synthetic operator completion", "completion_note_retained": False})
                if args.report: args.report.write_text(json.dumps({"synthetic": True, "results": results}, indent=2))
            finally:
                clear_session_vars(tokens)
        assert len(results) == len(selected)
        print(json.dumps({"ok": True, "synthetic": True, "platform_count": len(results), "platforms": results, "live_discord_tested": False, "live_source_extraction_tested": False}))


if __name__ == "__main__": main()
