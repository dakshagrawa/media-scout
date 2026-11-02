"""Offline contracts for the portable media skill and workflow package."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / "workflows" / "media-scout"
SKILL = ROOT / "media-evidence-library" / "SKILL.md"


def test_media_skill_frontmatter_and_actionable_sections():
    text = SKILL.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n(.+)\Z", text, re.S)
    assert match
    meta = yaml.safe_load(match[1])
    assert meta["name"] == "media-evidence-library"
    assert len(meta["description"]) <= 60 and meta["description"].endswith(".")
    assert meta["author"].startswith("Daksh Agrawal")
    assert meta["version"] == "0.1.1"
    assert meta["platforms"] == ["linux"]
    assert meta["metadata"]["hermes"]["category"] == "productivity"
    assert meta["metadata"]["hermes"]["related_skills"] == []
    sections = ["## When to Use", "## Prerequisites", "## Procedure", "## Pitfalls", "## Verification"]
    assert [text.index(s) for s in sections] == sorted(text.index(s) for s in sections)
    for phrase in ["standing authorization", "Default owns", "source claims", "original URL", "separate approval", "not a hard sandbox", "local-only"]:
        assert phrase in text


def test_templates_are_safe_inert_defaults():
    policy = json.loads((WORKFLOW / "templates/policy.example.json").read_text(encoding="utf-8"))
    assert policy["cleanup_mode"] == "report-only"
    assert policy["cleanup_authorization"] is None
    assert policy["cleanup_qualification"] is None
    assert policy["review_authorization"] is None
    assert policy["automatic_forwarding"] is False
    assert policy["automatic_installation"] is False
    assert policy["automatic_catalog_expiry"] is False
    assert policy["evidence_retention_days"] == 90
    assert policy["media_cache_retention_days"] == 7
    assert policy["cleanup_max_records"] == 100
    assert policy["cleanup_max_files"] == 100
    assert policy["cleanup_max_bytes"] == 52428800
    config = yaml.safe_load((WORKFLOW / "templates/discord.example.yaml").read_text(encoding="utf-8"))
    assert config["platforms"]["discord"]["enabled"] is False
    assert config["platforms"]["discord"]["extra"]["auto_thread_media_ids"] is False
    record = json.loads((WORKFLOW / "templates/library-record.example.json").read_text(encoding="utf-8"))
    assert record["synthetic"] is True
    assert record["review_status"] == "not_requested"
    assert record["review_tasks"] == []


def test_no_runtime_service_or_live_state_is_distributed():
    for directory in [ROOT / "media-evidence-library", WORKFLOW]:
        assert not list(directory.rglob("*.py"))
        assert not list(directory.rglob("*.sh"))
        assert not list(directory.rglob("*.db"))
        assert not list(directory.rglob("*.mp4"))
        assert not list(directory.rglob("*.jsonl"))
    assert not (WORKFLOW / "records").exists()
    assert not (WORKFLOW / "cache").exists()


def test_new_package_has_no_machine_paths_or_live_identifiers():
    paths = [ROOT / "README.md", ROOT / "MIGRATION.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md", *list((ROOT / "media-evidence-library").rglob("*")), *list(WORKFLOW.rglob("*")), *list((ROOT / "patches/media-thread-naming").rglob("*"))]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"/home/|/Users/|[A-Za-z]:\\\\", text), path
        assert not re.search(r"\b\d{17,20}\b", text), path
        assert not re.search(r"\bt_[0-9a-f]{8}\b", text), path
        assert not re.search(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{15,}", text), path
        assert not re.search(r"\binstagram_[A-Za-z0-9_-]{11}\b", text), path


def test_markdown_relative_links_exist():
    docs = [ROOT / "README.md", ROOT / "MIGRATION.md", *list((ROOT / "media-evidence-library").rglob("*.md")), *list(WORKFLOW.rglob("*.md")), *list((ROOT / "patches").rglob("*.md"))]
    for path in docs:
        for target in re.findall(r"(?<!!)\[[^\]]+\]\(([^\s)]+)\)", path.read_text(encoding="utf-8")):
            if ":" in target or target.startswith("#"):
                continue
            assert (path.parent / target.split("#")[0]).exists(), (path, target)


def test_ownership_learning_and_approval_contract():
    scout = (WORKFLOW / "templates/scout-SOUL.md").read_text(encoding="utf-8")
    contract = (WORKFLOW / "templates/default-review-contract.md").read_text(encoding="utf-8")
    assert "Default owns" in scout
    assert "no per-item forwarding prompt" in scout
    assert "only after the owner enables" in scout
    assert "separate worker session" in contract
    assert "not a skill proposal" in contract
    assert "not automatically injected" in contract
    assert "no blanket memory ingestion" in contract
    assert "separate approval" in contract


def test_retention_requires_qualification_and_protects_metadata():
    text = (ROOT / "media-evidence-library/references/retention.md").read_text(encoding="utf-8")
    for phrase in ["report-only", "delete-expired", "pinned", "queued", "symlink", "nested", "unknown", "permanent", "literal", "before", "after", "50 MiB", "100", "Never use recursive deletion", "not a hard sandbox"]:
        assert phrase in text
    assert "policy flag alone" in text
    assert "missing/unverifiable reference" in text
    setup = (WORKFLOW / "README.md").read_text(encoding="utf-8")
    assert "Do not copy a live profile" in setup
    assert "fixture" in setup and "explicit" in setup


def test_native_patch_provenance_and_parseability():
    import hashlib
    directory = ROOT / "patches/media-thread-naming"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    bundle = directory / "instagram-thread-names.patch"
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() == manifest["patch_sha256"]
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["upstream_base_commit"])
    assert manifest["upstream_repository"] == "https://github.com/NousResearch/hermes-agent"
    assert manifest["upstream_release"] is False
    assert manifest["deployment_reported_targeted_tests"] == 64
    assert "Copyright (c) 2025 Nous Research" in (directory / "UPSTREAM-LICENSE").read_text(encoding="utf-8")
    assert subprocess.run(["git", "apply", "--numstat", str(bundle)], cwd=ROOT, capture_output=True).returncode == 0


class DiagramParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.svgs = 0
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.scripts.append(attrs)
        if tag == "svg":
            self.svgs += 1
        if tag in {"script", "img", "iframe", "link"}:
            self.resources.extend(attrs.get(k, "") for k in ("src", "href") if attrs.get(k))


def test_diagram_is_self_contained_and_no_script():
    parser = DiagramParser()
    parser.feed((WORKFLOW / "workflow.html").read_text(encoding="utf-8"))
    assert parser.svgs == 1
    assert parser.scripts == []
    assert parser.resources == []


@pytest.mark.parametrize("relative", ["media-evidence-library/SKILL.md", "workflows/media-scout/README.md", "workflows/media-scout/workflow.html", "patches/media-thread-naming/README.md", "MIGRATION.md"])
def test_public_deliverables_exist(relative):
    assert (ROOT / relative).is_file()


def test_ci_uses_two_linux_jobs_and_manual_cross_platform_matrix():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    parsed = yaml.load(workflow, Loader=yaml.BaseLoader)
    assert "workflow_dispatch" in parsed["on"]
    assert parsed["permissions"] == {"contents": "read"}
    assert list(parsed["jobs"]) == ["tests"]
    job = parsed["jobs"]["tests"]
    assert job["name"] == "Python ${{ matrix.python-version }} on ${{ matrix.os }}"
    assert job["strategy"]["matrix"]["python-version"] == ["3.10", "3.13"]
    expression = job["strategy"]["matrix"]["os"]
    assert "github.event_name == 'workflow_dispatch'" in expression
    manual_matrix = re.search(r"&& '([^']+)'", expression)
    required_matrix = re.search(r"\|\| '([^']+)'", expression)
    assert manual_matrix and required_matrix
    assert json.loads(manual_matrix[1]) == ["ubuntu-latest", "macos-latest", "windows-latest"]
    assert json.loads(required_matrix[1]) == ["ubuntu-latest"]
    assert 'elif [[ "$EVENT_NAME" == "workflow_dispatch" ]]' in workflow
    assert "git diff-tree --check --root -r HEAD" in workflow


def test_auto_thread_parent_lookup_and_new_record_creation_are_explicit():
    skill = SKILL.read_text(encoding="utf-8")
    provenance = (ROOT / "media-evidence-library/references/source-provenance.md").read_text(encoding="utf-8")
    assert "references/source-provenance.md" in skill
    for phrase in ["parent", "not_found", "CREATE", "same run", "bot progress", "exact", "headless", "verified", "No broader permissions"]:
        assert phrase in provenance
    assert "not a blocker" in skill
    assert "similar_files" in provenance
