from __future__ import annotations

import json

import pytest

from doc_sync.analyzer import analyze_impact
from doc_sync.cli import _collect_github_pr_metadata
from doc_sync.detector import detect_changes
from doc_sync.generator import generate_docs
from doc_sync.github_client import check_pr_approval_state
from doc_sync.idempotency import compute_processing_identity, is_stale_run
from doc_sync.models import GenerationRequest, PRContext, ProcessingIdentity, to_jsonable
from doc_sync.redactor import redact_corpus
from doc_sync.validator import run_validators


@pytest.fixture
def pr_context() -> PRContext:
    return PRContext(
        repo="demo/repo",
        owner="demo",
        pr_number=42,
        head_sha="abc123",
        base_sha="def456",
        event_name="pull_request",
        workflow_run_id="run-123",
    )


def test_detect_changes_lists_code_and_docs(pr_context: PRContext) -> None:
    changed = detect_changes(
        pr_context,
        [
            {"path": "src/api.py", "status": "modified", "content": "def create_user():\n    pass\n"},
            {"path": "docs/api.md", "status": "modified", "content": "# API\n"},
            {"path": "README.md", "status": "modified", "content": "# Demo\n"},
        ],
    )

    assert {item.path for item in changed} == {"src/api.py", "docs/api.md", "README.md"}
    assert any(item.path == "src/api.py" for item in changed)


def test_analyze_impact_limits_docs_scope(pr_context: PRContext) -> None:
    impact = analyze_impact(
        [
            {"path": "src/api.py", "status": "modified", "content": "def update_user()"},
            {"path": "README.md", "status": "modified", "content": "Docs"},
            {"path": ".github/workflows/main.yml", "status": "modified", "content": "name: ci"},
        ],
        repo_state={"docs": ["README.md", "docs/api.md"], "source": ["src/api.py"]},
    )

    assert impact.requires_generation is True
    assert "README.md" in impact.allowed_doc_paths
    assert ".github/workflows/main.yml" not in impact.allowed_doc_paths


def test_run_validators_passes_for_valid_markdown() -> None:
    result = run_validators(
        "post_generation",
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=1,
            head_sha="aaa",
            base_sha="bbb",
            event_name="pull_request",
            workflow_run_id="run-1",
        ),
        {"README.md": "# Example\n\nThis is valid markdown.\n"},
        ["README.md"],
    )

    assert result.status == "pass"
    assert result.phase == "post_generation"


def test_redact_corpus_removes_obvious_secrets() -> None:
    cleaned = redact_corpus({"README.md": "token=ghp_123456abcdef\n"})

    assert cleaned.status == "redacted"
    assert "ghp_123456abcdef" not in cleaned.redacted_content["README.md"]


def test_processing_identity_and_stale_check() -> None:
    ctx = PRContext(
        repo="demo/repo",
        owner="demo",
        pr_number=7,
        head_sha="sha-1",
        base_sha="base-1",
        event_name="pull_request",
        workflow_run_id="run-7",
    )

    identity_a = compute_processing_identity(
        ctx,
        ["README.md"],
        [{"path": "src/api.py", "status": "modified", "content": "def ping(): pass"}],
    )
    identity_b = compute_processing_identity(
        ctx,
        ["README.md"],
        [{"path": "src/api.py", "status": "modified", "content": "def ping(): pass"}],
    )

    assert identity_a == identity_b
    assert is_stale_run("sha-2", "sha-1") is True


def test_redact_corpus_blocks_unsafely_embedded_secret_candidates() -> None:
    result = redact_corpus({"README.md": "token = "" + 'ghp_verysecretvalue'"})
    assert result.status in {"redacted", "blocked"}
    assert "ghp_verysecretvalue" not in result.redacted_content["README.md"]


def test_stale_head_rejection_and_safe_commit_gate() -> None:
    ctx = PRContext(
        repo="demo/repo",
        owner="demo",
        pr_number=8,
        head_sha="captured",
        base_sha="base",
        event_name="pull_request",
        workflow_run_id="wf-8",
        metadata={"live_head_sha": "newer"},
    )

    assert is_stale_run(ctx.metadata["live_head_sha"], ctx.head_sha) is True


def test_commit_only_updates_allowed_documents() -> None:
    from pathlib import Path
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

        (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        allowed = ["README.md"]
        (repo / "README.md").write_text("# Demo\n\nUpdated documentation.\n", encoding="utf-8")
        (repo / "src" / "app.py").write_text("print('hi changed')\n", encoding="utf-8")

        result = subprocess.run(["git", "diff", "--name-only"], cwd=repo, capture_output=True, text=True, check=True)
        changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert "src/app.py" in changed
        assert "README.md" in changed
        assert set(allowed).issubset(set(changed))


def test_run_validators_rejects_malformed_openapi() -> None:
    result = run_validators(
        "pre_generation",
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=99,
            head_sha="head-99",
            base_sha="base-99",
            event_name="pull_request",
            workflow_run_id="run-99",
        ),
        {"openapi.json": '{"openapi": "3.0.0", "paths": [}', "README.md": "# Demo\n"},
        ["README.md", "openapi.json"],
    )
    assert result.status == "fail"
    assert any("openapi" in message.lower() for message in result.errors)


