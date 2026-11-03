from pathlib import Path
import importlib.util
import sqlite3
import time

from test_media_scout_core import load_module
from test_media_scout_safety import fixture_record, observed

MODULE = Path(__file__).parents[2] / "plugins/media-scout/retention.py"


def retention():
    assert MODULE.exists(), "bounded retention implementation must exist"
    spec = importlib.util.spec_from_file_location("scout_retention", MODULE)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_only_registered_expired_owned_files_are_removed(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    token = mod.claim(db, media, "owner")["claim_token"]
    mod.save_evidence(db, media, token, "Retained summary", observed(), "partial")
    root = tmp_path / "plugin-data/media-scout"
    cache = root / "cache"; cache.mkdir()
    (cache / "old.bin").write_bytes(b"expired synthetic data")
    (cache / "unrelated.bin").write_bytes(b"preserve unknown")
    api = retention()
    api.register_file(db, root, "cache/old.bin", media, "cache", int(time.time()) - 10)
    plan = api.plan(db, root)
    assert len(plan["candidates"]) == 1
    assert "error" in api.apply(db, root, plan["plan_id"], enabled=False)
    assert (cache / "old.bin").exists()
    result = api.apply(db, root, plan["plan_id"], enabled=True)
    assert result["deleted"] == ["cache/old.bin"]
    assert (cache / "unrelated.bin").read_bytes() == b"preserve unknown"
    assert mod.get_item(db, media)["summary"] == "Retained summary"
    db.close()


def test_drift_pins_active_and_symlinks_are_preserved(monkeypatch, tmp_path):
    mod = load_module(monkeypatch, tmp_path)
    db, _, media = fixture_record(mod, tmp_path)
    root = tmp_path / "plugin-data/media-scout"; (root / "cache").mkdir(parents=True)
    path = root / "cache/old.bin"; path.write_bytes(b"before")
    api = retention(); api.register_file(db, root, "cache/old.bin", media, "cache", int(time.time()) - 10)
    plan = api.plan(db, root); path.write_bytes(b"changed")
    assert "error" in api.apply(db, root, plan["plan_id"], enabled=True)
    assert path.read_bytes() == b"changed"
    api.register_file(db, root, "cache/old.bin", media, "cache", int(time.time()) - 10)
    db.execute("UPDATE media SET pinned=1 WHERE media_id=?", (media,)); db.commit()
    assert not api.plan(db, root)["candidates"]
    db.execute("UPDATE media SET pinned=0,claim_state='running' WHERE media_id=?", (media,)); db.commit()
    assert not api.plan(db, root)["candidates"]
    outside = tmp_path / "outside"; outside.write_bytes(b"never touch")
    link = root / "cache/link.bin"; link.symlink_to(outside)
    try:
        api.register_file(db, root, "cache/link.bin", media, "cache", int(time.time()) - 10)
    except ValueError:
        pass
    else:
        raise AssertionError("must reject symlink registration")
    assert outside.read_bytes() == b"never touch"
    db.close()
