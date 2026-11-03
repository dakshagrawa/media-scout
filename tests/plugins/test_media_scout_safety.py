import concurrent.futures
import hashlib
import json
import sqlite3

from test_media_scout_core import load_module


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
