"""Offline archival contracts; never connect a profile or publish anything."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
import zipfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "snapshot-v1"


def snapshot_files():
    return sorted(p for p in SNAPSHOT.rglob("*") if p.is_file())


def test_snapshot_manifest_identity():
    manifest = json.loads((SNAPSHOT / "MANIFEST.json").read_text(encoding="utf-8"))
    files = {str(p.relative_to(SNAPSHOT)): p for p in snapshot_files() if p.name != "MANIFEST.json"}
    assert set(files) == set(manifest["files"])
    for name, path in files.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][name]["sha256"]
        assert path.stat().st_size == manifest["files"][name]["bytes"]


def test_snapshot_files_are_actually_versioned():
    # A complete working tree is not proof that ignored setup contracts ship.
    tracked = set(subprocess.check_output(
        ["git", "ls-files", "--", "snapshot-v1"], cwd=ROOT, text=True
    ).splitlines())
    expected = {str(path.relative_to(ROOT)).replace("\\", "/") for path in snapshot_files()}
    assert tracked == expected
    for sample in ["snapshot-v1/profile/media-library/records/private.json",
                   "snapshot-v1/profile/media-library/templates/private-extra.md"]:
        result = subprocess.run(["git", "check-ignore", "--no-index", sample], cwd=ROOT,
                                capture_output=True, text=True)
        assert result.returncode == 0


def test_safe_import_settings_and_disabled_cron():
    config = yaml.safe_load((SNAPSHOT / "config.example.yaml").read_text(encoding="utf-8"))
    assert config["platforms"]["discord"]["enabled"] is False
    assert config["discord"]["missed_message_backfill"]["enabled"] is False
    policy = json.loads((SNAPSHOT / "policy.safe-defaults.json").read_text(encoding="utf-8"))
    assert policy["automatic_forwarding"] is False
    assert policy["cleanup_mode"] == "report-only"
    recovery = json.loads((SNAPSHOT / "recovery.safe-defaults.json").read_text(encoding="utf-8"))
    assert recovery["enabled"] is False
    jobs = json.loads((SNAPSHOT / "cron.definitions.json").read_text(encoding="utf-8"))["jobs"]
    assert len(jobs) == 2
    assert all(j["enabled"] is False for j in jobs)
    assert any(j["source_enabled_at_capture"] is False for j in jobs)


def test_historical_policy_is_explicit_not_silently_lost():
    policy = json.loads((SNAPSHOT / "profile/media-library/policy.json").read_text(encoding="utf-8"))
    assert policy["automatic_forwarding"] is True
    assert policy["cleanup_mode"] == "delete-expired"
    assert policy["media_cache_retention_days"] == 7
    assert policy["evidence_retention_days"] == 90
    assert policy["cleanup_max_files"] == 100
    assert policy["cleanup_max_bytes"] == 50 * 1024 * 1024
    readme = (SNAPSHOT / "README.md").read_text(encoding="utf-8")
    assert "historical behavior" in readme
    assert "Do not bulk-copy" in readme
    assert "not installed" in readme


@pytest.mark.parametrize("name", ["media-evidence-library", "media-to-github"])
def test_local_skill_frontmatter_and_support_closure(name):
    base = SNAPSHOT / "profile/skills/media" / name
    source = (base / "SKILL.md").read_text(encoding="utf-8")
    assert source.startswith("---\n")
    _, header, body = source.split("---", 2)
    meta = yaml.safe_load(header)
    assert meta["name"] == name
    assert len(meta["description"]) <= 60
    assert meta["description"].endswith(".")
    assert meta["license"] == "MIT"
    assert body.strip()
    for link in re.findall(r"\]\(([^)]+)\)", body):
        if not link.startswith(("http:", "https:", "#")):
            assert (base / link).is_file(), link


def test_project_fit_and_publication_boundaries_preserved():
    contract = (SNAPSHOT / "profile/media-library/templates/primary-review-contract.md").read_text(encoding="utf-8")
    assert "GitHub project fit" in contract
    assert "read-only" in contract
    assert "implement, investigate, save for later or reject" in contract
    helper = (SNAPSHOT / "profile/skills/media/media-to-github/SKILL.md").read_text(encoding="utf-8")
    for text in ["Default remains the GitHub publishing operator", "full patch", "source notify+wake", "Material drift", "read the exact remote target before retrying"]:
        assert text in helper
    assert "not a promise of a registered slash command" in helper


def test_public_payload_excludes_private_paths_and_runtime_data():
    for path in snapshot_files():
        rel = path.relative_to(SNAPSHOT)
        assert not any(part in {"records", "receipts", "proposals", "sessions", "logs", "auth", ".env", "memories"} for part in rel.parts)
        assert path.suffix not in {".db", ".sqlite", ".mp4", ".mp3", ".png", ".jpg"}
        text = path.read_text(encoding="utf-8")
        # Ignore explicit content digests; digit runs inside a SHA are not account IDs.
        text = re.sub(r"\b[0-9a-f]{40,64}\b", "<digest>", text)
        for pattern in [r"/home/[a-zA-Z0-9_-]+", r"(?<!\d)\d{17,20}(?!\d)", r"\bt_[0-9a-f]{8}\b", r"https://discord\.com/channels/\d", r"(?:github_pat_|gh[pousr]_|sk-(?:proj-)?)[A-Za-z0-9_-]{18,}"]:
            assert not re.search(pattern, text), (str(rel), pattern)
        assert not path.is_symlink()


def test_snapshot_archive_extraction_identity(tmp_path):
    archive = tmp_path / "public.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for path in snapshot_files():
            z.write(path, str(path.relative_to(SNAPSHOT)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            assert not name.startswith("/") and ".." not in Path(name).parts
        z.extractall(tmp_path / "restored")
    for path in snapshot_files():
        assert (tmp_path / "restored" / path.relative_to(SNAPSHOT)).read_bytes() == path.read_bytes()
