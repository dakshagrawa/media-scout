"""Bounded, owner-scoped retrieval for imported v1 informational history.

Artifact verification policy (#12):
- Entry points: history._safe_artifact (used by history.get and history.get_orphan),
  import_v1._verify_file, import_v1._db_readonly, and retention.fingerprint.
- Streaming: all verification entry points stream SHA-256 in 64 KiB chunks.
- Limits: DEFAULT_MAX_ARTIFACT_BYTES (16 MiB) in history.py, MAX_FILE in import_v1.py,
  and MAX_BYTES (50 MiB) in retention.py; oversized, grown, or truncated files fail closed.
- Race boundary: path components are checked for symlinks before opening with O_NOFOLLOW
  and verifying fstat(fd) S_ISREG, size, and post-read byte count. On POSIX, a concurrent
  parent-directory swap before os.open remains outside this single-process threat model.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path, PurePosixPath

from .sources import parse_source_url

CHUNK_SIZE = 65536
DEFAULT_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024


def initialize_history(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS history_imports(batch_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,manifest_json TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS history_records(record_key TEXT PRIMARY KEY,batch_id TEXT NOT NULL,owner_id TEXT NOT NULL,media_id TEXT NOT NULL,source_url TEXT NOT NULL,original_source_url TEXT NOT NULL,record_json TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,record_json_sha256 TEXT NOT NULL DEFAULT '',identity_key TEXT NOT NULL DEFAULT '',search_text TEXT NOT NULL DEFAULT '',missing_evidence_json TEXT NOT NULL DEFAULT '[]',provenance_json TEXT NOT NULL);
    CREATE UNIQUE INDEX IF NOT EXISTS history_records_owner_media ON history_records(owner_id,media_id);
    CREATE INDEX IF NOT EXISTS history_records_identity ON history_records(owner_id,identity_key);
    CREATE INDEX IF NOT EXISTS history_records_keywords ON history_records(owner_id,search_text);
    CREATE TABLE IF NOT EXISTS history_files(batch_id TEXT NOT NULL,relative_path TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,PRIMARY KEY(batch_id,relative_path));
    CREATE TABLE IF NOT EXISTS history_record_files(record_key TEXT NOT NULL,relative_path TEXT NOT NULL,PRIMARY KEY(record_key,relative_path));
    """)
    cols={r[1] for r in db.execute("PRAGMA table_info(history_records)")}
    for name, decl in (("record_json_sha256", "TEXT NOT NULL DEFAULT ''"),("identity_key", "TEXT NOT NULL DEFAULT ''"),("search_text", "TEXT NOT NULL DEFAULT ''"),("missing_evidence_json", "TEXT NOT NULL DEFAULT '[]'")):
        if name not in cols: db.execute(f"ALTER TABLE history_records ADD COLUMN {name} {decl}")


def _key(url):
    parsed=parse_source_url(url) if isinstance(url,str) else None
    return f"{parsed.platform}:{parsed.identity_key}" if parsed else ""


def _matches(db, owner, query):
    if not isinstance(query,str) or not query or len(query)>2048: return [],0
    ident=_key(query)
    if ident:
        where="identity_key=?"; args=(owner,ident)
    else:
        q=query.casefold()
        if len(q)>=24 and q.startswith(("http://","https://")):
            where="source_url=? OR original_source_url=?"; args=(owner,query,query)
        else:
            where="media_id=? OR instr(search_text,?)>0"; args=(owner,query,q)
    select="record_key,media_id,source_url,original_source_url,record_json,filename,sha256,record_json_sha256,provenance_json"
    rows=db.execute(f"SELECT {select} FROM history_records WHERE owner_id=? AND ({where}) ORDER BY rowid LIMIT 11",args).fetchall()
    count=db.execute(f"SELECT count(*) FROM history_records WHERE owner_id=? AND ({where})",args).fetchone()[0]
    return rows,count


