from __future__ import annotations

import subprocess
from pathlib import Path

from .models import CommitPlan, PRContext, ValidationResult


def prepare_commit(plan: CommitPlan, validation_result: ValidationResult, pr_context: PRContext) -> CommitPlan:
    """Build a commit plan once validation passes and the PR head remains fresh."""
    files = [path for path in plan.files_to_update if path.strip()]
    if validation_result.status != 'pass':
        raise ValueError('Validation failed; commit cannot proceed.')
    if not files:
        raise ValueError('No approved files selected for commit.')

    if plan.allowed_paths is not None:
        files = [path for path in files if path in plan.allowed_paths]
    if not files:
        raise ValueError('No approved files selected for commit.')

    footer = f"\n\nDocs-Generated-By: {pr_context.workflow_run_id or plan.bot_identity}"
    return CommitPlan(
        branch=plan.branch,
        base_sha=plan.base_sha,
        head_sha=plan.head_sha,
        files_to_update=files,
        message=plan.message,
        footer=footer,
        bot_identity=plan.bot_identity,
        repo_path=plan.repo_path,
        allowed_paths=plan.allowed_paths,
    )


def write_atomic_commit(commit_plan: CommitPlan) -> str:
    """Create a single atomic documentation commit in the working repository."""
    repo_root = Path(commit_plan.repo_path).resolve() if commit_plan.repo_path else None
    if repo_root is None or not repo_root.exists():
        return (
            f"{commit_plan.message}\n"
            f"Files: {', '.join(commit_plan.files_to_update)}\n"
            f"Footer: {commit_plan.footer.strip()}"
        )

    allowed = {str(path).replace('\\', '/').strip() for path in (commit_plan.allowed_paths or commit_plan.files_to_update)}
    file_set = {str(path).replace('\\', '/').strip() for path in commit_plan.files_to_update}
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

    commit_message = commit_plan.message
    footer = commit_plan.footer.strip()
    subprocess.run(['git', 'commit', '-m', commit_message, '-m', footer], cwd=repo_root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return (
        f"{commit_plan.message}\n"
        f"Files: {', '.join(commit_plan.files_to_update)}\n"
        f"Footer: {commit_plan.footer.strip()}"
    )
