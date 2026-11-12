from pathlib import Path
import importlib.util
import sqlite3
import sys
import types
import asyncio
import json

MODULE = Path(__file__).parents[2] / "plugins" / "media-scout" / "__init__.py"


def load_module(monkeypatch, tmp_path):
    data = tmp_path / "plugin-data"
    data.mkdir()
    storage = types.ModuleType("plugins.plugin_storage")
    def data_dir(name):
        path = data / name; path.mkdir(exist_ok=True); return path
    storage.plugin_data_dir = data_dir
    storage.plugin_db = lambda name: sqlite3.connect(data_dir(name) / "data.db", timeout=5)
    monkeypatch.setitem(sys.modules, "plugins.plugin_storage", storage)
    spec = importlib.util.spec_from_file_location("media_scout", MODULE)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "media_scout", mod)
    spec.loader.exec_module(mod)
    return mod


def test_reel_identity_preserves_case_and_functional_query(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    parsed = mod.parse_instagram_url("https://www.instagram.com/p/AbC123/?img_index=2&utm_source=x#frame")
    assert parsed == ("AbC123", "https://www.instagram.com/p/AbC123/?img_index=2&utm_source=x#frame")
    assert mod.canonical_identity("https://instagram.com/p/AbC123/?img_index=2&utm_source=x") == "AbC123"


def test_registered_async_name_action_uses_captured_source_and_facade(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    path = tmp_path / "plugin-data" / "media-scout" / "data.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    mod.initialize(db)
    source = {"platform": "discord", "user_id": "owner", "scope_id": "guild", "guild_id": "guild",
              "parent_chat_id": "parent", "chat_id": "thread", "thread_id": "thread"}
    receipt = mod.capture_receipt(db, "message", source, "https://bsky.app/profile/alexbenzer.com/post/3mysmixc7hs2k")
    db.execute("UPDATE media SET summary='saved summary',evidence_hash='evidence-hash',claim_token='claim-token',claim_state='done',review_task_id='task-id' WHERE media_id=?", (receipt["media_id"],))
    db.commit()
    db.close()
    cached = path.parent / "cache" / receipt["media_id"]
    cached.mkdir(parents=True)
    (cached / "source.info.json").write_text(json.dumps({"webpage_url":"https://bsky.app/profile/alexbenzer.com/post/3mysmixc7hs2k", "uploader_id":"alexbenzer.com"}))

    monkeypatch.setattr(mod, "_db", lambda: sqlite3.connect(path))
    session = types.ModuleType("gateway.session_context")
    session_values = {"HERMES_SESSION_USER_ID":"owner", "HERMES_SESSION_PLATFORM":"discord",
                      "HERMES_SESSION_CHAT_ID":"thread", "HERMES_SESSION_THREAD_ID":"thread",
                      "HERMES_SESSION_SCOPE_ID":"guild", "HERMES_SESSION_PARENT_CHAT_ID":"parent"}
    session.get_session_env = lambda name, default="": session_values.get(name, default)
    monkeypatch.setitem(sys.modules, "gateway.session_context", session)
    calls = []
    facade_result = {"ok": False, "error": "capability_not_granted"}
    async def set_title(platform, chat, thread, title):
        calls.append((platform, chat, thread, title))
        return facade_result
    class Context:
        platform_actions = types.SimpleNamespace(set_thread_title=set_title)
        settings = {"owner_id":"owner", "guild_id":"guild", "parent_channel_id":"parent", "rename_threads":True}
        def __init__(self): self.tools = {}
        def get_config(self, key, default=None):
            return self.settings.get(key, default)
        def register_skill(self, *a): pass
        def register_hook(self, *a): pass
        def register_command(self, *a, **kw): pass
        def register_tool(self, *, name, handler, **kw): self.tools[name] = (handler, kw)
    ctx = Context()
    mod.register(ctx)
    handler, registration = ctx.tools["media_scout"]
    assert registration["is_async"] is True
    arguments = {"action":"name_thread", "media_id":receipt["media_id"], "author":"alexbenzer.com"}
    result = json.loads(asyncio.run(handler(arguments)))  # real model-call shape: no source kwarg
    assert result["state"] == "failed" and result["detail"] == "capability_not_granted"
    assert "submitted" not in result
    facade_result.update(ok=True, error="")
    result = json.loads(asyncio.run(handler(arguments)))
    assert result["state"] == "acknowledged" and result["acknowledgment_only"] is True
    assert json.loads(asyncio.run(handler({"action":"name_thread", "media_id":receipt["media_id"]}))) ["state"] == "acknowledged"
    asyncio.run(handler(arguments))
    assert calls == [("discord", "thread", "thread", "bluesky_alexbenzer_com_3mysmixc7hs2k")] * 2
    assert json.loads(asyncio.run(handler(arguments, source={**source, "thread_id":"foreign"}))) == {"error":"injected source conflicts with trusted session context"}
    session_values["HERMES_SESSION_THREAD_ID"] = "foreign"
    assert json.loads(asyncio.run(handler(arguments)))["error"] == "captured source thread not found"
    session_values["HERMES_SESSION_THREAD_ID"] = "thread"
    ctx.settings["owner_id"] = ""
    assert json.loads(asyncio.run(handler(arguments)))["error"] == "captured owner source and naming consent required"
    db = sqlite3.connect(path)
    assert db.execute("SELECT title,state FROM thread_titles").fetchone() == ("bluesky_alexbenzer_com_3mysmixc7hs2k", "acknowledged")
    assert db.execute("SELECT author FROM thread_authors").fetchone() == ("alexbenzer.com",)
    assert db.execute("SELECT source_url,thread_id FROM receipts").fetchone() == ("https://bsky.app/profile/alexbenzer.com/post/3mysmixc7hs2k", "thread")
    assert db.execute("SELECT summary,evidence_hash,claim_token,claim_state,review_task_id FROM media WHERE media_id=?", (receipt["media_id"],)).fetchone() == ("saved summary", "evidence-hash", "claim-token", "done", "task-id")
    assert db.execute("SELECT COUNT(*) FROM thread_titles WHERE title LIKE '%foreign%'").fetchone() == (0,)
    db.close()


def test_registered_save_automatically_names_from_explicit_author(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    path = tmp_path / "plugin-data" / "media-scout" / "data.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path); mod.initialize(db)
    source = {"platform":"discord", "user_id":"owner", "scope_id":"guild", "parent_chat_id":"parent", "chat_id":"thread", "thread_id":"thread"}
    captured = mod.capture_receipt(db, "msg", source, "https://instagram.com/reel/AbCdEfG")
    token = mod.claim(db, captured["media_id"], "owner")["claim_token"]
    db.close()
    cached = path.parent / "cache" / captured["media_id"]
    cached.mkdir(parents=True)
    (cached / "extract.info.json").write_text(json.dumps({"webpage_url":"https://instagram.com/reel/AbCdEfG", "uploader_id":"sample_creator"}))
    monkeypatch.setattr(mod, "_db", lambda: sqlite3.connect(path))
    session = types.ModuleType("gateway.session_context")
    values = {"HERMES_SESSION_USER_ID":"owner", "HERMES_SESSION_PLATFORM":"discord", "HERMES_SESSION_CHAT_ID":"thread", "HERMES_SESSION_THREAD_ID":"thread", "HERMES_SESSION_SCOPE_ID":"guild", "HERMES_SESSION_PARENT_CHAT_ID":"parent"}
    setattr(session, "get_session_env", lambda name, default="": values.get(name, default))
    monkeypatch.setitem(sys.modules, "gateway.session_context", session)
    titles = []
    async def set_title(platform, chat, thread, title):
        titles.append(title); return {"ok":True}
    class Context:
        settings = {"owner_id":"owner", "guild_id":"guild", "parent_channel_id":"parent", "rename_threads":True}
        platform_actions = types.SimpleNamespace(set_thread_title=set_title)
        def __init__(self): self.tools = {}
        def get_config(self, key, default=None): return self.settings.get(key, default)
        def register_skill(self, *a): pass
        def register_hook(self, *a): pass
        def register_command(self, *a, **kw): pass
        def register_tool(self, *, name, handler, **kw): self.tools[name] = (handler, kw)
    ctx = Context(); mod.register(ctx)
    handler, registration = ctx.tools["media_scout"]
    assert registration["is_async"] is True
    save_args = {"action":"save", "media_id":captured["media_id"], "claim_token":token, "summary":"Synthetic saved evidence.", "coverage":"partial", "evidence":{"audio":0,"visual":1,"pictures":0,"times":[],"observations":"Synthetic fixture observations, not actual extracted media.","limitations":"Synthetic partial fixture."}}
    result = json.loads(asyncio.run(handler(save_args)))
    assert result["saved"] is True and result["naming"]["state"] == "acknowledged"
    assert titles == ["instagram_sample_creator_AbCdEfG"]
    state_db = sqlite3.connect(path)
    state_db.execute("UPDATE thread_titles SET state='failed' WHERE thread_id='thread'")
    state_db.commit()
    state_db.close()
    async def denied(*args): raise RuntimeError("synthetic post-save naming failure")
    ctx.platform_actions.set_thread_title = denied
    retried = json.loads(asyncio.run(handler(save_args)))
    assert retried["saved"] is True and retried["naming"]["state"] in {"failed", "deferred"}
    db = sqlite3.connect(path)
    assert db.execute("SELECT author FROM thread_authors").fetchone() == ("sample_creator",)
    assert db.execute("SELECT evidence_hash,claim_state FROM media").fetchone()[0]
    db.close()


def test_initialize_adds_author_metadata_without_rewriting_legacy_records(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db = sqlite3.connect(tmp_path / "legacy.db")
    db.executescript("CREATE TABLE media(media_id TEXT PRIMARY KEY,shortcode TEXT NOT NULL UNIQUE,created_at INTEGER NOT NULL,summary TEXT NOT NULL DEFAULT '',evidence_hash TEXT NOT NULL DEFAULT '',evidence_path TEXT NOT NULL DEFAULT '',coverage TEXT NOT NULL DEFAULT '',claim_token TEXT NOT NULL DEFAULT '',claim_owner TEXT NOT NULL DEFAULT '',claim_state TEXT NOT NULL DEFAULT '',pinned INTEGER NOT NULL DEFAULT 0,review_task_id TEXT NOT NULL DEFAULT '',review_key TEXT NOT NULL DEFAULT '',packet_version INTEGER NOT NULL DEFAULT 0); CREATE TABLE receipts(receipt_id TEXT PRIMARY KEY,message_id TEXT NOT NULL UNIQUE,media_id TEXT NOT NULL,source_url TEXT NOT NULL,platform TEXT NOT NULL,owner_id TEXT NOT NULL,guild_id TEXT NOT NULL,parent_channel_id TEXT NOT NULL,chat_id TEXT NOT NULL,thread_id TEXT NOT NULL,created_at INTEGER NOT NULL,session_key TEXT NOT NULL DEFAULT '',source_text TEXT NOT NULL DEFAULT '',chat_type TEXT NOT NULL DEFAULT 'group'); CREATE TABLE thread_titles(thread_id TEXT PRIMARY KEY,media_id TEXT NOT NULL,title TEXT NOT NULL,state TEXT NOT NULL,detail TEXT NOT NULL DEFAULT ''); INSERT INTO media(media_id,shortcode,created_at,summary,evidence_hash,claim_token,claim_state,review_task_id) VALUES('m','id',1,'summary','hash','claim','running','task'); INSERT INTO receipts VALUES('r','msg','m','https://youtube.com/watch?v=AbCdEf12345','discord','owner','guild','parent','chat','thread',1,'session','url','group');")
    mod.initialize(db)
    assert db.execute("SELECT summary,evidence_hash,claim_token,claim_state,review_task_id FROM media").fetchone() == ("summary", "hash", "claim", "running", "task")
    assert db.execute("SELECT source_url,thread_id FROM receipts").fetchone() == ("https://youtube.com/watch?v=AbCdEf12345", "thread")
    assert db.execute("SELECT COUNT(*) FROM thread_authors").fetchone() == (0,)
    db.close()


def test_rejects_ambiguous_or_untrusted_instagram_urls(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    for value in (
        "https://instagram.com.evil/p/AbC123", "https://u@instagram.com/p/AbC123",
        "https://instagram.com:443/p/AbC123", "https://instagram.com/p/%2e%2e",
        "https://instagram.com/p/a https://instagram.com/p/b",
    ):
        assert mod.parse_instagram_url(value) is None


def test_receipt_replay_is_idempotent_and_does_not_reset_claim(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db = sqlite3.connect(tmp_path / "state.db", timeout=5)
    mod.initialize(db)
    source = {"platform": "discord", "user_id": "owner", "chat_id": "42", "thread_id": "99", "guild_id": "7"}
    first = mod.capture_receipt(db, "m1", source, "https://instagram.com/reel/AbC123/?utm_source=x")
    claim = mod.claim(db, first["media_id"], "owner")
    again = mod.capture_receipt(db, "m1", source, "https://instagram.com/reel/AbC123/?different=1")
    assert again["receipt_id"] == first["receipt_id"]
    assert mod.get_item(db, first["media_id"])["claim_token"] == claim["claim_token"]
    stored = db.execute("SELECT source_url FROM receipts WHERE message_id=?", ("m1",)).fetchone()[0]
    assert stored.endswith("utm_source=x")
    db.close()


def test_save_requires_claim_token_and_structured_coverage(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db = sqlite3.connect(tmp_path / "state.db")
    mod.initialize(db)
    source = {"platform": "discord", "user_id": "owner", "chat_id": "42", "guild_id": "7"}
    media = mod.capture_receipt(db, "m1", source, "https://instagram.com/p/AbC123")["media_id"]
    token = mod.claim(db, media, "owner")["claim_token"]
    assert mod.save_evidence(db, media, "wrong", "summary", {"audio": 1, "visual": 1, "pictures": 0, "times": ["00:01"]}, "partial")["error"]
    assert mod.save_evidence(db, media, token, "summary", {}, "complete")["error"]
    result = mod.save_evidence(db, media, token, "Summary", {"audio": 0, "visual": 2, "pictures": 0, "times": ["00:01", "00:02"], "visual_mode": "sampled", "observations": "Synthetic fixture observations, not actual extracted media.", "limitations": "Sampled fixture only."}, "partial")
    assert result["saved"] is True
    row = mod.get_item(db, media)
    assert row["coverage"] == "partial" and row["evidence_hash"]
    db.close()


def test_tool_never_trusts_model_supplied_owner(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: "owner" if key == "owner_id" else default)
    gateway = types.ModuleType("gateway.session_context")
    gateway.get_session_env = lambda name, default="": "intruder"
    monkeypatch.setitem(sys.modules, "gateway.session_context", gateway)
    assert "owner identity required" in mod._handler(ctx, {"action": "status", "owner_id": "owner"})


def test_cached_author_requires_exact_source_and_rejects_symlinks_and_oversize(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    base = tmp_path / "plugin-data" / "media-scout"
    monkeypatch.setattr(mod, "_data_root", lambda: base)
    item = "a" * 24
    cache = base / "cache" / item
    cache.mkdir(parents=True)
    metadata = cache / "source.info.json"
    metadata.write_text(json.dumps({"webpage_url":"https://youtu.be/AbCdEf12345", "uploader_id":"@actual"}))
    assert mod._cached_source_author(item, "https://youtube.com/watch?v=AbCdEf12345&utm_source=x") == "@actual"
    assert mod._cached_source_author(item, "https://youtu.be/ZyXwVu98765") is None
    metadata.write_text(json.dumps({"webpage_url":"https://youtu.be/AbCdEf12345", "uploader_id":"@actual", "padding":"x" * (513 * 1024)}))
    assert mod._cached_source_author(item, "https://youtu.be/AbCdEf12345") is None
    metadata.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"webpage_url":"https://youtu.be/AbCdEf12345", "uploader_id":"@wrong"}))
    metadata.symlink_to(outside)
    assert mod._cached_source_author(item, "https://youtu.be/AbCdEf12345") is None
    metadata.unlink()
    cache.rmdir()
    cache.symlink_to(tmp_path, target_is_directory=True)
    assert mod._cached_source_author(item, "https://youtu.be/AbCdEf12345") is None
    cache.unlink()
    cache.parent.rmdir()
    cache.parent.symlink_to(tmp_path, target_is_directory=True)
    assert mod._cached_source_author(item, "https://youtu.be/AbCdEf12345") is None


def test_import_keyword_fields_include_retained_knowledge_and_creator_claims():
    spec = importlib.util.spec_from_file_location("media_scout_import_for_test", MODULE.with_name("import_v1.py"))
    assert spec and spec.loader
    importer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(importer)
    text = importer._keywords({"retained_knowledge":["fact alpha"], "creator_claims":["claim beta"]})
    assert "fact alpha" in text and "claim beta" in text
