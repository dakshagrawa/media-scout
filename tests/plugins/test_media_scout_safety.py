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


def test_save_finishes_claim_and_is_replay_safe(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    first = mod.save_evidence(db, media, token, "summary", observed(), "partial")
    assert first["saved"]
    assert mod.get_item(db, media)["claim_state"] == "saved"
    assert mod.save_evidence(db, media, token, "summary", observed(), "partial")["evidence_hash"] == first["evidence_hash"]
    assert hashlib.sha256(__import__("pathlib").Path(mod.get_item(db, media)["evidence_path"]).read_bytes()).hexdigest() == first["evidence_hash"]


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


def test_evidence_details_are_bounded_before_writing(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    ev = observed(); ev["observations"] = "x" * 100000
    assert "error" in mod.save_evidence(db, media, token, "summary", ev, "partial")


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
