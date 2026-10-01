from __future__ import annotations

from doc_sync.models import PRContext
from doc_sync.orchestrator import run_documentation_sync


def test_run_documentation_sync_noop_when_no_changes_are_detected() -> None:
    result = run_documentation_sync(
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=10,
            head_sha='sha-1',
            base_sha='sha-0',
            event_name='pull_request',
            workflow_run_id='wf-10',
        ),
        changed_files=[],
        repo_state={'docs': ['README.md'], 'source': ['src/example.py']},
        corpus={},
    )

    assert result['status'] == 'no_op'


def test_run_documentation_sync_generates_and_validates_docs() -> None:
    result = run_documentation_sync(
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=11,
            head_sha='sha-2',
            base_sha='sha-1',
            event_name='pull_request',
            workflow_run_id='wf-11',
        ),
        changed_files=[{'path': 'src/api.py', 'status': 'modified', 'content': 'def demo_function(): pass'}],
        repo_state={'docs': ['README.md'], 'source': ['src/api.py']},
        corpus={'README.md': '# Demo\n\nUpdated docs for new API changes.'},
    )

    assert result['status'] in {'success', 'skipped'}
    assert 'check' in result
