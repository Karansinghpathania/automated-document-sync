from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

from .models import PRContext, to_jsonable
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


def _github_request_json(url: str, token: str) -> object:
    request = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'documentation-sync/1.0',
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def _collect_github_pr_metadata(owner: str, repo: str, pr_number: int, token: str, current_head_sha: str | None = None) -> dict[str, object]:
    metadata: dict[str, object] = {
        'has_codeowners': False,
        'review_required': False,
        'approved': False,
        'current_pr_state_matches_review': False,
        'review_head_sha': '',
        'reviewer': '',
        'repo_path': str(Path.cwd()),
        'live_head_sha': current_head_sha or '',
        'workflow_token_present': bool(token),
    }
    if not token or not owner or not repo or not pr_number:
        return metadata

    candidates = ['.github/CODEOWNERS', 'CODEOWNERS']
    for candidate in candidates:
        url = f'https://api.github.com/repos/{owner}/{repo}/contents/{candidate}'
        try:
            _github_request_json(url, token)
            metadata['has_codeowners'] = True
            metadata['review_required'] = True
            break
        except Exception:
            continue

    try:
        reviews_url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews'
        reviews = _github_request_json(reviews_url, token)
        if isinstance(reviews, list):
            approved_reviews = [review for review in reviews if str(review.get('state', '')).upper() == 'APPROVED']
            if approved_reviews:
                latest = max(approved_reviews, key=lambda review: str(review.get('submitted_at') or ''))
                metadata['approved'] = True
                metadata['reviewer'] = str(latest.get('user', {}).get('login') or '').strip()
                metadata['review_head_sha'] = str(latest.get('commit_id') or '').strip()
                head_sha = str(current_head_sha or '').strip()
                if head_sha and str(metadata['review_head_sha']) == head_sha:
                    metadata['current_pr_state_matches_review'] = True
                elif not head_sha:
                    metadata['current_pr_state_matches_review'] = True
    except Exception:
        pass

    return metadata


def _resolve_pr_number(event_name: str, input_pr_number: int | None = None) -> int:
    if event_name == 'pull_request':
        env_value = os.environ.get('PR_NUMBER', '').strip()
        if env_value.isdigit() and int(env_value) > 0:
            return int(env_value)
        if isinstance(input_pr_number, int) and input_pr_number > 0:
            return input_pr_number
        ref = os.environ.get('GITHUB_REF', '').strip()
        match = re.search(r'/pull/(\d+)(?:/|$)', ref)
        if match:
            return int(match.group(1))
        return 0

    if isinstance(input_pr_number, int) and input_pr_number > 0:
        return input_pr_number

    env_value = os.environ.get('PR_NUMBER', '').strip()
    if env_value.isdigit() and int(env_value) > 0:
        return int(env_value)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Run the documentation synchronization pipeline.')
    parser.add_argument('--event', default='workflow_dispatch')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'demo/repo'))
    parser.add_argument('--head-sha', default=os.environ.get('PR_HEAD_SHA', 'local-head'))
    parser.add_argument('--base-sha', default=os.environ.get('PR_BASE_SHA', 'local-base'))
    parser.add_argument('--workflow-run-id', default=os.environ.get('WORKFLOW_RUN_ID', 'local-run'))
    parser.add_argument('--token', default=os.environ.get('GITHUB_TOKEN', ''))
    parser.add_argument('--pr-number', type=int, default=0)
    args = parser.parse_args()

    resolved_pr_number = _resolve_pr_number(args.event, args.pr_number)
    if resolved_pr_number <= 0:
        raise SystemExit(
            'Documentation sync requires a valid PR number. Real pull_request events must provide github.event.pull_request.number; '
            'workflow_dispatch requires an explicit pr_number input and may not run with PR_NUMBER=0.'
        )

    repo_root = Path.cwd()
    repo_name = args.repo
    owner, _, repo = repo_name.partition('/')
    metadata = _collect_github_pr_metadata(owner or 'local', repo or repo_name, resolved_pr_number, args.token, args.head_sha)
    pr_context = PRContext(
        repo=repo or repo_name,
        owner=owner or 'local',
        pr_number=resolved_pr_number,
        head_sha=args.head_sha,
        base_sha=args.base_sha,
        event_name=args.event,
        workflow_run_id=args.workflow_run_id,
        metadata={
            **metadata,
            'repo_path': str(repo_root),
            'live_head_sha': args.head_sha,
            'workflow_token_present': bool(args.token),
        },
    )

    changed_files = _collect_changed_files(repo_root)
    repo_state = {'docs': ['README.md'], 'source': []}
    corpus = {'README.md': '# Documentation\n'}
    result = run_documentation_sync(pr_context, changed_files, repo_state, corpus)
    print(json.dumps(to_jsonable(result), sort_keys=True, indent=2))
    return 0 if result.get('status') in {'success', 'no_op', 'skipped'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
