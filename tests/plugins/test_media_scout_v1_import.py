import hashlib
import importlib.util
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

BASE = Path(__file__).parents[2]
IMPORTER = BASE / "plugins/media-scout/import_v1.py"
PLUGIN = BASE / "plugins/media-scout/__init__.py"


def load_importer():
    spec = importlib.util.spec_from_file_location("standalone_import_v1", IMPORTER)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def fixture(root):
    (root / "records").mkdir(parents=True)
    (root / "evidence").mkdir()
    evidence = b"Exact synthetic evidence\x00\xff\n"
    (root / "evidence" / "item.md").write_bytes(evidence)
    raw = {"schema_version":1,"media_id":"legacy_001","source_url":"https://youtube.com/watch?v=AbCdEf12345","original_source_url":"https://youtu.be/AbCdEf12345","media_type":"video","title":"Synthetic","summary":"Saved summary","topics":["test"],"entities":[],"creator_claims":[],"coverage":{"audio":"partial"},"extraction_status":"partial","review_status":"approved","evidence_status":"saved","evidence_path":"evidence/item.md","source_threads":["thread-x"],"review_tasks":["task-x"],"authorization":{"approved":True},"unknown_field":{"kept":1}}
    rec = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode()
    (root / "records" / "one.json").write_bytes(rec)
    (root / "reviews" ).mkdir(); (root / "reviews" / "decision.json").write_bytes(b'{"approval":"historical"}')
    return raw, rec, evidence


def test_dry_run_preserves_and_apply_is_idempotent(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); raw,rec,ev=fixture(src); dst=tmp_path/"dest"
    plan=mod.import_v1(src,dst,"owner",apply=False)
    assert plan["verified"] is False and not dst.exists()
    done=mod.import_v1(src,dst,"owner",apply=True)
    assert done["verified"] and done["records"]==1
    assert (dst/"v1-import/records/one.json").read_bytes()==rec
    assert (dst/"v1-import/evidence/item.md").read_bytes()==ev
    assert mod.import_v1(src,dst,"owner",apply=True)["already_imported"]
    db=sqlite3.connect(dst/"data.db")
    stored=json.loads(db.execute("SELECT record_json FROM history_records").fetchone()[0])
    assert stored==raw
    assert db.execute("SELECT name FROM sqlite_master WHERE name='receipts'").fetchone() is None
    assert db.execute("SELECT name FROM sqlite_master WHERE name='reviews'").fetchone() is None
    db.close()


def test_media_library_evidence_prefix_resolves_without_mutating_record(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); raw,_,ev=fixture(src)
    raw["evidence_path"]="media-library/evidence/item.md"
    rec=json.dumps(raw,ensure_ascii=False,separators=(",",":")).encode()
    (src/"records/one.json").write_bytes(rec)
    dst=tmp_path/"dst"
    result=mod.import_v1(src,dst,"owner",apply=True)
    assert result["verified"]
    assert (dst/"v1-import/records/one.json").read_bytes()==rec
    assert (dst/"v1-import/evidence/item.md").read_bytes()==ev
    db=sqlite3.connect(dst/"data.db")
    assert db.execute("SELECT relative_path FROM history_record_files").fetchone()==("evidence/item.md",)
    assert db.execute("SELECT missing_evidence_json FROM history_records").fetchone()==("[]",)
    db.close()


def test_import_additional_information_roots_and_root_files(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); fixture(src)
    expected={"wiki/index.md":b"wiki", "templates/reply.md":b"template", "receipts/old.json":b'{"historical":true}', "tests/case.txt":b"test", "policy.json":b'{"never_execute":true}'}
    for rel,data in expected.items():
        path=src/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    dst=tmp_path/"dst"; mod.import_v1(src,dst,"owner",apply=True)
    for rel,data in expected.items(): assert (dst/"v1-import"/rel).read_bytes()==data
    db=sqlite3.connect(dst/"data.db")
    assert db.execute("SELECT name FROM sqlite_master WHERE name='receipts'").fetchone() is None
    db.close()


def test_retry_rechecks_persisted_canonical_record_and_manifest(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); fixture(src); dst=tmp_path/"dst"
    mod.import_v1(src,dst,"owner",apply=True)
    db=sqlite3.connect(dst/"data.db")
    db.execute("UPDATE history_records SET record_json='{}'"); db.commit(); db.close()
    with pytest.raises(mod.ImportError,match="persisted import record mismatch"):
        mod.import_v1(src,dst,"owner",apply=True)


