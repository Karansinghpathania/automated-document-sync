from __future__ import annotations

import subprocess
from pathlib import Path

from .models import CommitPlan, PRContext, ValidationResult


def _coerce_commit_plan(commit_plan: CommitPlan | dict[str, object]) -> CommitPlan:
    if isinstance(commit_plan, CommitPlan):
        return commit_plan
    return CommitPlan(
        branch=str(commit_plan.get('branch') or 'main'),
        base_sha=str(commit_plan.get('base_sha') or ''),
        head_sha=str(commit_plan.get('head_sha') or ''),
        files_to_update=[str(item) for item in commit_plan.get('files_to_update', [])],
        message=str(commit_plan.get('message') or 'Update documentation'),
        footer=str(commit_plan.get('footer') or 'Docs-Generated-By: workflow-run'),
        bot_identity=str(commit_plan.get('bot_identity') or 'github-actions[bot]'),
        repo_path=str(commit_plan.get('repo_path') or ''),
        allowed_paths=[str(item) for item in commit_plan.get('allowed_paths', [])],
    )


def _current_repo_head(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ''
    return result.stdout.strip()


def prepare_commit(plan: CommitPlan | dict[str, object], validation_result: ValidationResult, pr_context: PRContext) -> CommitPlan:
    """Build a commit plan once validation passes and the PR head remains fresh."""
    resolved = _coerce_commit_plan(plan)
    files = [path for path in resolved.files_to_update if path.strip()]
    if validation_result.status != 'pass':
        raise ValueError('Validation failed; commit cannot proceed.')
    if not files:
        raise ValueError('No approved files selected for commit.')

    if resolved.allowed_paths is not None:
        files = [path for path in files if path in resolved.allowed_paths]
    if not files:
        raise ValueError('No approved files selected for commit.')

    footer = f"\n\nDocs-Generated-By: {pr_context.workflow_run_id or resolved.bot_identity}"
    return CommitPlan(
        branch=resolved.branch,
        base_sha=resolved.base_sha,
        head_sha=resolved.head_sha,
        files_to_update=files,
        message=resolved.message,
        footer=footer,
        bot_identity=resolved.bot_identity,
        repo_path=resolved.repo_path,
        allowed_paths=resolved.allowed_paths,
    )


def write_atomic_commit(commit_plan: CommitPlan | dict[str, object]) -> str:
    """Create a single atomic documentation commit in the working repository."""
    resolved = _coerce_commit_plan(commit_plan)
    repo_root = Path(resolved.repo_path).resolve() if resolved.repo_path else None
    if repo_root is None or not repo_root.exists():
        return (
            f"{resolved.message}\n"
            f"Files: {', '.join(resolved.files_to_update)}\n"
            f"Footer: {resolved.footer.strip()}"
        )

    current_head = _current_repo_head(repo_root)
    if resolved.head_sha and current_head and current_head != resolved.head_sha:
        raise ValueError(
            f'Stale PR head detected: repository HEAD is {current_head}, expected {resolved.head_sha}.'
        )

    allowed = {str(path).replace('\\', '/').strip() for path in (resolved.allowed_paths or resolved.files_to_update)}
    file_set = {str(path).replace('\\', '/').strip() for path in resolved.files_to_update}
    if not file_set.issubset(allowed):
        raise ValueError('Commit attempted outside approved documentation paths.')

    for target in sorted(file_set):
        candidate = repo_root / target
        if not candidate.exists():
            raise ValueError(f'Cannot commit missing approved file: {target}')

    subprocess.run(['git', 'add', '--', *sorted(file_set)], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=repo_root, check=True, capture_output=True, text=True).stdout.splitlines()
    staged_set = {line.strip().replace('\\', '/') for line in staged if line.strip()}
    if not staged_set:
        raise ValueError('No documented files were staged for commit.')
    if staged_set - file_set:
        raise ValueError('Commit attempted to stage disallowed files.')

    commit_message = resolved.message
    footer = resolved.footer.strip()
    subprocess.run(['git', 'commit', '-m', commit_message, '-m', footer], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return (
        f"{resolved.message}\n"
        f"Files: {', '.join(resolved.files_to_update)}\n"
        f"Footer: {resolved.footer.strip()}"
    )
