import asyncio
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import types

MODULE = Path(__file__).parents[2] / "plugins/media-scout/naming.py"


def load():
    assert MODULE.exists(), "public platform-action naming implementation required"
    spec = importlib.util.spec_from_file_location("scout_naming", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup(tmp_path, result):
    path = tmp_path / "state.db"
    db = sqlite3.connect(path)
    db.executescript("CREATE TABLE receipts(thread_id TEXT,media_id TEXT,owner_id TEXT,guild_id TEXT,parent_channel_id TEXT,chat_id TEXT); INSERT INTO receipts VALUES('44','media','11','22','33','44'); CREATE TABLE thread_titles(thread_id TEXT PRIMARY KEY,media_id TEXT,title TEXT,state TEXT,detail TEXT);")
    db.close()
    calls = []
    async def rename(platform, chat_id, thread_id, title):
        calls.append((platform, chat_id, thread_id, title, asyncio.get_running_loop()))
        return result
    settings = {"rename_threads": True, "owner_id": "11", "guild_id": "22", "parent_channel_id": "33"}
    ctx = types.SimpleNamespace(get_config=lambda k, default=None: settings.get(k, default), platform_actions=types.SimpleNamespace(set_thread_title=rename))
    source = {"platform": "discord", "user_id": "11", "scope_id": "22", "parent_chat_id": "33", "chat_id": "44", "thread_id": "44"}
    return ctx, source, lambda: sqlite3.connect(path), calls, settings


def test_naming_awaits_public_facade_on_callers_loop_and_reuses_ack(tmp_path):
    api = load(); ctx, source, factory, calls, _ = setup(tmp_path, {"ok": True})
    async def run():
        loop = asyncio.get_running_loop()
        await api.rename_captured_thread(ctx, source, "youtube_TestVideo12", "media", factory)
        await api.rename_captured_thread(ctx, source, "youtube_TestVideo12", "media", factory)
        assert calls == [("discord", "44", "44", "youtube_TestVideo12", loop)]
    asyncio.run(run())
    with closing(factory()) as db:
        assert db.execute("SELECT title,state FROM thread_titles").fetchone() == ("youtube_TestVideo12", "acknowledged")


def test_missing_permission_is_recorded_without_breaking_intake(tmp_path):
    api = load(); ctx, source, factory, calls, _ = setup(tmp_path, {"ok": False, "error": "capability_not_granted"})
    asyncio.run(api.rename_captured_thread(ctx, source, "threads_AbC123", "media", factory))
    with closing(factory()) as db:
        assert db.execute("SELECT state,detail FROM thread_titles").fetchone() == ("failed", "capability_not_granted")
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1


def test_foreign_sources_and_disabled_naming_cannot_rename(tmp_path):
    api = load(); ctx, source, factory, calls, settings = setup(tmp_path, {"ok": True})
    asyncio.run(api.rename_captured_thread(ctx, dict(source, user_id="intruder"), "tiktok_123", "media", factory))
    settings["rename_threads"] = False
    asyncio.run(api.rename_captured_thread(ctx, source, "tiktok_123", "media", factory))
    assert calls == []
