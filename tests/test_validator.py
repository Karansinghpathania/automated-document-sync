from __future__ import annotations

from doc_sync.models import PRContext
from doc_sync.validator import run_validators


def test_validate_fails_on_empty_markdown() -> None:
    result = run_validators(
        'post_generation',
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=4,
            head_sha='x',
            base_sha='y',
            event_name='pull_request',
            workflow_run_id='wf-4',
        ),
        {'README.md': ''},
        ['README.md'],
    )

    assert result.status == 'fail'
    assert any('README.md is empty.' in message for message in result.errors)


def test_validate_passes_for_valid_markdown() -> None:
    result = run_validators(
        'post_generation',
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=5,
            head_sha='z',
            base_sha='a',
            event_name='pull_request',
            workflow_run_id='wf-5',
        ),
        {'README.md': '# Demo\n\nThis is valid markdown.'},
        ['README.md'],
    )

    assert result.status == 'pass'
