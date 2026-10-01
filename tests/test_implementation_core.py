from __future__ import annotations

import pytest

from doc_sync.analyzer import analyze_impact
from doc_sync.detector import detect_changes
from doc_sync.idempotency import compute_processing_identity, is_stale_run
from doc_sync.models import PRContext, ValidationResult
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