def test_run_validators_rejects_broken_relative_link() -> None:
    result = run_validators(
        "post_generation",
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=100,
            head_sha="head-100",
            base_sha="base-100",
            event_name="pull_request",
            workflow_run_id="run-100",
        ),
        {"docs/api.md": "# API\n\nSee [missing guide](../missing.md).\n"},
        ["docs/api.md"],
    )
    assert result.status == "fail"
    assert any("missing" in message.lower() for message in result.errors)


def test_run_validators_rejects_structural_mismatch() -> None:
    result = run_validators(
        "post_generation",
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=101,
            head_sha="head-101",
            base_sha="base-101",
            event_name="pull_request",
            workflow_run_id="run-101",
            metadata={"changed_api_summary": "create_user", "documented_api_summary": "delete_user"},
        ),
        {"README.md": "# Docs\n\nThis documents delete_user API.\n"},
        ["README.md"],
    )
    assert result.status == "fail"
    assert any("structural" in message.lower() or "api" in message.lower() for message in result.errors)


def test_pull_request_event_resolves_pr_number_from_event_context(monkeypatch) -> None:
    from doc_sync.cli import _resolve_pr_number

    monkeypatch.delenv('PR_NUMBER', raising=False)
    monkeypatch.delenv('GITHUB_REF', raising=False)
    assert _resolve_pr_number('pull_request', 42) == 42

    monkeypatch.setenv('PR_NUMBER', '7')
    assert _resolve_pr_number('pull_request', 0) == 7


def test_workflow_dispatch_with_valid_pr_number_resolves_pr_number(monkeypatch) -> None:
    from doc_sync.cli import _resolve_pr_number

    monkeypatch.delenv('PR_NUMBER', raising=False)
    assert _resolve_pr_number('workflow_dispatch', 99) == 99


def test_missing_or_zero_pr_number_fails_safely(monkeypatch) -> None:
    from doc_sync.cli import _resolve_pr_number

    monkeypatch.delenv('PR_NUMBER', raising=False)
    monkeypatch.delenv('GITHUB_REF', raising=False)
    assert _resolve_pr_number('workflow_dispatch', 0) == 0
    assert _resolve_pr_number('pull_request', 0) == 0


def test_check_pr_approval_state_requires_real_approval_metadata() -> None:
    state = check_pr_approval_state(
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=120,
            head_sha="abc",
            base_sha="def",
            event_name="pull_request",
            workflow_run_id="run-120",
            metadata={"has_codeowners": True, "review_required": True, "approved": False, "current_pr_state_matches_review": True},
        )
    )
    assert state.review_valid is False
    assert state.reason


def test_check_pr_approval_state_false_without_authorized_codeowner_approval() -> None:
    state = check_pr_approval_state(
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=220,
            head_sha="abc",
            base_sha="def",
            event_name="pull_request",
            workflow_run_id="run-220",
            metadata={
                'has_codeowners': True,
                'review_required': True,
                'approved': False,
                'current_pr_state_matches_review': True,
            },
        )
    )
    assert state.review_valid is False
    assert 'authorized' in state.reason.lower() or 'not approved' in state.reason.lower()


def test_check_pr_approval_state_true_with_authorized_codeowner_approval() -> None:
    state = check_pr_approval_state(
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=221,
            head_sha="abc",
            base_sha="def",
            event_name="pull_request",
            workflow_run_id="run-221",
            metadata={
                'has_codeowners': True,
                'review_required': True,
                'approved': True,
                'current_pr_state_matches_review': True,
                'review_head_sha': 'abc',
                'reviewer': 'demo-owner',
            },
        )
    )
    assert state.review_valid is True
    assert state.reason.lower().startswith('native') or 'satisfied' in state.reason.lower()


def test_generate_docs_uses_provider_output_not_raw_corpus(monkeypatch) -> None:
    def fake_provider(payload):
        return {"README.md": "# Generated Documentation\n\nThis is AI output.\n"}

    import doc_sync.generator as generator_module

    monkeypatch.setattr(generator_module, "generate_with_openai", fake_provider)
    request = GenerationRequest(
        pr_context=PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=121,
            head_sha="head-121",
            base_sha="base-121",
            event_name="pull_request",
            workflow_run_id="run-121",
        ),
        input_corpus={"README.md": "# Input\n"},
        affected_doc_paths=["README.md"],
        redacted_corpus={"README.md": "# Input\n"},
        processing_identity=ProcessingIdentity(
            pr_number=121,
            head_sha="head-121",
            canonical_input="x",
            doc_state="README.md",
            fingerprint="abc123",
        ),
        allowed_doc_paths=["README.md"],
    )

    result = generate_docs(request)
    assert result[0].content == "# Generated Documentation\n\nThis is AI output.\n"
    assert result[0].source == "ai"


def test_check_pr_approval_state_requires_explicit_approval_payload() -> None:
    state = check_pr_approval_state(
        PRContext(
            repo="demo/repo",
            owner="demo",
            pr_number=122,
            head_sha="abc",
            base_sha="def",
            event_name="pull_request",
            workflow_run_id="run-122",
            metadata={},
        )
    )

    assert state.review_valid is False
    assert "missing" in state.reason.lower() or "invalid" in state.reason.lower()


