"""Selective upstream guidance stays instruction-only and safely reachable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / 'plugins/media-scout/skills/workflow'


def test_selective_retrieval_reference_is_wired_and_has_provenance():
    text = (BUNDLE / 'references/retrieval-routing.md').read_text()
    assert 'references/retrieval-routing.md' in (BUNDLE / 'SKILL.md').read_text()
    assert 'retrieval-routing.md' in (BUNDLE / 'references/extraction.md').read_text()
    for phrase in ['7a38047acf26a729cbb27851e3cb81639da86b29', 'Panniantong/Agent-Reach',
                   'NEED_SETUP', 'NEED_LOGIN', 'UPSTREAM_BROKEN', 'TIMEOUT',
                   'RATE_LIMITED', 'PLATFORM_BLOCKED', 'BUSY', 'NOT_FOUND', 'BAD_INPUT',
                   'nonempty', 'subtitle track', 'local transcription', 'not a runtime dependency',
                   'Do not copy browser sessions', 'untrusted data']:
        assert phrase in text
    notice = (ROOT / 'plugins/media-scout/THIRD_PARTY_NOTICES.md').read_text()
    assert 'Copyright (c) 2025 Agent Eyes' in notice
    assert 'Permission is hereby granted, free of charge' in notice
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in notice


def test_no_agent_reach_execution_or_setup_in_adapted_reference():
    text = (BUNDLE / 'references/retrieval-routing.md').read_text()
    for command in ['agent-reach setup', 'agent-reach install', 'agent-reach login',
                    'agent-reach add', '--from-browser', 'pip install', 'uv tool install']:
        assert command not in text