@pytest.mark.parametrize("bad", ["../outside.md", "/tmp/outside.md", "evidence/missing.md", "media-library/../evidence/item.md", "media-library/evidence\\\\item.md", "other/evidence/item.md"])
def test_rejects_bad_evidence_references_before_apply(tmp_path,bad):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); raw,_,_=fixture(src); raw["evidence_path"]=bad
    (src/"records/one.json").write_text(json.dumps(raw))
    with pytest.raises(mod.ImportError): mod.import_v1(src,tmp_path/"dest","owner",apply=True)
    assert not (tmp_path/"dest").exists()


def test_rejects_symlink_and_owner_mismatch(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); fixture(src); (src/"previews").symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(mod.ImportError): mod.plan_import(src,tmp_path/"dest","owner")
    src2=tmp_path/"src2"; src2.mkdir(); fixture(src2); dst=tmp_path/"dst"; dst.mkdir()
    db=sqlite3.connect(dst/"data.db"); db.execute("CREATE TABLE catalog_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)"); db.execute("INSERT INTO catalog_meta VALUES('owner_id','other')"); db.commit(); db.close()
    with pytest.raises(mod.ImportError): mod.import_v1(src2,dst,"owner",apply=True)


def test_changed_existing_media_id_conflicts_without_overwrite(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); raw,_,_=fixture(src); dst=tmp_path/"dst"
    mod.import_v1(src,dst,"owner",apply=True)
    src2=tmp_path/"src2"; src2.mkdir(); fixture(src2)
    changed=json.loads((src2/"records/one.json").read_text()); changed["summary"]="changed"; (src2/"records/renamed.json").write_text(json.dumps(changed)); (src2/"records/one.json").unlink()
    with pytest.raises(mod.ImportError,match="record conflict"):
        mod.import_v1(src2,dst,"owner",apply=True)
    assert (dst/"v1-import/records/one.json").exists()


def test_search_get_after_source_removed_and_artifact_drift(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); fixture(src); dst=tmp_path/"dst"
    mod.import_v1(src,dst,"owner",apply=True)
    import shutil; shutil.rmtree(src)
    spec=importlib.util.spec_from_file_location("history_mod", BASE/"plugins/media-scout/history.py")
    hist=importlib.util.module_from_spec(spec)
    # history module imports the plugin's package-relative source parser.
    pkg=types.ModuleType("plugins"); pkg.__path__=[str(BASE/"plugins")]; sys.modules.setdefault("plugins",pkg)
    # Load as a package module using an isolated package alias.
    spec=importlib.util.spec_from_file_location("plugins.media_scout.history", BASE/"plugins/media-scout/history.py", submodule_search_locations=[])
    hist=importlib.util.module_from_spec(spec); sys.modules[spec.name]=hist
    # the package name has a hyphen on disk; source is imported under an explicit alias
    srcspec=importlib.util.spec_from_file_location("plugins.media_scout.sources", BASE/"plugins/media-scout/sources.py")
    sources=importlib.util.module_from_spec(srcspec); sys.modules[srcspec.name]=sources; srcspec.loader.exec_module(sources)
    spec.loader.exec_module(hist)
    db=sqlite3.connect(dst/"data.db")
    assert hist.search(db,"owner","legacy_001")["results"][0]["summary"]=="Saved summary"
    assert hist.search(db,"owner","https://www.youtube.com/watch?v=AbCdEf12345")["count"]==1
    assert hist.get(db,"owner","legacy_001",dst)["records"][0]["record"]["unknown_field"]=={"kept":1}
    (dst/"v1-import/evidence/item.md").write_text("changed")
    assert "hash drift" in hist.get(db,"owner","legacy_001",dst)["error"]
    db.close()


def test_unsupported_source_exact_url_and_bounded_search(tmp_path):
    mod=load_importer(); src=tmp_path/"src"; src.mkdir(); (src/"records").mkdir()
    for i in range(12):
        record={"media_id":f"unsupported_{i}","source_url":"https://github.com/org/repo/issues/7","title":f"T{i}","summary":"S"*1400,"coverage":"blocked","raw_unknown":{"n":i}}
        (src/"records"/f"{i:02}.json").write_bytes(json.dumps(record).encode())
    dst=tmp_path/"dst"; mod.import_v1(src,dst,"owner",apply=True)
    pkg=types.ModuleType("plugins"); pkg.__path__=[str(BASE/"plugins")]; sys.modules.setdefault("plugins",pkg)
    sub=types.ModuleType("plugins.media_scout"); sub.__path__=[str(BASE/"plugins/media-scout")]; sys.modules.setdefault("plugins.media_scout",sub)
    srcspec=importlib.util.spec_from_file_location("plugins.media_scout.sources",BASE/"plugins/media-scout/sources.py")
    sources=importlib.util.module_from_spec(srcspec); sys.modules[srcspec.name]=sources; srcspec.loader.exec_module(sources)
    spec=importlib.util.spec_from_file_location("plugins.media_scout.history",BASE/"plugins/media-scout/history.py")
    hist=importlib.util.module_from_spec(spec); sys.modules[spec.name]=hist; spec.loader.exec_module(hist)
    db=sqlite3.connect(dst/"data.db")
    result=hist.search(db,"owner","https://github.com/org/repo/issues/7",99)
    assert result["count"]==12 and result["has_more"] and len(result["results"])==10 and len(result["results"][0]["summary"])<=1200
    file_result=hist.search_files(db,"owner","records",99)
    assert file_result["count"]==12 and file_result["has_more"] and len(file_result["results"])==10
    detail=hist.get(db,"owner","https://github.com/org/repo/issues/7",dst)
    assert detail["count"]==12 and detail["has_more"] and len(detail["records"])==10 and detail["records"][0]["record"]["raw_unknown"]
    db.close()


