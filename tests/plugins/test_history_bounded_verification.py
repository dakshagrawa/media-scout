"""Offline tests for bounded memory and batch/owner isolation in artifact verification (#12)."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sqlite3
import sys
import tracemalloc
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "media-scout"


def _load_pkg():
    pkg_name = "ms_bounded_pkg"
    if pkg_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            pkg_name,
            PLUGIN_DIR / "__init__.py",
            submodule_search_locations=[str(PLUGIN_DIR)],
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[pkg_name] = mod
        spec.loader.exec_module(mod)

    return (
        importlib.import_module(f"{pkg_name}.history"),
        importlib.import_module(f"{pkg_name}.import_v1"),
        importlib.import_module(f"{pkg_name}.retention"),
    )


def _seed_history(tmp_path: Path, history, *, owner="owner-a", batch_id="batch-1", rel="records/rec1.json", payload=None):
    db = sqlite3.connect(":memory:")
    history.initialize_history(db)
    v1_root = tmp_path / "v1-import"
    rec_path = v1_root / rel
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    record = payload if payload is not None else {"media_id": "med-1", "title": "Sample", "summary": "Grounded summary", "source_url": "https://example.com/p/1"}
    raw_bytes = json.dumps(record, sort_keys=True).encode("utf-8")
    rec_path.write_bytes(raw_bytes)
    sha = hashlib.sha256(raw_bytes).hexdigest()
    rec_json = raw_bytes.decode("utf-8")
    rec_key = hashlib.sha256((owner + "\0" + record["media_id"]).encode()).hexdigest()
    db.execute("INSERT INTO history_imports VALUES(?,?,?,datetime('now'))", (batch_id, owner, "{}"))
    db.execute(
        "INSERT INTO history_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rec_key, batch_id, owner, record["media_id"], record["source_url"], record["source_url"], rec_json, rel, sha, sha, "", "sample", "[]", "{}"),
    )
    db.execute("INSERT INTO history_files VALUES(?,?,?,?)", (batch_id, rel, sha, len(raw_bytes)))
    db.commit()
    return db, rec_path, sha, len(raw_bytes)


def test_valid_drift_missing_and_symlink_rejection(tmp_path: Path):
    history, _, _ = _load_pkg()
    db, rec_path, sha, size = _seed_history(tmp_path, history)

    # Valid artifact
    res = history.get(db, "owner-a", "med-1", tmp_path)
    assert "error" not in res and len(res["records"]) == 1

    # Hash drift (same size, altered byte)
    altered = bytearray(rec_path.read_bytes())
    altered[0] ^= 0x01
    rec_path.write_bytes(bytes(altered))
    res_drift = history.get(db, "owner-a", "med-1", tmp_path)
    assert "hash drift" in res_drift["error"]

    # Missing file
    rec_path.unlink()
    res_missing = history.get(db, "owner-a", "med-1", tmp_path)
    assert "missing" in res_missing["error"]

    # Symlink rejection
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    rec_path.symlink_to(outside)
    res_sym = history.get(db, "owner-a", "med-1", tmp_path)
    assert "symlink" in res_sym["error"]


def test_oversized_grown_and_truncated_artifacts_rejected(tmp_path: Path):
    history, _, _ = _load_pkg()
    db, rec_path, sha, size = _seed_history(tmp_path, history)

    # Oversized relative to configured max_bytes
    res_over = history.get(db, "owner-a", "med-1", tmp_path, max_bytes=max(1, size - 1))
    assert "exceeds size limit" in res_over["error"]

    # Grown file (manifest size smaller than on-disk file)
    orig = rec_path.read_bytes()
    rec_path.write_bytes(orig + b"extra-bytes")
    res_grown = history.get(db, "owner-a", "med-1", tmp_path)
    assert "size mismatch" in res_grown["error"]

    # Truncated file (manifest size larger than on-disk file)
    rec_path.write_bytes(orig[:-5])
    res_trunc = history.get(db, "owner-a", "med-1", tmp_path)
    assert "size mismatch" in res_trunc["error"]


def test_owner_and_batch_isolation_in_history_get(tmp_path: Path):
    history, _, _ = _load_pkg()
    db, rec_path, sha, size = _seed_history(tmp_path, history, owner="owner-a", batch_id="batch-z")
    # Insert an earlier-sorting batch for another owner with the same relative_path and different hash
    db.execute("INSERT INTO history_imports VALUES(?,?,?,datetime('now'))", ("batch-a", "owner-b", "{}"))
    db.execute("INSERT INTO history_files VALUES(?,?,?,?)", ("batch-a", "records/rec1.json", "0" * 64, 999))
    db.commit()

    # owner-a must resolve against batch-z (its own batch), not batch-a
    res = history.get(db, "owner-a", "med-1", tmp_path)
    assert "error" not in res and res["records"][0]["artifacts"][0]["sha256"] == sha

    # owner-b cannot fetch owner-a's record
    res_b = history.get(db, "owner-b", "med-1", tmp_path)
    assert res_b["error"] == "historical record not found"


def test_bounded_memory_streaming_hashes_full_large_file(tmp_path: Path):
    history, import_v1, retention = _load_pkg()
    v1_root = tmp_path / "v1-import"
    v1_root.mkdir(parents=True, exist_ok=True)
    rel = "evidence/large.bin"
    target = v1_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write a 4 MiB synthetic file whose final byte distinguishes it from any prefix
    chunk = b"A" * 65536
    digest = hashlib.sha256()
    total = 0
    with target.open("wb") as fh:
        for _ in range(63):
            fh.write(chunk)
            digest.update(chunk)
            total += len(chunk)
        tail = b"B" * 65535 + b"Z"
        fh.write(tail)
        digest.update(tail)
        total += len(tail)
    expected_sha = digest.hexdigest()

    tracemalloc.start()
    try:
        verified = history._safe_artifact(tmp_path, rel, expected_sha, expected_size=total)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert verified == target
    # Peak traced Python allocation must stay well below the 4 MiB file size
    assert peak < 1024 * 1024

    # Truncated prefix hash must be rejected
    prefix_sha = hashlib.sha256(chunk).hexdigest()
    with pytest.raises(ValueError, match="hash drift"):
        history._safe_artifact(tmp_path, rel, prefix_sha, expected_size=total)

    # import_v1._verify_file and retention.fingerprint also succeed and reject size limits
    assert import_v1._verify_file(v1_root, target, expected_sha, expected_size=total) is True
    assert import_v1._verify_file(v1_root, target, expected_sha, expected_size=total, max_bytes=1024) is False
    assert retention.fingerprint(target) == (total, expected_sha)
