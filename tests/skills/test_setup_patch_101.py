"""Offline contracts for the selective setup 1.0.1 instruction update."""
import hashlib
import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "snapshot-v1"
HELPER = SNAP / "profile/skills/media/media-to-github"


def text(path):
    return path.read_text(encoding="utf-8")


def test_setup_and_helper_versions_are_distinct_and_inventory_matches():
    manifest = json.loads(text(SNAP / "MANIFEST.json"))
    assert manifest["setup_version"] == "1.0.1"
    assert manifest["baseline_setup_version"] == "1.0.0"
    meta = yaml.safe_load(text(HELPER / "SKILL.md").split("---", 2)[1])
    assert meta["version"] == "0.2.0"
    inventory = json.loads(text(SNAP / "skills-inventory.json"))
    entry = next(x for x in inventory["inventory"] if x["name"] == "media-to-github")
    assert entry["version"] == meta["version"]
    assert entry["sha256"] == hashlib.sha256((HELPER / "SKILL.md").read_bytes()).hexdigest()
    assert entry["hash_scope"] == "sanitized bundled SKILL.md; original capture inventory otherwise retained"


def test_selective_routing_preserves_default_and_owner_limits():
    for path in [SNAP / "profile/SOUL.md", SNAP / "profile/media-library/review-policy.md"]:
        source = text(path)
        assert "summary" in source.lower()
        assert "bare" in source.lower()
        assert "project-fit" in source
        assert "no-forward" in source
        assert "unavailable" in source
    policy = text(SNAP / "profile/media-library/review-policy.md")
    assert "Historical behavior specification, not transferable consent" in policy
    assert "Activated:" not in policy
    assert "2026-11-02" not in policy


def test_easy_call_uses_canonical_checklist_repository_not_skill_path():
    helper = text(HELPER / "SKILL.md")
    easy_calls = helper.split("## Easy calls", 1)[1].split("## Procedure", 1)[0]
    assert "<github-owner>/<checklist-repository>" in easy_calls
    assert "production-web-checklist" not in easy_calls
    assert "production-web-checklist/" in helper.split("## Procedure", 1)[1]


def test_optional_actions_are_separate_from_required_blockers():
    for path in [SNAP / "profile/SOUL.md",
                 SNAP / "profile/media-library/templates/response-format.md",
                 SNAP / "profile/media-library/templates/primary-review-contract.md"]:
        source = text(path)
        assert "Optional things you can do" in source
        assert "None required" in source
        assert "homework" in source
    response = text(SNAP / "profile/media-library/templates/response-format.md")
    assert "Omit this section" in response
    assert "action-specific approval" in response


def test_issue_and_pr_have_proportional_self_contained_handoff():
    for name in ["issue.md", "pull-request.md"]:
        body = text(HELPER / "templates" / name)
        assert "## Implementation and deployment handoff" in body
        for field in ["Target / baseline", "Implementation", "Configuration / security / data",
                      "Acceptance / release gates", "Rollout / activation", "Operations / ownership",
                      "Rollback / recovery", "Open decisions / deferred work"]:
            assert f"**{field}:**" in body
        assert "Unknown" in body and "Not applicable" in body
        assert "without Discord or the source video" in body
    reference = text(HELPER / "references/implementation-deployment-handoff.md")
    for term in ["irreversible", "synthetic", "secret names", "documentation/skill-only",
                 "not a complete handoff", "not authorize", "git revert"]:
        assert term in reference.lower()
    assert "implementation-deployment-handoff.md" in text(HELPER / "SKILL.md")


def test_all_helper_support_links_resolve_and_patch_is_documented():
    for path in HELPER.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", text(path)):
            if not link.startswith(("https:", "http:", "#")):
                assert (path.parent / link).is_file(), (path.name, link)
    notes = text(SNAP / "CHANGES-1.0.1.md")
    for term in ["1.0.0", "0.2.0", "selective", "not a new full", "not published"]:
        assert term in notes.lower()
