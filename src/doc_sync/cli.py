from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from .models import PRContext
from .orchestrator import run_documentation_sync


def _collect_changed_files(repo_root: Path) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        files = []
        for item in result.stdout.splitlines():
            path = item.strip()
            if path:
                files.append({'path': path, 'status': 'modified'})
        return files
    except Exception:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description='Run the documentation synchronization pipeline.')
    parser.add_argument('--event', default='workflow_dispatch')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'demo/repo'))
    parser.add_argument('--head-sha', default=os.environ.get('PR_HEAD_SHA', 'local-head'))
    parser.add_argument('--base-sha', default=os.environ.get('PR_BASE_SHA', 'local-base'))
    parser.add_argument('--workflow-run-id', default=os.environ.get('WORKFLOW_RUN_ID', 'local-run'))
    parser.add_argument('--token', default=os.environ.get('GITHUB_TOKEN', ''))
    args = parser.parse_args()

    repo_root = Path.cwd()
    repo_name = args.repo
    owner, _, repo = repo_name.partition('/')
    pr_context = PRContext(
        repo=repo or repo_name,
        owner=owner or 'local',
        pr_number=int(os.environ.get('PR_NUMBER', '0') or 0),
        head_sha=args.head_sha,
        base_sha=args.base_sha,
        event_name=args.event,
        workflow_run_id=args.workflow_run_id,
        metadata={
            'has_codeowners': False,
            'review_required': False,
            'approved': False,
            'current_pr_state_matches_review': False,
            'repo_path': str(repo_root),
            'live_head_sha': args.head_sha,
            'workflow_token_present': bool(args.token),
        },
    )

    changed_files = _collect_changed_files(repo_root)
    repo_state = {'docs': ['README.md'], 'source': []}
    corpus = {'README.md': '# Documentation\n'}
    result = run_documentation_sync(pr_context, changed_files, repo_state, corpus)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result.get('status') in {'success', 'no_op', 'skipped'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
