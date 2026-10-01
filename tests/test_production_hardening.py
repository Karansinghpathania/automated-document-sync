from __future__ import annotations

import pytest

from doc_sync.committer import write_atomic_commit
from doc_sync.generator import generate_docs, generate_with_openai
from doc_sync.github_client import check_pr_approval_state
from doc_sync.models import GenerationRequest, PRContext, ProcessingIdentity
from doc_sync.validator import run_validators


def test_generate_with_openai_fails_closed_without_credentials() -> None:
    with pytest.raises(RuntimeError):
        generate_with_openai({
            'redacted_corpus': {'README.md': '# Demo\n'},
            'strict': True,
            'require_provider_auth': True,
        })

    with pytest.raises(RuntimeError):
        generate_with_openai({'redacted_corpus': {'README.md': '# Demo\n'}})


def test_generate_docs_rejects_output_outside_allowlist() -> None:
    request = GenerationRequest(
        pr_context=PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=1,
            head_sha='abc',
            base_sha='def',
            event_name='pull_request',
            workflow_run_id='run-1',
            metadata={'require_provider_auth': True},
        ),
        input_corpus={'README.md': '# Demo\n'},
        affected_doc_paths=['README.md'],
        redacted_corpus={'README.md': '# Demo\n'},
        processing_identity=ProcessingIdentity(
            pr_number=1,
            head_sha='abc',
            canonical_input='x',
            doc_state='README.md',
            fingerprint='abc123',
        ),
        allowed_doc_paths=['README.md'],
    )

    with pytest.raises(ValueError):
        generate_docs(
            GenerationRequest(
                pr_context=request.pr_context,
                input_corpus=request.input_corpus,
                affected_doc_paths=['README.md'],
                redacted_corpus=request.redacted_corpus,
                processing_identity=request.processing_identity,
                allowed_doc_paths=['README.md'],
            )
        )


def test_validation_returns_structured_check_results() -> None:
    result = run_validators(
        'post_generation',
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=7,
            head_sha='h1',
            base_sha='b1',
            event_name='pull_request',
            workflow_run_id='wf-7',
        ),
        {'docs/api.md': '# API\n\nSee [missing](../missing.md).\n'},
        ['docs/api.md'],
    )

    assert hasattr(result, 'checks')
    assert hasattr(result, 'files_checked')
    assert hasattr(result, 'blocking')
    assert hasattr(result, 'human_review_required')
    assert result.status == 'fail'
    assert result.blocking is True


def test_approval_state_fails_closed_for_missing_or_stale_review() -> None:
    coverage = check_pr_approval_state(
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=10,
            head_sha='current-head',
            base_sha='base',
            event_name='pull_request',
            workflow_run_id='wf-10',
            metadata={
                'has_codeowners': True,
                'review_required': True,
                'approved': True,
                'current_pr_state_matches_review': False,
                'review_head_sha': 'stale-head',
                'reviewer': 'owner',
            },
        )
    )

    assert coverage.review_valid is False
    assert 'stale' in coverage.reason.lower() or 'current' in coverage.reason.lower()


def test_commit_rejects_stale_repo_head() -> None:
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(['git', 'init'], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', 'config', 'user.name', 'Test Bot'], cwd=repo, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo, check=True)
        (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
        subprocess.run(['git', 'add', 'README.md'], cwd=repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        expected = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        (repo / 'README.md').write_text('# Demo\n\nUpdated\n', encoding='utf-8')

        with pytest.raises(ValueError):
            write_atomic_commit(
                {
                    'branch': 'main',
                    'base_sha': 'base',
                    'head_sha': 'stale-head',
                    'files_to_update': ['README.md'],
                    'message': 'Update docs',
                    'footer': 'Docs-Generated-By: test',
                    'repo_path': str(repo),
                    'allowed_paths': ['README.md'],
                }
            )

        assert subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True, capture_output=True, text=True).stdout.strip() == expected
