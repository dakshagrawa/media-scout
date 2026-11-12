"""Standalone stdlib-only, explicit one-time Media Scout v1 information import."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import quote

MAX_FILE = 8 * 1024 * 1024
MAX_BATCH = 128 * 1024 * 1024
MAX_FILES = 10_000
DIRS = ("records", "evidence", "reviews", "proposals", "previews", "wiki", "templates", "receipts", "tests")
ROOT_FILES = ("policy.json", "recovery-policy.json", "review-policy.md", "recovery-report.md", "cleanup-report.md")
_MEDIA_PARSER = None


class ImportError(ValueError):
    pass


def _reject_symlink_components(path):
    absolute = Path(os.path.abspath(Path(path).expanduser()))
    probe = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        probe /= part
        if probe.is_symlink():
            raise ImportError("symlink path components are not permitted")


def _root(path, must_exist):
    p = Path(path).expanduser()
    _reject_symlink_components(p)
    if p.is_symlink():
        raise ImportError("symlink roots are not permitted")
    if must_exist and not p.is_dir():
        raise ImportError("source root must be an existing directory")
    p = p.resolve(strict=must_exist)
    if p == Path("/") or p == Path.home():
        raise ImportError("unsafe root")
    return p


def _safe_file(root, path):
    st = path.lstat()
    if not path.is_file() or path.is_symlink() or not stat.S_ISREG(st.st_mode):
        raise ImportError(f"unsafe or nonregular source entry: {path.name}")
    resolved = path.resolve(strict=True)
    if root not in resolved.parents:
        raise ImportError("source entry escaped root")
    rel = path.relative_to(root).as_posix()
    pp = PurePosixPath(rel)
    if pp.is_absolute() or ".." in pp.parts or "\\" in rel:
        raise ImportError("unsafe relative path")
    if st.st_size > MAX_FILE:
        raise ImportError(f"file exceeds {MAX_FILE} bytes")
    data = path.read_bytes()
    if len(data) != st.st_size:
        raise ImportError("source file changed while reading")
    return rel, data


def _identity_key(url):
    global _MEDIA_PARSER
    if not isinstance(url, str):
        return ""
    if _MEDIA_PARSER is None:
        path = Path(__file__).with_name("sources.py")
        spec = importlib.util.spec_from_file_location("_media_scout_import_sources", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _MEDIA_PARSER = module.parse_source_url
    parsed = _MEDIA_PARSER(url)
    return f"{parsed.platform}:{parsed.identity_key}" if parsed else ""


def _keywords(record):
    words = [record.get("title", ""), record.get("summary", "")]
    for field in ("topics", "entities", "retained_knowledge", "creator_claims"):
        value = record.get(field, [])
        if isinstance(value, list):
            words.extend(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, sort_keys=True) for x in value)
    return " ".join(str(x) for x in words if x).casefold()[:12000]


def _walk_refs(obj, paths, refs):
    if isinstance(obj, dict):
        for value in obj.values(): _walk_refs(value, paths, refs)
    elif isinstance(obj, list):
        for value in obj: _walk_refs(value, paths, refs)
    elif isinstance(obj, str):
        resolved = _resolve_evidence_ref(obj)
        if resolved and resolved in paths: refs.add(resolved)


def _resolve_evidence_ref(value):
    if not isinstance(value, str) or "\\" in value: return None
    prefix = "media-library/"
    candidate = value[len(prefix):] if value.startswith(prefix) else value
    pp = PurePosixPath(candidate)
    if pp.is_absolute() or ".." in pp.parts or not candidate.startswith("evidence/"): return None
    return candidate


def _associated(record, record_filename, files):
    paths = {f["relative_path"] for f in files}
    refs = set()
    _walk_refs(record, paths, refs)
    media_id = record["media_id"]
    for rel in paths:
        if rel.startswith("records/"):
            continue
        stem = Path(rel).stem
        if stem == media_id or (stem.startswith(media_id) and stem[len(media_id):len(media_id)+1] in "._-"):
            refs.add(rel)
    return sorted(refs)


def _db_readonly(dbpath, owner_id, records, files, destination):
    if not dbpath.exists():
        return {"records": [], "files": []}
    _reject_symlink_components(dbpath)
    if dbpath.is_symlink() or not dbpath.is_file():
        raise ImportError("unsafe destination database")
    uri = "file:" + quote(str(dbpath)) + "?mode=ro"
    try:
        db = sqlite3.connect(uri, uri=True, timeout=5)
    except sqlite3.Error as exc:
        raise ImportError("destination database is not readable") from exc
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "catalog_meta" in tables:
            owner = db.execute("SELECT value FROM catalog_meta WHERE key='owner_id'").fetchone()
            if owner and owner[0] != owner_id:
                raise ImportError("catalog owner mismatch")
        existing_records = []
        if "history_records" in tables:
            cols = {r[1] for r in db.execute("PRAGMA table_info(history_records)")}
            if {"owner_id", "media_id", "sha256"} <= cols:
                existing_records = db.execute("SELECT owner_id,media_id,sha256 FROM history_records").fetchall()
        existing_files = []
        if "history_files" in tables:
            existing_files = db.execute("SELECT relative_path,sha256 FROM history_files").fetchall()
        old_records = {(o, m): h for o, m, h in existing_records}
        for rec in records:
            old = old_records.get((owner_id, rec["record"]["media_id"]))
            if old and old != rec["sha256"]:
                raise ImportError(f"record conflict for media_id {rec['record']['media_id']}")
        old_files = dict(existing_files)
        for f in files:
            prior = old_files.get(f["relative_path"])
            dest = destination / "v1-import" / f["relative_path"]
            if prior and prior != f["sha256"]:
                raise ImportError(f"destination file conflict: {f['relative_path']}")
            if dest.exists() and (dest.is_symlink() or not dest.is_file() or hashlib.sha256(dest.read_bytes()).hexdigest() != f["sha256"]):
                raise ImportError(f"destination file conflict: {f['relative_path']}")
        return {"records": existing_records, "files": existing_files}
    finally:
        db.close()


def plan_import(source_root, destination_root, owner_id, *, allow_missing_evidence=False):
    if not isinstance(owner_id, str) or not owner_id.strip() or len(owner_id) > 128:
        raise ImportError("explicit owner_id required")
    src = _root(source_root, True)
    dst = Path(destination_root).expanduser()
    _reject_symlink_components(dst)
    dst_resolved = dst.resolve(strict=False)
    if src == dst_resolved or src in dst_resolved.parents or dst_resolved in src.parents:
        raise ImportError("source and destination roots must be separate")
    files, total = [], 0
    for dirname in DIRS:
        base = src / dirname
        if base.is_symlink(): raise ImportError("symlink source directory")
        if not base.exists(): continue
        for path in sorted(base.rglob("*")):
            if path.is_symlink(): raise ImportError("symlink encountered in source tree")
            if path.is_dir(): continue
            rel, data = _safe_file(src, path)
            total += len(data)
            if total > MAX_BATCH: raise ImportError("batch exceeds size limit")
            files.append({"relative_path": rel, "data": data, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
            if len(files) > MAX_FILES: raise ImportError("batch exceeds file-count limit")
    for filename in ROOT_FILES:
        path = src / filename
        if path.exists() or path.is_symlink():
            if path.is_symlink(): raise ImportError("symlink root information file")
            rel, data = _safe_file(src, path)
            total += len(data)
            if total > MAX_BATCH: raise ImportError("batch exceeds size limit")
            files.append({"relative_path": rel, "data": data, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
            if len(files) > MAX_FILES: raise ImportError("batch exceeds file-count limit")
    filemap = {f["relative_path"]: f for f in files}
    records = []
    seen_ids = set()
    statuses = []
    for f in files:
        if not f["relative_path"].startswith("records/") or not f["relative_path"].endswith(".json"): continue
        try: record = json.loads(f["data"])
        except (ValueError, UnicodeError) as exc: raise ImportError(f"invalid record JSON: {f['relative_path']}") from exc
        if not isinstance(record, dict) or not isinstance(record.get("media_id"), str) or not record["media_id"]:
            raise ImportError(f"record lacks media_id: {f['relative_path']}")
        media_id = record["media_id"]
        if media_id in seen_ids: raise ImportError(f"duplicate media_id in source batch: {media_id}")
        seen_ids.add(media_id)
        missing = []
        evidence_ref = record.get("evidence_path")
        if evidence_ref:
            if not isinstance(evidence_ref, str): raise ImportError(f"unsafe evidence reference: {f['relative_path']}")
            normalized_ref = _resolve_evidence_ref(evidence_ref)
            if normalized_ref is None:
                raise ImportError(f"unsafe evidence reference: {f['relative_path']}")
            if normalized_ref not in filemap:
                missing.append(normalized_ref)
                if not allow_missing_evidence: raise ImportError(f"missing evidence reference: {f['relative_path']} -> {evidence_ref}")
        for field in ("source_threads", "review_tasks"):
            if record.get(field) is not None and not isinstance(record[field], list): raise ImportError(f"invalid {field} reference list")
        associated = _associated(record, f["relative_path"], files)
        records.append({"filename": f["relative_path"], "record": record, "sha256": f["sha256"], "associated_files": associated, "missing_references": missing})
        statuses.append({"media_id": media_id, "source_filename": f["relative_path"], "evidence_status": "missing" if missing else "present_or_unreferenced", "missing_references": missing})
    batch = hashlib.sha256((owner_id + "\n" + "\n".join(f["relative_path"] + ":" + f["sha256"] for f in files)).encode()).hexdigest()
    manifest = {"batch_id": batch, "owner_id": owner_id, "files": [{k:f[k] for k in ("relative_path","sha256","size")} for f in files], "records": len(records), "file_count": len(files), "bytes": total, "missing_references": [x for s in statuses for x in s["missing_references"]], "record_statuses": statuses, "conflicts": [], "verified": False}
    _db_readonly(dst / "data.db", owner_id, records, files, dst)
    return src, dst, files, records, manifest


def _mkdir_private(path):
    _reject_symlink_components(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir(): raise ImportError("unsafe destination directory")
    os.chmod(path, 0o700)


def _write_private(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as out: out.write(data)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)


def _schema(db):
    for statement in (
        "CREATE TABLE IF NOT EXISTS catalog_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_imports(batch_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,manifest_json TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS history_records(record_key TEXT PRIMARY KEY,batch_id TEXT NOT NULL,owner_id TEXT NOT NULL,media_id TEXT NOT NULL,source_url TEXT NOT NULL,original_source_url TEXT NOT NULL,record_json TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,record_json_sha256 TEXT NOT NULL,identity_key TEXT NOT NULL,search_text TEXT NOT NULL,missing_evidence_json TEXT NOT NULL,provenance_json TEXT NOT NULL)",
        "CREATE UNIQUE INDEX IF NOT EXISTS history_records_owner_media ON history_records(owner_id,media_id)",
        "CREATE INDEX IF NOT EXISTS history_records_identity ON history_records(owner_id,identity_key)",
        "CREATE INDEX IF NOT EXISTS history_records_keywords ON history_records(owner_id,search_text)",
        "CREATE TABLE IF NOT EXISTS history_files(batch_id TEXT NOT NULL,relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,PRIMARY KEY(batch_id,relative_path))",
        "CREATE TABLE IF NOT EXISTS history_record_files(record_key TEXT NOT NULL,relative_path TEXT NOT NULL,PRIMARY KEY(record_key,relative_path))",
    ):
        db.execute(statement)


def import_v1(source_root, destination_root, owner_id, *, apply=False, allow_missing_evidence=False):
    src, dst, files, records, manifest = plan_import(source_root, destination_root, owner_id, allow_missing_evidence=allow_missing_evidence)
    if not apply: return manifest
    _mkdir_private(dst)
    dbpath = dst / "data.db"
    _reject_symlink_components(dbpath)
    if dbpath.is_symlink(): raise ImportError("unsafe destination database")
    db = sqlite3.connect(dbpath, timeout=10)
    moved = []
    stage = dst / ".v1-import-stage"
    try:
        db.execute("BEGIN IMMEDIATE")
        _schema(db)
        owner = db.execute("SELECT value FROM catalog_meta WHERE key='owner_id'").fetchone()
        if owner and owner[0] != owner_id: raise ImportError("catalog owner mismatch")
        prior = db.execute("SELECT owner_id,manifest_json FROM history_imports WHERE batch_id=?", (manifest["batch_id"],)).fetchone()
        if prior:
            if prior[0] != owner_id: raise ImportError("import batch owner mismatch")
            stored = json.loads(prior[1])
            expected_manifest = dict(manifest, verified=True)
            if stored != expected_manifest: raise ImportError("persisted import manifest mismatch")
            stored_files = db.execute("SELECT relative_path,sha256,size FROM history_files WHERE batch_id=? ORDER BY relative_path", (manifest["batch_id"],)).fetchall()
            expected_files = sorted((f["relative_path"], f["sha256"], f["size"]) for f in files)
            if stored_files != expected_files: raise ImportError("persisted import file inventory mismatch")
            for f in files:
                rows = db.execute("SELECT sha256 FROM history_files WHERE batch_id=? AND relative_path=?", (manifest["batch_id"],f["relative_path"])).fetchone()
                dest = dst / "v1-import" / f["relative_path"]
                if not rows or rows[0] != f["sha256"] or not _verify_file(dst, dest, f["sha256"]): raise ImportError("persisted import artifact/manifest mismatch")
            for rec in records:
                row = db.execute("SELECT sha256,record_json,record_json_sha256 FROM history_records WHERE owner_id=? AND media_id=?", (owner_id,rec["record"]["media_id"])).fetchone()
                expected_json = json.dumps(rec["record"], ensure_ascii=False, sort_keys=True)
                if not row or row[0] != rec["sha256"] or row[1] != expected_json or not row[2] or hashlib.sha256(row[1].encode()).hexdigest() != row[2]: raise ImportError("persisted import record mismatch")
            db.commit(); manifest["verified"] = True; manifest["already_imported"] = True; return manifest
        if owner and owner[0] != owner_id: raise ImportError("catalog owner mismatch")
        for rec in records:
            old = db.execute("SELECT sha256 FROM history_records WHERE owner_id=? AND media_id=?", (owner_id,rec["record"]["media_id"])).fetchone()
            if old: raise ImportError(f"duplicate existing media_id: {rec['record']['media_id']}")
        for f in files:
            old = db.execute("SELECT sha256 FROM history_files WHERE relative_path=?",(f["relative_path"],)).fetchone()
            if old and old[0] != f["sha256"]: raise ImportError(f"destination file conflict: {f['relative_path']}")
            dest = dst / "v1-import" / f["relative_path"]
            _reject_symlink_components(dest)
            if dest.exists() and (dest.is_symlink() or not dest.is_file() or hashlib.sha256(dest.read_bytes()).hexdigest()!=f["sha256"]): raise ImportError(f"destination file conflict: {f['relative_path']}")
        if stage.exists():
            if stage.is_symlink(): raise ImportError("unsafe staging directory")
            shutil.rmtree(stage)
        _mkdir_private(stage)
        for f in files:
            target=stage/f["relative_path"]; _mkdir_private(target.parent); _write_private(target,f["data"])
        for f in files:
            staged=stage/f["relative_path"]; dest=dst/"v1-import"/f["relative_path"]
            _mkdir_private(dest.parent)
            if not dest.exists(): os.replace(staged,dest); moved.append(dest)
        for f in files:
            dest=dst/"v1-import"/f["relative_path"]
            if not _verify_file(dst,dest,f["sha256"]): raise ImportError(f"copied file verification failed: {f['relative_path']}")
            db.execute("INSERT INTO history_files VALUES(?,?,?,?)",(manifest["batch_id"],f["relative_path"],f["sha256"],f["size"]))
        if not owner: db.execute("INSERT INTO catalog_meta VALUES('owner_id',?)",(owner_id,))
        for rec in records:
            record=rec["record"]; record_json=json.dumps(record,ensure_ascii=False,sort_keys=True); record_json_hash=hashlib.sha256(record_json.encode()).hexdigest()
            key=hashlib.sha256((owner_id+"\0"+record["media_id"]).encode()).hexdigest()
            db.execute("INSERT INTO history_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(key,manifest["batch_id"],owner_id,record["media_id"],str(record.get("source_url","")),str(record.get("original_source_url",record.get("source_url",""))),record_json,rec["filename"],rec["sha256"],record_json_hash,_identity_key(record.get("source_url","")),_keywords(record),json.dumps(rec["missing_references"]),json.dumps({"source_filename":rec["filename"],"source_sha256":rec["sha256"],"associated_artifacts":rec["associated_files"]},sort_keys=True)))
            for rel in rec["associated_files"]: db.execute("INSERT INTO history_record_files VALUES(?,?)",(key,rel))
        manifest["verified"] = True
        db.execute("INSERT INTO history_imports VALUES(?,?,?,datetime('now'))",(manifest["batch_id"],owner_id,json.dumps(manifest,sort_keys=True)))
        db.commit()
        shutil.rmtree(stage,ignore_errors=True)
        return manifest
    except Exception:
        db.rollback()
        for path in reversed(moved): path.unlink(missing_ok=True)
        shutil.rmtree(stage,ignore_errors=True)
        raise
    finally: db.close()


def _verify_file(root, path, expected):
    _reject_symlink_components(path)
    return root in path.resolve(strict=False).parents and path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==expected


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True); parser.add_argument("--destination",required=True); parser.add_argument("--owner",required=True)
    parser.add_argument("--apply",action="store_true",help="apply import; default prints dry-run manifest")
    parser.add_argument("--allow-missing-evidence",action="store_true",help="retain records with missing referenced evidence and mark each gap")
    args=parser.parse_args(argv)
    try: result=import_v1(args.source,args.destination,args.owner,apply=args.apply,allow_missing_evidence=args.allow_missing_evidence)
    except (ImportError,OSError,sqlite3.Error) as exc: parser.error(str(exc))
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))


if __name__=="__main__": main()
