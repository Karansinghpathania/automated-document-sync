from __future__ import annotations

import os
import subprocess
from typing import Any, Mapping

from .analyzer import analyze_impact
from .artifacts import publish_artifact
from .committer import prepare_commit, write_atomic_commit
from .detector import detect_changes
from .generator import generate_docs
from .github_client import check_pr_approval_state, set_check_status
from .idempotency import compute_processing_identity, is_stale_run, resolve_existing_successful_processing
from .logging import emit_log
from .models import ArtifactBundle, CommitPlan, GenerationRequest, PRContext
from .redactor import redact_corpus
from .validator import run_validators


def _resolve_live_head(pr_context: PRContext) -> str:
    candidate = str(
        pr_context.metadata.get('live_head_sha')
        or pr_context.metadata.get('current_head_sha')
        or pr_context.metadata.get('repo_head_sha')
        or ''
    ).strip()
    if candidate:
        return candidate
    repo_root = pr_context.metadata.get('repo_path')
    if repo_root:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo_root, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            return ''
    return ''


def run_documentation_sync(
    pr_context: PRContext,
    changed_files: list[dict[str, Any]] | None = None,
    repo_state: dict[str, Any] | None = None,
    corpus: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Inside a GitHub Action runtime, run the documented workflow stages in order."""
    if changed_files is None:
        changed_files = []
    if repo_state is None:
        repo_state = {'docs': ['README.md'], 'source': []}
    if corpus is None:
        corpus = {'README.md': '# Documentation\n'}

    detected = detect_changes(pr_context, changed_files)
    if not detected:
        return {
            'status': 'no_op',
            'stage': 'analysis',
            'changed_files': [],
            'check': set_check_status('success', 'No documentation update needed for this PR.', 'n/a'),
        }

    normalized_detected = [
        item if isinstance(item, Mapping) else {
            'path': item.path,
            'status': item.status,
            'content': item.content,
            'diff_hunk': item.diff_hunk,
            'kind': item.kind,
        }
        for item in detected
    ]
    impact = analyze_impact(normalized_detected, repo_state)
    if not impact.requires_generation and not impact.allowed_doc_paths:
        return {
            'status': 'no_op',
            'stage': 'analysis',
            'changed_files': [item.path for item in detected],
            'impact': impact,
            'check': set_check_status('success', 'No documentation update needed for this PR.', 'n/a'),
        }

    redacted = redact_corpus(corpus)
    if redacted.status == 'blocked':
        return {
            'status': 'fail',
            'stage': 'redaction',
            'validation': None,
            'redaction': redacted,
            'impact': impact,
            'check': set_check_status('failure', redacted.blocked_reason or 'Secret redaction blocked external AI processing.', 'n/a'),
        }

    validation = run_validators('pre_generation', pr_context, corpus, impact.allowed_doc_paths)
    if validation.status != 'pass':
        return {
            'status': 'fail',
            'stage': 'pre_generation',
            'validation': validation,
            'redaction': redacted,
            'impact': impact,
            'check': set_check_status('failure', 'Pre-generation validation failed.', 'n/a'),
        }

    processing_identity = compute_processing_identity(
        pr_context,
        impact.allowed_doc_paths,
        [
            {
                'path': item.path,
                'status': item.status,
                'content': item.content,
                'diff_hunk': item.diff_hunk,
                'kind': item.kind,
            }
            for item in detected
        ],
    )
    if resolve_existing_successful_processing(pr_context, processing_identity):
        return {
            'status': 'skipped',
            'stage': 'idempotent',
            'processing_identity': processing_identity,
            'impact': impact,
            'check': set_check_status('success', 'Documentation already processed for this PR state.', 'n/a'),
        }

    current_head_sha = _resolve_live_head(pr_context)
    if current_head_sha and is_stale_run(current_head_sha, pr_context.head_sha):
        return {
            'status': 'fail',
            'stage': 'stale_head',
            'processing_identity': processing_identity,
            'check': set_check_status('failure', 'Run rejected as stale because the PR head changed after capture.', 'n/a'),
        }

    approval = check_pr_approval_state(pr_context)
    if not approval.review_valid:
        return {
            'status': 'fail',
            'stage': 'approval',
            'approval': approval,
            'check': set_check_status('failure', 'Required GitHub review is not valid for the current PR state.', 'n/a'),
        }

    provider_key = str(pr_context.metadata.get('openai_api_key') or os.environ.get('OPENAI_API_KEY') or '').strip()
    if not provider_key and bool(pr_context.metadata.get('require_provider_auth', False)):
        return {
            'status': 'fail',
            'stage': 'provider_auth',
            'processing_identity': processing_identity,
            'approval': approval,
            'check': set_check_status('failure', 'Provider authentication is required for generation and is missing.', 'n/a'),
        }
    if not provider_key and not bool(pr_context.metadata.get('allow_synthetic_fallback', False)):
        return {
            'status': 'fail',
            'stage': 'provider_auth',
            'processing_identity': processing_identity,
            'approval': approval,
            'check': set_check_status('failure', 'Provider authentication is required for generation and is missing.', 'n/a'),
        }

    generation_request = GenerationRequest(
        pr_context=pr_context,
        input_corpus=corpus,
        affected_doc_paths=impact.allowed_doc_paths,
        redacted_corpus=redacted.redacted_content,
        processing_identity=processing_identity,
        allowed_doc_paths=impact.allowed_doc_paths,
    )
    generated_docs = generate_docs(generation_request)
    generated_corpus = {doc.path: doc.content for doc in generated_docs}
    post_validation = run_validators('post_generation', pr_context, generated_corpus, impact.allowed_doc_paths)
    if post_validation.status != 'pass':
        return {
            'status': 'fail',
            'stage': 'post_generation',
            'validation': post_validation,
            'generated_docs': generated_docs,
            'check': set_check_status('failure', 'Post-generation validation failed.', 'n/a'),
        }

    current_head_sha = _resolve_live_head(pr_context)
    if current_head_sha and is_stale_run(current_head_sha, pr_context.head_sha):
        return {
            'status': 'fail',
            'stage': 'stale_head',
            'processing_identity': processing_identity,
            'check': set_check_status('failure', 'PR head changed after generation; stale run aborted before commit.', 'n/a'),
        }

    commit_plan = CommitPlan(
        branch='main',
        base_sha=pr_context.base_sha,
        head_sha=pr_context.head_sha,
        files_to_update=impact.allowed_doc_paths,
        message='Update documentation for PR changes',
        footer='Docs-Generated-By: workflow-run',
        repo_path=pr_context.metadata.get('repo_path', ''),
        allowed_paths=list(impact.allowed_doc_paths),
    )
    commit_plan = prepare_commit(commit_plan, post_validation, pr_context)
    summary = write_atomic_commit(commit_plan)
    bundle = ArtifactBundle(
        workflow_run_id=pr_context.workflow_run_id,
        pr_number=pr_context.pr_number,
        head_sha=pr_context.head_sha,
        duration_seconds=1,
        changed_files=[item.path for item in detected],
        affected_docs=impact.allowed_doc_paths,
        validation_status=post_validation.status,
        final_check_state='success',
        commit_summary=summary,
    )
    artifact_link = publish_artifact(bundle)
    emit_log('info', 'Documentation sync workflow completed', workflow_run_id=pr_context.workflow_run_id, status='success')
    return {
        'status': 'success',
        'stage': 'complete',
        'processing_identity': processing_identity,
        'impact': impact,
        'redaction': redacted,
        'validation': post_validation,
        'commit_summary': summary,
        'artifact_uri': artifact_link,
        'check': set_check_status('success', 'Automated Documentation Check passed.', artifact_link),
    }


def process_pull_request(pr_context: PRContext, changed_files: list[dict[str, Any]], repo_state: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_documentation_sync(pr_context, changed_files=changed_files, repo_state=repo_state)
