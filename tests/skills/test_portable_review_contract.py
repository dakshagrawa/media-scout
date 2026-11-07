"""Textual regression guards for portable reviewer instructions, not model adherence."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "plugins/media-scout/skills/workflow/references/review-contract.md"


def test_project_fit_is_evidence_based_and_respects_owner_scope():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in [
        "ordinary new media", "relevant authorized owner projects", "read-only repository inspection",
        "expected value, effort/risk", "reasoned no-change", "informational-only, local-only or summary-only",
        "Do not manufacture an implementation proposal",
    ]:
        assert phrase in text


def test_deferred_skill_capture_requires_authorized_existing_catalog_and_readback():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in [
        "existing operator-designated single catalog", "only when review policy authorizes",
        "Preserve existing entries and source bindings", "upsert or deduplicate",
        "read back the exact entry", "without inventing a store", "not installation approval",
    ]:
        assert phrase in text


def test_completion_channel_and_summary_preserve_truthful_delivery():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in [
        "user_facing_summary", "native completion metadata", "actual requested deliverables",
        "not routine raw evidence", "action needed (none when true)",
        "Do not send unsolicited cross-channel messages", "claim a result was delivered merely because the task finished",
    ]:
        assert phrase in text
    assert not re.search(r"/home/|/Users/|\bt_[0-9a-f]{8}\b|\b\d{17,20}\b", text)


def test_existing_source_and_approval_safeguards_remain():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in [
        "untrusted quoted data", "separate specific owner approval", "original source",
        "Do not perform blanket personal-memory ingestion", "Native task status is distinct",
    ]:
        assert phrase in text
