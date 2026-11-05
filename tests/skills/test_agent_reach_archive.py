"""Archive integrity is separate from installation or runtime qualification."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = '7a38047acf26a729cbb27851e3cb81639da86b29'
ARCHIVE = ROOT / 'archive/agent-reach' / REVISION


def test_inactive_upstream_skill_archive_is_complete_and_byte_preserved():
    manifest = json.loads((ARCHIVE / 'MANIFEST.json').read_text())
    assert manifest['revision'] == REVISION
    expected = {
        'agent_reach/skill/SKILL.md', 'agent_reach/skill/SKILL_en.md',
        'agent_reach/skill/references/capabilities.md',
        'agent_reach/skill/references/maintenance.md',
        'agent_reach/skill/references/sessions.md',
        'LICENSE', 'pyproject.toml', 'docs/README_en.md',
    }
    assert {r['path'] for r in manifest['files']} == expected
    assert {str(p.relative_to(ARCHIVE / 'upstream')) for p in (ARCHIVE / 'upstream').rglob('*') if p.is_file()} == expected
    for record in manifest['files']:
        data = (ARCHIVE / 'upstream' / record['path']).read_bytes()
        assert len(data) == record['bytes']
        assert hashlib.sha256(data).hexdigest() == record['sha256']
        assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == record['git_blob']
    assert not (ROOT / 'plugins/media-scout/archive').exists()
    assert 'not a runnable or tested fallback' in (ROOT / 'archive/agent-reach/README.md').read_text()
