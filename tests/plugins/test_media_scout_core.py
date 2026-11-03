from pathlib import Path
import importlib.util
import sqlite3
import sys
import types

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


def test_tool_never_trusts_model_supplied_owner(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    ctx = types.SimpleNamespace(get_config=lambda key, default=None: "owner" if key == "owner_id" else default)
    gateway = types.ModuleType("gateway.session_context")
    gateway.get_session_env = lambda name, default="": "intruder"
    monkeypatch.setitem(sys.modules, "gateway.session_context", gateway)
    assert "owner identity required" in mod._handler(ctx, {"action": "status", "owner_id": "owner"})
