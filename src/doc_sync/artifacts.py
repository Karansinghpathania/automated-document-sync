from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ArtifactBundle


def publish_artifact(bundle: ArtifactBundle) -> str:
    """Create a structured private artifact bundle for the workflow run."""
    base_dir = Path(os.environ.get('RUNNER_TEMP', '.')) / 'artifacts' / str(bundle.workflow_run_id)
    base_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        'workflow_run_id': bundle.workflow_run_id,
        'repository': os.environ.get('GITHUB_REPOSITORY', 'unknown/repository'),
        'pull_request': bundle.pr_number,
        'captured_head_sha': bundle.head_sha,
        'final_head_sha': bundle.head_sha,
        'processing_identity': f'pr-{bundle.pr_number}:{bundle.head_sha}',
        'started_at': None,
        'completed_at': None,
        'duration_seconds': bundle.duration_seconds,
        'files_analyzed': bundle.changed_files,
        'documents_changed': bundle.affected_docs,
        'ai': {
            'provider': 'openai',
            'attempts': max(bundle.ai_calls, 1),
            'retry_reason': None,
        },
        'validation': {
            'status': bundle.validation_status,
            'checks': [],
            'human_review_required': bundle.final_check_state != 'failure',
        },
        'approval': {
            'status': 'unknown',
            'reviewer': None,
            'head_sha': bundle.head_sha,
        },
        'commit': {
            'created': bool(bundle.commit_summary),
            'sha': None,
        },
        'result': bundle.final_check_state,
        'failure': bundle.failure_reason,
        'stale_reason': bundle.stale_reason,
    }
    artifact_path = base_dir / 'bundle.json'
    artifact_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
    return str(artifact_path)
