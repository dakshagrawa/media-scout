"""Portable package contracts for the native Media Scout distribution."""
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "media-scout"


def test_native_plugin_documents_qualified_boundaries_and_rollback():
    acceptance = PLUGIN / "ACCEPTANCE.md"
    assert acceptance.is_file(), "Native release needs an explicit acceptance/rollback contract"
    text = acceptance.read_text(encoding="utf-8")
    for phrase in ["synthetic", "native", "Discord", "replay", "cleanup", "rollback", "credentials"]:
        assert phrase in text


def test_plugin_bundled_skill_metadata_and_local_references():
    path = PLUGIN / "skills/workflow/SKILL.md"
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.+)", text, re.S)
    assert match
    meta = yaml.safe_load(match[1])
    assert meta["name"] == "workflow" and meta["version"] == "0.1.0"
    assert meta["author"].startswith("Daksh Agrawal")
    assert len(meta["description"]) <= 60 and meta["description"].endswith(".")
    assert meta["metadata"]["hermes"]["related_skills"] == []
    for relative in re.findall(r"\[[^\]]+\]\((references/[^)]+)\)", text):
        assert (path.parent / relative).is_file()
    for section in ["## When to Use", "## Prerequisites", "## Procedure", "## Pitfalls", "## Verification"]:
        assert section in text


def test_native_plugin_source_has_no_private_deployment_material():
    for path in PLUGIN.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".md", ".yaml", ".yml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"/home/|/Users/|[A-Za-z]:\\\\", text), path
        assert not re.search(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{15,}", text), path
        assert not re.search(r"\bt_[0-9a-f]{8}\b", text), path
        assert not re.search(r"\b\d{17,20}\b", text), path
        assert not re.search(r"\binstagram_[A-Za-z0-9_-]{11}\b", text), path


def test_plugin_readme_links_resolve():
    for path in PLUGIN.rglob("*.md"):
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
            if ":" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