def search(db, owner, query, limit=5) -> dict:
    limit=max(1,min(int(limit or 5),10)); rows,total=_matches(db,owner,query); out=[]
    for key,media,url,original,raw,filename,digest,json_digest,provenance in rows[:limit]:
        if not json_digest or hashlib.sha256(raw.encode()).hexdigest()!=json_digest: return {"error":"imported record hash drift detected"}
        item=json.loads(raw)
        out.append({"media_id":media,"source_url":url,"title":str(item.get("title",""))[:240],"summary":str(item.get("summary",""))[:1200],"coverage":item.get("coverage"),"extraction_status":item.get("extraction_status"),"review_status":item.get("review_status"),"record_sha256":digest,"record_key":key})
    return {"count":total,"results":out,"has_more":total>len(out),"historical_only":True}


def _safe_artifact(root, rel, expected, expected_size=None, *, max_bytes=DEFAULT_MAX_ARTIFACT_BYTES):
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise ValueError("unsafe imported path")
    pp=PurePosixPath(rel)
    if pp.is_absolute() or any(part in {".", ".."} for part in pp.parts):
        raise ValueError("unsafe imported path")
    if max_bytes <= 0:
        raise ValueError("invalid artifact size limit")
    if expected_size is not None and (type(expected_size) is not int or expected_size < 0):
        raise ValueError("invalid manifest artifact size")
    base=Path(root).expanduser(); v1_root=base/"v1-import"; path=v1_root/rel
    probe=Path(path.anchor)
    for part in path.parts[1:]:
        probe/=part
        if probe.is_symlink(): raise ValueError("symlink in imported artifact path")
    try:
        if not path.resolve(strict=True).is_relative_to(v1_root.resolve(strict=True)):
            raise ValueError("imported artifact escaped root")
    except FileNotFoundError as exc:
        raise ValueError("imported artifact missing") from exc
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError as exc:
        raise ValueError("imported artifact missing") from exc
    except OSError as exc:
        raise ValueError("symlink or unreadable imported artifact") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("imported artifact is not a regular file")
        if st.st_size > max_bytes:
            raise ValueError("imported artifact exceeds size limit")
        if expected_size is not None and st.st_size != expected_size:
            raise ValueError("imported artifact size mismatch (hash drift detected)")
        digest = hashlib.sha256()
        total = 0
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("imported artifact exceeds size limit")
                if expected_size is not None and total > expected_size:
                    raise ValueError("imported artifact size mismatch (hash drift detected)")
                digest.update(chunk)
        if expected_size is not None and total != expected_size:
            raise ValueError("imported artifact size mismatch (hash drift detected)")
        if total != st.st_size:
            raise ValueError("imported artifact changed while reading")
        if digest.hexdigest() != expected:
            raise ValueError("imported artifact hash drift detected")
        return path
    finally:
        if fd >= 0:
            os.close(fd)


