from __future__ import annotations

from doc_sync.detector import detect_changes
from doc_sync.models import PRContext


def test_detect_changes_classifies_files_and_preserves_metadata() -> None:
    pr_context = PRContext(
        repo='demo/repo',
        owner='demo',
        pr_number=3,
        head_sha='abc',
        base_sha='def',
        event_name='pull_request',
        workflow_run_id='wf-3',
    )

    changes = detect_changes(
        pr_context,
        [
            {'path': 'src/api.py', 'status': 'modified', 'content': 'def list_users(): pass'},
            {'path': 'docs/api.md', 'status': 'modified', 'content': '# API'},
            {'path': '.github/workflows/ci.yml', 'status': 'modified', 'content': 'name: ci'},
        ],
    )

    assert {item.path for item in changes} == {'src/api.py', 'docs/api.md', '.github/workflows/ci.yml'}
    assert changes[0].kind == 'code'
    assert changes[1].kind == 'docs'
    assert changes[2].kind == 'config'