def test_registered_tool_owner_check_and_history_actions(monkeypatch,tmp_path):
    storage=types.ModuleType("plugins.plugin_storage"); data=tmp_path/"data"; data.mkdir()
    storage.plugin_data_dir=lambda name: data/name
    def plugin_db(name):
        (data/name).mkdir(exist_ok=True)
        return sqlite3.connect(data/name/"data.db")
    storage.plugin_db=plugin_db
    monkeypatch.setitem(sys.modules,"plugins.plugin_storage",storage)
    pkg=types.ModuleType("media_scout_pkg"); pkg.__path__=[str(BASE/"plugins/media-scout")]
    spec=importlib.util.spec_from_file_location("media_scout_pkg",PLUGIN,submodule_search_locations=pkg.__path__)
    plugin=importlib.util.module_from_spec(spec); sys.modules[spec.name]=plugin; spec.loader.exec_module(plugin)
    session=types.ModuleType("gateway.session_context"); session.get_session_env=lambda key,default="": "owner" if key=="HERMES_SESSION_USER_ID" else default
    monkeypatch.setitem(sys.modules,"gateway.session_context",session)
    class Ctx:
        settings={"owner_id":"owner","guild_id":"guild","parent_channel_id":"parent"}
        def get_config(self,k,d=None): return self.settings.get(k,d)
        def register_skill(self,*a): pass
        def register_hook(self,*a): pass
        def register_command(self,*a,**k): pass
        def register_tool(self,*,name,handler,schema,**kw): self.handler=handler; self.schema=schema
    ctx=Ctx(); plugin.register(ctx)
    assert "search" in ctx.schema["parameters"]["properties"]["action"]["enum"]
    import asyncio
    src=tmp_path/"legacy"; src.mkdir(); fixture(src)
    importer=load_importer(); importer.import_v1(src,data/"media-scout","owner",apply=True)
    result=json.loads(asyncio.run(ctx.handler({"action":"search","query":"https://youtu.be/AbCdEf12345"})))
    assert result["history"]["count"]==1
    discovered=json.loads(asyncio.run(ctx.handler({"action":"history_files","query":"decision","limit":10})))
    assert discovered["count"]==1 and discovered["results"][0]["path"]=="reviews/decision.json"
    fetched=json.loads(asyncio.run(ctx.handler({"action":"history_artifact","path":"reviews/decision.json"})))
    assert fetched["artifact"]["historical_only"]
    assert json.loads(asyncio.run(ctx.handler({"action":"history_get","query":"legacy_001"}))) ["records"][0]["historical_only"]
    # Count the full native result set, not the bounded fetch window.
    from contextlib import closing
    with closing(sqlite3.connect(data/"media-scout/data.db")) as db:
        def admit(index, url):
            thread=f"source-thread-{index}"
            return plugin.capture_receipt(db,f"message-{index}",{"platform":"discord","user_id":"owner","scope_id":"guild","parent_chat_id":"parent","chat_id":thread,"thread_id":thread,"session_key":"key:"+thread},url)
        for index in range(12):
            captured=admit(index,f"https://youtube.com/watch?v=budget{index:05d}")
            db.execute("UPDATE media SET summary='Budget shared summary',coverage='partial' WHERE media_id=?",(captured["media_id"],)); db.commit()
        linked=admit(20,"https://youtu.be/AbCdEf12345")
        admit(21,"https://youtube.com/watch?v=AbCdEf12345")
    bounded=json.loads(asyncio.run(ctx.handler({"action":"search","query":"Budget shared","limit":3})))
    assert bounded["native_count"]==12 and bounded["native_has_more"]
    assert len(bounded["native_matches"])==3
    item=json.loads(asyncio.run(ctx.handler({"action":"get","media_id":linked["media_id"]})))
    assert len(item["related_history"])==1
    session.get_session_env=lambda key,default="": "stranger" if key=="HERMES_SESSION_USER_ID" else default
    assert "owner identity required" in json.loads(asyncio.run(ctx.handler({"action":"search","query":"legacy_001"}))) ["error"]