def get(db, owner, query, data_root, *, max_bytes=DEFAULT_MAX_ARTIFACT_BYTES):
    rows,total=_matches(db,owner,query)
    if not rows:return {"error":"historical record not found"}
    out=[]
    for key,media,url,original,raw,filename,digest,json_digest,provenance in rows[:10]:
        if not json_digest or hashlib.sha256(raw.encode()).hexdigest()!=json_digest:return {"error":"imported record hash drift detected"}
        record=json.loads(raw)
        batch = db.execute("SELECT batch_id FROM history_records WHERE record_key=? AND owner_id=?", (key, owner)).fetchone()
        if not batch:return {"error":"historical record batch not found"}
        batch_id = batch[0]
        linked={r[0] for r in db.execute("SELECT relative_path FROM history_record_files WHERE record_key=?",(key,))}
        linked.add(filename)
        missing=json.loads(db.execute("SELECT missing_evidence_json FROM history_records WHERE record_key=?",(key,)).fetchone()[0])
        artifacts=[]
        for rel in sorted(linked):
            row=db.execute("SELECT f.sha256,f.size FROM history_files f JOIN history_imports i USING(batch_id) WHERE f.batch_id=? AND i.owner_id=? AND f.relative_path=?",(batch_id,owner,rel)).fetchone()
            if not row:return {"error":"linked imported artifact missing from manifest","path":rel}
            try: path=_safe_artifact(data_root,rel,row[0],expected_size=row[1],max_bytes=max_bytes)
            except (ValueError,OSError) as exc: return {"error":str(exc),"path":rel}
            artifacts.append({"path":str(path),"sha256":row[0],"size":row[1]})
        derivatives = {"count": 0, "has_more": False, "results": []}
        if isinstance(media, str) and media not in {".", ".."} and "/" not in media and "\\" not in media and not any(ord(char) < 32 or ord(char) == 127 for char in media):
            prefix = f"evidence/derived-cache/cache/{media}/"
            # Range lookup uses the manifest primary-key index; only the record's
            # owner-bound import batch is eligible, never a neighboring media ID.
            args = (batch_id, owner, prefix, prefix + "\U0010ffff")
            where = ("f.batch_id=? AND i.owner_id=? AND f.relative_path>=? AND f.relative_path<? "
                     "AND instr(f.relative_path, char(92))=0 AND instr(f.relative_path, '//')=0 "
                     "AND instr('/'||f.relative_path||'/', '/../')=0 AND instr('/'||f.relative_path||'/', '/./')=0 "
                     "AND substr(f.relative_path,-1)<>'/'")
            total_files = db.execute(f"SELECT count(*) FROM history_files f JOIN history_imports i USING(batch_id) WHERE {where}", args).fetchone()[0]
            files = db.execute(f"SELECT f.relative_path,f.sha256,f.size FROM history_files f JOIN history_imports i USING(batch_id) WHERE {where} ORDER BY f.relative_path LIMIT 10", args).fetchall()
            derivatives = {"count": total_files, "has_more": total_files > len(files), "results": [{"path": p, "sha256": h, "size": s, "role": "retained derivative, not new inspection"} for p,h,s in files]}
        out.append({"record":record,"record_sha256":digest,"filename":filename,"provenance":json.loads(provenance),"artifacts":artifacts,"related_derivatives":derivatives,"missing_references":missing,"historical_only":True})
    return {"count":total,"has_more":total>len(out),"records":out,"historical_only":True}


def get_orphan(db, owner, relative_path, data_root, *, max_bytes=DEFAULT_MAX_ARTIFACT_BYTES):
    row=db.execute("SELECT f.sha256,f.size FROM history_files f JOIN history_imports i USING(batch_id) WHERE i.owner_id=? AND f.relative_path=?",(owner,relative_path)).fetchone()
    if not row:return {"error":"historical artifact not found"}
    try:path=_safe_artifact(data_root,relative_path,row[0],expected_size=row[1],max_bytes=max_bytes)
    except (ValueError,OSError) as exc:return {"error":str(exc)}
    return {"artifact":{"path":str(path),"sha256":row[0],"size":row[1],"historical_only":True}}


def search_files(db, owner, query="", limit=10):
    limit=max(1,min(int(limit or 10),10))
    if not isinstance(query,str) or len(query)>2048:return {"count":0,"results":[],"has_more":False}
    where="i.owner_id=? AND (?='' OR instr(lower(f.relative_path),?)>0)"
    args=(owner,query,query.casefold())
    total=db.execute(f"SELECT count(*) FROM history_files f JOIN history_imports i USING(batch_id) WHERE {where}",args).fetchone()[0]
    rows=db.execute(f"SELECT f.relative_path,f.sha256,f.size FROM history_files f JOIN history_imports i USING(batch_id) WHERE {where} ORDER BY f.relative_path LIMIT ?",(*args,limit)).fetchall()
    return {"count":total,"has_more":total>len(rows),"results":[{"path":r[0],"sha256":r[1],"size":r[2],"historical_only":True} for r in rows]}
