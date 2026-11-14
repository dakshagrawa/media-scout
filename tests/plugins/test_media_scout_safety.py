import concurrent.futures
import hashlib
import json
import sqlite3
from pathlib import Path
import pytest

from test_media_scout_core import load_module


def test_owner_submission_intent_suppresses_automatic_review(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    for text in (
        "keep this local", "don’t share this", "do not share this",
        "don't send this to Default", "not for review", "dont share this",
        "keep this private", "don’t show this to anyone", "keep it confidential", "for my eyes only",
    ):
        assert mod._owner_intent_overrides_review(text), text
    for text in ("https://example.com/keep-this-local", "please review this", "share with my team"):
        assert not mod._owner_intent_overrides_review(text), text


def fixture_record(mod, tmp_path):
    path = tmp_path / "state.db"
    db = sqlite3.connect(path, timeout=5)
    mod.initialize(db)
    source = {"platform": "discord", "user_id": "owner", "chat_id": "42", "thread_id": "42", "guild_id": "7", "parent_chat_id": "8", "session_key": "discord:fixture"}
    media = mod.capture_receipt(db, "m1", source, "https://instagram.com/p/AbC123")["media_id"]
    return db, path, media


def observed():
    return {"audio": 0, "visual": 2, "pictures": 0, "times": ["00:01", "00:02"], "visual_mode": "sampled", "observations": "SYNTHETIC fixture observations, not real extracted media.", "limitations": "Only sampled fixture frames."}


def test_complete_rejects_empty_or_sampled_evidence(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    for ev in [{"audio": 0, "visual": 0, "pictures": 0, "times": []}, observed()]:
        assert "error" in mod.save_evidence(db, media, token, "summary", ev, "complete")
    db.close()


def test_save_finishes_claim_and_is_replay_safe(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    first = mod.save_evidence(db, media, token, "summary", observed(), "partial")
    assert first["saved"]
    assert mod.get_item(db, media)["claim_state"] == "saved"
    assert mod.save_evidence(db, media, token, "summary", observed(), "partial")["evidence_hash"] == first["evidence_hash"]
    assert hashlib.sha256(__import__("pathlib").Path(mod.get_item(db, media)["evidence_path"]).read_bytes()).hexdigest() == first["evidence_hash"]
    db.close()


def test_extraction_claim_excludes_concurrent_caller(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, path, media = fixture_record(mod, tmp_path)
    db.close()
    def acquire(_):
        conn = sqlite3.connect(path, timeout=5)
        try:
            return mod.claim(conn, media, "owner")
        finally:
            conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(acquire, range(8)))
    assert sum("claim_token" in r for r in results) == 1


def test_capture_cannot_rebind_existing_catalog_to_new_owner(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    other = {"platform": "discord", "user_id": "new-owner", "chat_id": "52", "guild_id": "7"}
    assert mod.capture_receipt(db, "m2", other, "https://instagram.com/p/AbC123") is None
    assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
    db.close()


def test_save_rejects_symlink_evidence_directory(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    root = tmp_path / "plugin-data/media-scout"
    root.mkdir(parents=True)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    (root / "evidence").symlink_to(outside, target_is_directory=True)
    assert "error" in mod.save_evidence(db, media, token, "summary", observed(), "partial")
    assert not list(outside.iterdir())
    db.close()


def test_evidence_details_are_bounded_before_writing(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    ev = observed(); ev["observations"] = "x" * 100000
    assert "error" in mod.save_evidence(db, media, token, "summary", ev, "partial")
    db.close()


def test_item_action_missing_or_invalid_media_id_is_actionable_and_no_write(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    settings = {"owner_id": "owner", "guild_id": "7", "parent_channel_id": "8"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    gateway = types.ModuleType("gateway.session_context")
    gateway.get_session_env = lambda name, default="": "owner"
    monkeypatch.setitem(__import__("sys").modules, "gateway.session_context", gateway)
    monkeypatch.setattr(mod, "_db", lambda: pytest.fail("invalid identity must not open storage"))
    for action, media_id in (("save", None), ("claim", "instagram_shortcode"), ("review", "")):
        args = {"action": action}
        if media_id is not None:
            args["media_id"] = media_id
        result = json.loads(mod._handler(ctx, args))
        assert "captured media_id" in result["error"]
        assert "status or get" in result["error"]
        assert "identity" not in result["error"] or "captured" in result["error"]
    gateway.get_session_env = lambda name, default="": "intruder"
    assert "owner identity required" in mod._handler(ctx, {"action": "save"})


def test_evidence_counts_reject_descriptive_objects_with_field_guidance(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    ev = observed(); ev["audio"] = {"transcript": "descriptive data"}
    result = mod.save_evidence(db, media, token, "summary", ev, "partial")
    assert "audio" in result["error"] and "nonnegative integer" in result["error"]
    assert mod.get_item(db, media)["claim_state"] == "running"
    db.close()


def test_declared_evidence_schema_matches_canonical_and_rejects_malformed_counts(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    registered = {}
    ctx = types.SimpleNamespace(register_skill=lambda *a: None, register_hook=lambda *a: None,
        register_command=lambda *a, **k: None, register_tool=lambda **kw: registered.update(kw))
    mod.register(ctx)
    schema = registered["schema"]["parameters"]["properties"]["evidence"]
    assert set(schema["required"]) == {"audio", "visual", "pictures", "times", "observations"}
    assert schema["properties"]["kind"]["enum"] == ["video", "image", "carousel", "text", "mixed"]
    for field in ("audio", "visual", "pictures"):
        assert schema["properties"][field]["type"] == "integer"
        assert schema["properties"][field]["minimum"] == 0
        assert schema["properties"][field]["maximum"] == 500
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    canonical = observed()
    assert mod.save_evidence(db, media, token, "Illustrative synthetic fixture", canonical, "partial")["saved"]
    media2 = mod.capture_receipt(db, "m2", {"platform": "discord", "user_id": "owner", "chat_id": "43", "thread_id": "43", "guild_id": "7", "parent_chat_id": "8", "session_key": "discord:fixture"}, "https://instagram.com/p/XyZ678")["media_id"]
    token2 = mod.claim(db, media2, "owner")["claim_token"]
    bad = dict(canonical, visual={"frames": 2})
    assert "visual" in mod.save_evidence(db, media2, token2, "Illustrative synthetic fixture", bad, "partial")["error"]
    db.close()


def test_owner_change_cannot_release_previous_owners_claim(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    mod.claim(db, media, "owner")
    monkeypatch.setattr(mod, "_db", lambda: db)
    settings = {"owner_id": "new-owner", "guild_id": "7", "parent_channel_id": "8"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    source = {"platform": "discord", "user_id": "new-owner", "scope_id": "7", "parent_chat_id": "8"}
    result = json.loads(mod._command(ctx, f"release {media} --writer-stopped", source))
    assert "error" in result
    db.close()


def test_native_capture_accepts_only_owner_scope_and_preserves_original_receipt(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    settings = {"owner_id": "owner", "guild_id": "7", "parent_channel_id": "8"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    source = {"platform": "discord", "user_id": "owner", "chat_id": "99", "thread_id": "99", "scope_id": "7", "parent_chat_id": "8", "chat_type": "group"}
    payload = dict(platform="discord", source=source, session_key="discord:fixture", message_id="m1", text="https://instagram.com/reel/AbC123/?img_index=2")
    mod._capture(ctx, **payload)
    for bad in [dict(source, user_id="intruder"), dict(source, scope_id="wrong"), dict(source, parent_chat_id="wrong"), dict(source, thread_id=None)]:
        mod._capture(ctx, **{**payload, "source": bad, "message_id": "m2"})
    mod._capture(ctx, **{**payload, "text": "https://instagram.com/reel/AbC123/?different=1"})
    db = mod._db()
    assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
    assert db.execute("SELECT source_url,session_key,chat_type FROM receipts").fetchone() == ("https://instagram.com/reel/AbC123/?img_index=2", "discord:fixture", "group")
    db.close()


def test_cleared_owner_dormants_registered_capture_and_tool_before_storage(monkeypatch, tmp_path):
    import asyncio
    import sys
    import types
    mod = load_module(monkeypatch, tmp_path)
    settings = {"owner_id": "owner", "guild_id": "7", "parent_channel_id": "8"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    source = {"platform": "discord", "user_id": "owner", "chat_id": "99", "thread_id": "99", "scope_id": "7", "parent_chat_id": "8", "chat_type": "group"}
    payload = dict(platform="discord", source=source, session_key="discord:fixture", message_id="m1", text="https://instagram.com/reel/AbC123/")
    assert mod._capture(ctx, **payload)
    settings["owner_id"] = ""
    monkeypatch.setattr(mod, "_db", lambda: pytest.fail("dormant intake opened storage"))
    different = {**payload, "message_id": "m2", "text": "https://youtube.com/watch?v=AbCdEf12345"}
    assert mod._capture(ctx, **different) is None
    asyncio.run(mod._admission(ctx, **different))
    gateway = types.ModuleType("gateway")
    session_context = types.ModuleType("gateway.session_context")
    session_context.get_session_env = lambda *args: "owner"
    monkeypatch.setitem(sys.modules, "gateway", gateway)
    monkeypatch.setitem(sys.modules, "gateway.session_context", session_context)
    for action in ("claim", "review", "review_status", "cleanup_apply"):
        result = json.loads(mod._handler(ctx, {"action": action, "media_id": "a" * 24, "plan_id": "plan"}))
        assert "error" in result


def test_complete_text_post_requires_real_text_basis_and_no_missing_media(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    evidence = {"kind": "text", "audio": 0, "visual": 0, "pictures": 0, "times": [], "text_segments": 1, "has_media": False, "visual_mode": "none", "text_content": ["SYNTHETIC captured text-post fixture, not actual creator content."], "observations": "SYNTHETIC publicly retrieved text-post fixture, not real creator content."}
    assert mod.save_evidence(db, media, token, "Synthetic text post", evidence, "complete")["saved"]
    db.close()



def test_multiplatform_capture_retains_legacy_ids_and_uses_platform_namespace(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    settings = {"owner_id": "owner", "guild_id": "7", "parent_channel_id": "8"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    source = {"platform": "discord", "user_id": "owner", "scope_id": "7", "parent_chat_id": "8", "chat_type": "group"}
    urls = [("instagram", "https://instagram.com/p/AbC123/"), ("youtube", "https://youtu.be/AbCdEf12345?t=7"), ("threads", "https://threads.com/@author/post/AbC123"), ("tiktok", "https://tiktok.com/@author/video/12345"), ("snapchat", "https://snapchat.com/spotlight/AbC123"), ("x", "https://x.com/author/status/12345"), ("reddit", "https://redd.it/abc123"), ("facebook", "https://facebook.com/reel/12345"), ("vimeo", "https://vimeo.com/12345"), ("bluesky", "https://bsky.app/profile/author.test/post/abc123")]
    for index, (platform, url) in enumerate(urls):
        thread = str(100 + index)
        mod._capture(ctx, platform="discord", source=dict(source, chat_id=thread, thread_id=thread), session_key="discord:fixture:"+thread, message_id="message"+thread, text=url)
    db = mod._db()
    rows = db.execute("SELECT media_id FROM media").fetchall()
    assert len(rows) == len(urls)
    seen = set()
    for (media,) in rows:
        item = mod.get_item(db, media); seen.add(item["source_platform"])
    assert seen == {x[0] for x in urls}
    assert db.execute("SELECT media_id FROM media WHERE shortcode='AbC123'").fetchone()[0] == mod._identity_shortcode("AbC123")
    db.close()


def test_v010_catalog_upgrades_without_rekeying_or_erasing_claim(monkeypatch, tmp_path):
    import subprocess, types
    from pathlib import Path
    mod = load_module(monkeypatch, tmp_path)
    root = Path(__file__).parents[2]
    original = subprocess.run(["git", "show", "media-scout-v0.1.0:plugins/media-scout/__init__.py"], cwd=root, capture_output=True, text=True, check=True).stdout
    legacy = types.ModuleType("legacy_scout")
    legacy.__file__ = str(root / "plugins/media-scout/__init__.py")
    exec(compile(original, legacy.__file__, "exec"), legacy.__dict__)
    db = sqlite3.connect(tmp_path / "legacy.db")
    legacy.initialize(db)
    receipt = legacy.capture_receipt(db, "original", {"platform": "discord", "user_id": "owner", "chat_id": "42", "thread_id": "42", "guild_id": "7"}, "https://instagram.com/p/AbC123/?img_index=2")
    token = legacy.claim(db, receipt["media_id"], "owner")["claim_token"]
    before = db.execute("SELECT * FROM receipts").fetchall()
    mod.initialize(db)
    item = mod.get_item(db, receipt["media_id"])
    assert item["claim_token"] == token and item["source_platform"] == "instagram"
    assert db.execute("SELECT * FROM receipts").fetchall() == before
    assert db.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 1
    db.close()


def test_second_distinct_source_cannot_retarget_existing_thread(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db = sqlite3.connect(tmp_path / "bound.db"); mod.initialize(db)
    source = {"platform": "discord", "user_id": "owner", "chat_id": "42", "thread_id": "42", "guild_id": "7"}
    first = mod.capture_receipt(db, "one", source, "https://instagram.com/p/AbC123/")
    assert first
    assert mod.capture_receipt(db, "two", source, "https://youtu.be/AbCdEf12345") is None
    assert db.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 1
    assert db.execute("SELECT media_id FROM receipts").fetchone()[0] == first["media_id"]
    db.close()


def test_complete_text_requires_bounded_retained_segments_not_just_a_count(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    base = {"kind": "text", "audio": 0, "visual": 0, "pictures": 0, "times": [], "text_segments": 1, "has_media": False, "visual_mode": "none", "observations": "SYNTHETIC observation alone is not captured source text."}
    for invalid in [None, [], [""], ["   "], "not an array", ["one", "two"], [42], ["x" * 16001]]:
        evidence = dict(base)
        if invalid is not None:
            evidence["text_content"] = invalid
        assert "error" in mod.save_evidence(db, media, token, "Synthetic text", evidence, "complete"), invalid
    evidence = dict(base, text_content=["SYNTHETIC captured source text, not real creator material."])
    assert mod.save_evidence(db, media, token, "Synthetic text", evidence, "complete")["saved"]
    db.close()


def test_optional_intake_thread_scope_leaves_other_threads_untouched(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    settings = {"owner_id": "owner", "guild_id": "7", "parent_channel_id": "8", "intake_thread_id": "101"}
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    source = {"platform": "discord", "user_id": "owner", "scope_id": "7", "parent_chat_id": "8", "chat_type": "group"}
    def capture(thread, message, url):
        return mod._capture(ctx, platform="discord", source=dict(source, chat_id=thread, thread_id=thread), session_key="discord:fixture:" + thread, message_id=message, text=url)
    assert capture("102", "not-pilot", "https://youtu.be/AbCdEf12345") is None
    accepted = capture("101", "pilot", "https://youtu.be/AbCdEf12345")
    assert accepted
    db = mod._db()
    assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
    assert db.execute("SELECT thread_id FROM receipts").fetchone()[0] == "101"
    db.close()


def test_review_opt_out_never_dispatches_or_creates_review_rows(monkeypatch, tmp_path):
    import types
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    assert mod.save_evidence(db, media, token, "Synthetic test only", observed(), "partial")["saved"]
    settings = {"owner_id": "owner", "auto_review": True, "review_policy_reference": "synthetic authorized fixture"}
    calls = []
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default), dispatch_tool=lambda *a, **kw: calls.append((a, kw)))
    import importlib
    assert isinstance(mod.__package__, str)
    bridge = importlib.import_module(mod.__package__ + ".bridge")
    monkeypatch.setattr(bridge.shutil, "which", lambda name: "/usr/bin/hermes")
    for phrase in ("keep this local", "don’t share this", "do not share this", "don't send this to Default", "not for review", "keep this private", "don’t show this to anyone", "keep it confidential", "for my eyes only"):
        db.execute("UPDATE receipts SET source_text=?", (phrase + " https://instagram.com/p/AbC123",)); db.commit()
        result = mod._review(ctx, db, media)
        assert result["error"] == "owner source overrides automatic review"
        assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 0
    assert calls == []
    db.close()


def _review_harness(monkeypatch, tmp_path, mod, data_root, *, contract_path="", contract_hash=""):
    import types
    settings = {"owner_id":"owner", "auto_review":True, "review_policy_reference":"operator consent",
                "review_contract_path":contract_path, "review_contract_sha256":contract_hash}
    class Bridge:
        bodies = []
        def __init__(self, *args): pass
        @staticmethod
        def packet_body(body, origin, key): return body + "\n<!-- marker -->"
        def ensure_review(self, key, origin, body, **kwargs):
            self.bodies.append(body)
            return {"task_id":"task_12345678", "status":"blocked", "source_verified":True, "error":"held"}
    import importlib
    bridge = importlib.import_module(mod.__package__ + ".bridge")
    monkeypatch.setattr(bridge, "NativeBridge", Bridge)
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    return ctx, Bridge


def test_configured_review_contract_is_literal_and_default_stays_generic(monkeypatch, tmp_path):
    import hashlib
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    assert mod.save_evidence(db, media, token, "Synthetic review fixture", observed(), "partial")["saved"]
    data_root = tmp_path / "plugin-data" / "media-scout"
    configured = data_root / "operator-contract.md"
    literal = "FULL OPERATOR FIXTURE: retain source provenance and disclose uncertainty.\n"
    configured.write_text(literal)
    ctx, bridge = _review_harness(monkeypatch, tmp_path, mod, data_root,
                                  contract_path="operator-contract.md", contract_hash=hashlib.sha256(literal.encode()).hexdigest())
    result = mod._review(ctx, db, media)
    assert result.get("task_id") == "task_12345678"
    assert len(bridge.bodies) >= 1 and all(literal in body for body in bridge.bodies)
    assert db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] == 1
    db.close()


def test_contract_drift_blocks_review_binding_and_dispatch(monkeypatch, tmp_path):
    import hashlib
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    assert mod.save_evidence(db, media, token, "Synthetic review fixture", observed(), "partial")["saved"]
    data_root = tmp_path / "plugin-data" / "media-scout"
    configured = data_root / "operator-contract.md"
    configured.write_text("changed contract")
    packet = mod.get_item(db, media)["packet_version"]
    db.execute("INSERT INTO reviews(media_id,packet_version,origin,task_id,state,assignee,board) VALUES(?,?,?,?,?,?,?)",
               (media, packet, '{"preserved":true}', "existing_task", "pending", "reviewer", "media-review"))
    db.commit()
    ctx, bridge = _review_harness(monkeypatch, tmp_path, mod, data_root,
                                  contract_path="operator-contract.md", contract_hash=hashlib.sha256(b"original").hexdigest())
    result = mod._review(ctx, db, media)
    assert "hash-mismatched" in result["error"]
    assert db.execute("SELECT origin,task_id,state FROM reviews WHERE media_id=? AND packet_version=?", (media, packet)).fetchone() == ('{"preserved":true}', "existing_task", "pending")
    assert bridge.bodies == []
    db.close()


def test_unconfigured_review_uses_generic_contract_only(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    assert mod.save_evidence(db, media, token, "Synthetic review fixture", observed(), "partial")["saved"]
    data_root = tmp_path / "plugin-data" / "media-scout"
    ctx, bridge = _review_harness(monkeypatch, tmp_path, mod, data_root)
    result = mod._review(ctx, db, media)
    generic = (Path(str(mod.__file__)).parent / "skills/workflow/references/review-contract.md").read_text()
    assert result.get("task_id") == "task_12345678"
    assert bridge.bodies and all(generic in body and "FULL OPERATOR FIXTURE" not in body for body in bridge.bodies)
    db.close()


def test_configured_web_admission_and_registered_tool(monkeypatch, tmp_path):
    import asyncio, sys, types, socket
    mod=load_module(monkeypatch,tmp_path)
    settings={"owner_id":"owner","guild_id":"7","parent_channel_id":"8"}
    class Ctx:
        def get_config(self,k,d=None): return settings.get(k,d)
        def register_skill(self,*a): pass
        def register_hook(self,*a): self.hook=a[1]
        def register_command(self,*a,**kw): pass
        def register_tool(self,*,handler,**kw): self.handler=handler
    ctx=Ctx(); mod.register(ctx)
    session=types.ModuleType("gateway.session_context"); session.get_session_env=lambda k,d="": "owner" if k=="HERMES_SESSION_USER_ID" else d
    monkeypatch.setitem(sys.modules,"gateway.session_context",session)
    monkeypatch.setattr(socket,"getaddrinfo",lambda *a,**k: pytest.fail("network lookup"))
    source={"platform":"discord","user_id":"owner","scope_id":"7","parent_chat_id":"8","chat_id":"42","thread_id":"42"}
    args=dict(source=source,platform="discord",message_id="m1",session_key="key",text="https://example.org/article?view=full")
    assert mod._capture(ctx,**args) is None
    settings["allowed_web_hosts"]=["example.org"]
    assert mod._capture(ctx,**{**args,"source":{**source,"user_id":"other"}}) is None
    item=mod._capture(ctx,**args); assert item and item["platform"]=="web"
    run=lambda a: json.loads(asyncio.run(ctx.handler(a)))
    media=item["media_id"]
    assert run({"action":"get","media_id":media})["canonical_url"]==args["text"]
    assert run({"action":"search","query":args["text"]})["native_count"]==1
    token=run({"action":"claim","media_id":media})["claim_token"]
    evidence={"kind":"text","audio":0,"visual":0,"pictures":0,"times":[],"observations":"Synthetic article text was inspected.","text_content":["Synthetic article."],"text_segments":1,"has_media":False}
    assert run({"action":"save","media_id":media,"claim_token":token,"summary":"Synthetic article","coverage":"complete","evidence":evidence})["saved"]
    pdf="https://example.org/paper.pdf"
    asyncio.run(ctx.hook(**{**args,"text":pdf,"message_id":"m2","source":{**source,"thread_id":"43","chat_id":"43"}}))
    match=run({"action":"search","query":pdf})["native_matches"][0]
    assert run({"action":"get","media_id":match["media_id"]})["source_platform"]=="pdf_link"
    settings["allowed_web_hosts"]=[]
    assert run({"action":"search","query":pdf})["native_count"]==1
    settings["allowed_web_hosts"]=["example.org", "127.0.0.1", "localhost", "*.org"]
    for bad in ("https://127.0.0.1/a", "https://example.org/a?token=secret", "https://example.org/a?url=https://evil.test/", "https://example.org/a https://evil.test/b", "https://example.org/a https://instagram.com/p/AbC123", "https://user:pass@example.org/a", "https://example.org:443/a", "https://example.org/a#fragment", "https://localhost/a", "https://evil.org/a"):
        assert mod._capture(ctx,**{**args,"message_id":"bad", "text":bad}) is None
