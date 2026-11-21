"""Offline synthetic contract tests for optional date-bounded source discovery (#5)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[2] / "plugins" / "media-scout"


def _load_discovery():
    spec = importlib.util.spec_from_file_location("ms_discovery_mod", PLUGIN_DIR / "discovery.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_synthetic_packet_covers_accessible_blocked_duplicate_and_distinct_related():
    disc = _load_discovery()
    packet = disc.build_discovery_packet(
        question="Recent creator posts comparing local transcription tools",
        date_start="2026-10-01",
        date_end="2026-10-31",
        platforms=["threads", "youtube", "x"],
        budget={"max_items": 10, "max_requests_per_platform": 5, "max_cost_usd": 0.0},
        platform_coverage=[
            {
                "platform": "threads",
                "status": "covered",
                "covered_window": {"start": "2026-10-01", "end": "2026-10-31"},
            },
            {
                "platform": "youtube",
                "status": "partial",
                "covered_window": {"start": "2026-10-15", "end": "2026-10-31"},
                "reason": "pagination limit reached",
                "stop_condition": "youtube_max_requests_reached",
            },
            {
                "platform": "x",
                "status": "blocked",
                "covered_window": None,
                "reason": "login wall prevented public search",
                "stop_condition": "x_login_wall",
            },
        ],
        sources=[
            {
                "platform": "threads",
                "original_url": "https://threads.example/post/100?utm_source=share",
                "canonical_url": "https://threads.example/post/100",
                "related_topic": "tool-alpha",
                "published_at": "2026-10-12",
                "published_at_provenance": "observed",
                "retrieved_at": "2026-10-31",
                "access_status": "accessible",
                "claims": [
                    {"text": "Runs offline on CPU", "verified": True},
                    {"text": "10x faster than baseline", "verified": False},
                ],
            },
            # Exact canonical duplicate (should collapse without losing original URL)
            {
                "platform": "threads",
                "original_url": "https://threads.example/post/100?ref=repost",
                "canonical_url": "https://threads.example/post/100",
                "related_topic": "tool-alpha",
                "published_at": "2026-10-12",
                "published_at_provenance": "observed",
                "retrieved_at": "2026-10-31",
                "access_status": "accessible",
                "claims": [],
            },
            # Distinct post about the same product/topic (must NOT merge)
            {
                "platform": "youtube",
                "original_url": "https://youtube.example/watch?v=abc123",
                "canonical_url": "https://youtube.example/watch?v=abc123",
                "related_topic": "tool-alpha",
                "published_at": "2026-10-20",
                "published_at_provenance": "estimated",
                "retrieved_at": "2026-10-31",
                "access_status": "accessible",
                "claims": [{"text": "Supports diarization", "verified": False}],
            },
            # Blocked source with unavailable publication date
            {
                "platform": "x",
                "original_url": "https://x.example/user/status/999",
                "canonical_url": "https://x.example/user/status/999",
                "published_at": None,
                "published_at_provenance": "unavailable",
                "retrieved_at": "2026-10-31",
                "access_status": "login_required",
                "access_limit_reason": "post behind login wall",
                "claims": [],
            },
        ],
    )

    assert packet["full_coverage"] is False
    assert packet["duplicates_collapsed"] == 1
    assert len(packet["sources"]) == 3
    # Exact duplicate recorded on the primary entry
    assert packet["sources"][0]["duplicate_urls"] == ["https://threads.example/post/100?ref=repost"]
    # Distinct related posts remain separate
    related_urls = [s["canonical_url"] for s in packet["sources"] if s["related_topic"] == "tool-alpha"]
    assert len(related_urls) == 2
    # Date provenances preserved
    assert [s["published_at_provenance"] for s in packet["sources"]] == ["observed", "estimated", "unavailable"]
    # Unverified claims and stop conditions reported
    assert len(packet["unverified_claims"]) == 2
    assert set(packet["stop_conditions"]) == {"youtube_max_requests_reached", "x_login_wall"}
    # No side effects enabled
    assert packet["side_effects"] == {
        "credentials_required": False,
        "paid_apis_enabled": False,
        "automatic_media_processing": False,
    }


def test_validation_rejects_missing_reason_and_enforces_budget_stop():
    disc = _load_discovery()
    with pytest.raises(ValueError, match="reason required"):
        disc.build_discovery_packet(
            question="Q",
            date_start="2026-10-01",
            date_end="2026-10-05",
            platforms=["threads"],
            budget={"max_items": 2, "max_requests_per_platform": 2},
            platform_coverage=[{"platform": "threads", "status": "blocked"}],
            sources=[],
        )

    pkt = disc.build_discovery_packet(
        question="Q",
        date_start="2026-10-01",
        date_end="2026-10-05",
        platforms=["threads"],
        budget={"max_items": 1, "max_requests_per_platform": 2},
        platform_coverage=[
            {
                "platform": "threads",
                "status": "covered",
                "covered_window": {"start": "2026-10-01", "end": "2026-10-05"},
            }
        ],
        sources=[
            {"platform": "threads", "original_url": "https://threads.example/1", "published_at_provenance": "unavailable"},
            {"platform": "threads", "original_url": "https://threads.example/2", "published_at_provenance": "unavailable"},
        ],
    )
    assert len(pkt["sources"]) == 1
    assert "budget_max_items_reached" in pkt["stop_conditions"]
