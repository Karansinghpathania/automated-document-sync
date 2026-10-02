from __future__ import annotations

from .models import ApprovalStatus, PRContext


def check_pr_approval_state(pr_context: PRContext) -> ApprovalStatus:
    """Validate the PR approval boundary using the current GitHub review metadata.

    This implementation is intentionally fail-closed. Missing CODEOWNERS, missing
    approval, stale review heads, or failed GitHub API metadata all cause the PR
    to fail the approval gate instead of defaulting to pass.
    """
    metadata = pr_context.metadata or {}

    has_codeowners = bool(metadata.get('has_codeowners', False))
    review_required = bool(metadata.get('review_required', False))
    approved = bool(metadata.get('approved', False))
    current_pr_state_matches_review = bool(metadata.get('current_pr_state_matches_review', False))
    review_head_sha = str(metadata.get('review_head_sha') or '').strip()
    reviewer = str(metadata.get('reviewer') or '').strip()
    current_head_sha = str(pr_context.head_sha or '').strip()

    if not metadata:
        reason = 'Missing GitHub approval metadata: CODEOWNERS review state is not available for the current PR head.'
    elif not has_codeowners:
        reason = 'Missing or invalid CODEOWNERS configuration prevents approval enforcement.'
    elif not review_required:
        reason = 'The repository does not declare a required CODEOWNERS review for this PR.'
    elif not approved:
        reason = 'The PR is not approved by an authorized CODEOWNERS reviewer.'
    elif review_head_sha and current_head_sha and review_head_sha != current_head_sha:
        reason = 'The approval is stale for the current PR head SHA and cannot be used to approve the latest state.'
        current_pr_state_matches_review = False
    elif not current_pr_state_matches_review:
        reason = 'The current PR state does not match the approved review state.'
    else:
        reason = 'Native GitHub review requirements are satisfied for the current PR state.'

    review_valid = (
        has_codeowners
        and review_required
        and approved
        and current_pr_state_matches_review
        and (not review_head_sha or review_head_sha == current_head_sha)
    )

    return ApprovalStatus(
        has_codeowners=has_codeowners,
        review_required=review_required,
        review_valid=review_valid,
        current_pr_state_matches_review=current_pr_state_matches_review,
        reviewer=reviewer,
        review_head_sha=review_head_sha,
        reason=reason,
    )


def set_check_status(status: str, summary: str, artifact_link: str) -> dict[str, str]:
    return {'status': status, 'summary': summary, 'artifact_link': artifact_link}