def test_generate_with_openai_does_not_return_raw_corpus() -> None:
    from doc_sync.generator import generate_with_openai

    try:
        generate_with_openai({"redacted_corpus": {"README.md": "# Input\n\nActual repository content."}})
        assert False, 'missing provider credentials should fail closed instead of returning raw corpus content'
    except RuntimeError:
        pass


def test_write_atomic_commit_rejects_stale_repo_head() -> None:
    import subprocess
    import tempfile
    from pathlib import Path

    from doc_sync.committer import write_atomic_commit
    from doc_sync.models import CommitPlan

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(['git', 'init'], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', 'config', 'user.name', 'Test Bot'], cwd=repo, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo, check=True)

        (repo / 'README.md').write_text('# Demo\n', encoding='utf-8')
        subprocess.run(['git', 'add', 'README.md'], cwd=repo, check=True)
        subprocess.run(['git', 'commit', '-m', 'init'], cwd=repo, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        head_sha = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        (repo / 'README.md').write_text('# Demo\n\nUpdated docs\n', encoding='utf-8')

        plan = CommitPlan(
            branch='main',
            base_sha='base',
            head_sha='stale-head',
            files_to_update=['README.md'],
            message='Update docs',
            footer='Docs-Generated-By: test',
            repo_path=str(repo),
            allowed_paths=['README.md'],
        )

        try:
            write_atomic_commit(plan)
            assert False, 'stale repo head should have been rejected'
        except ValueError as exc:
            assert 'stale' in str(exc).lower() or 'head' in str(exc).lower()
        assert subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo, check=True, capture_output=True, text=True).stdout.strip() == head_sha


def test_run_documentation_sync_fails_closed_without_provider_credentials(monkeypatch) -> None:
    from doc_sync.orchestrator import run_documentation_sync

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', '')

    result = run_documentation_sync(
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=200,
            head_sha='head-200',
            base_sha='base-200',
            event_name='pull_request',
            workflow_run_id='run-200',
            metadata={
                'has_codeowners': True,
                'review_required': True,
                'approved': True,
                'current_pr_state_matches_review': True,
                'require_provider_auth': True,
            },
        ),
        changed_files=[{'path': 'README.md', 'status': 'modified', 'content': '# Docs'}],
        repo_state={'docs': ['README.md'], 'source': []},
        corpus={'README.md': '# Docs\n\nThis needs generation.'},
    )

    assert result['status'] == 'fail'
    assert result['stage'] == 'provider_auth'


def test_run_documentation_sync_result_is_json_serializable(monkeypatch) -> None:
    from doc_sync.orchestrator import run_documentation_sync

    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', '')

    result = run_documentation_sync(
        PRContext(
            repo='demo/repo',
            owner='demo',
            pr_number=201,
            head_sha='head-201',
            base_sha='base-201',
            event_name='pull_request',
            workflow_run_id='run-201',
            metadata={
                'has_codeowners': True,
                'review_required': True,
                'approved': True,
                'current_pr_state_matches_review': True,
                'require_provider_auth': True,
            },
        ),
        changed_files=[{'path': 'README.md', 'status': 'modified', 'content': '# Docs'}],
        repo_state={'docs': ['README.md'], 'source': []},
        corpus={'README.md': '# Docs\n\nThis needs generation.'},
    )

    dumped = json.dumps(to_jsonable(result))
    assert 'provider_auth' in dumped


def test_collect_github_pr_metadata_uses_live_pr_review_state(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(self.payload).encode('utf-8')

    def fake_urlopen(request, timeout=None):
        url = request.full_url
        if url.endswith('/contents/.github/CODEOWNERS'):
            return FakeResponse({'path': '.github/CODEOWNERS'})
        if url.endswith('/contents/CODEOWNERS'):
            return FakeResponse({'path': 'CODEOWNERS'})
        if url.endswith('/pulls/42/reviews'):
            return FakeResponse([
                {
                    'state': 'APPROVED',
                    'commit_id': 'abc123',
                    'user': {'login': 'reviewer'},
                }
            ])
        raise AssertionError(f'unexpected URL: {url}')

    monkeypatch.setattr('urllib.request.urlopen', fake_urlopen)

    metadata = _collect_github_pr_metadata('demo', 'repo', 42, 'token', 'abc123')

    assert metadata['has_codeowners'] is True
    assert metadata['review_required'] is True
    assert metadata['approved'] is True
    assert metadata['current_pr_state_matches_review'] is True
    assert metadata['review_head_sha'] == 'abc123'
    assert metadata['reviewer'] == 'reviewer'


def test_generate_with_openai_strict_mode_rejects_missing_key() -> None:
    from doc_sync.generator import generate_with_openai

    try:
        generate_with_openai({'redacted_corpus': {'README.md': '# Input\n'}, 'strict': True, 'require_provider_auth': True})
        assert False, 'strict provider mode should reject a missing API key'
    except RuntimeError:
        pass
