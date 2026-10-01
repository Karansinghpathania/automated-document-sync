from __future__ import annotations

from .models import ApprovalStatus, PRContext


def check_pr_approval_state(pr_context: PRContext) -> ApprovalStatus:
    """Model the native GitHub approval boundary for the current PR state."""
    has_codeowners = bool(pr_context.metadata.get('has_codeowners', True))
    review_required = bool(pr_context.metadata.get('review_required', True))
    current_pr_state_matches_review = bool(pr_context.metadata.get('current_pr_state_matches_review', True))
    approved = bool(pr_context.metadata.get('approved', True))
    review_valid = has_codeowners and review_required and approved and current_pr_state_matches_review
    reason = 'Native GitHub review semantics should be enforced by repository configuration.'
    if not has_codeowners:
        reason = 'Missing or invalid CODEOWNERS configuration prevents approval enforcement.'
    elif not approved:
        reason = 'The PR is not approved by an authorized CODEOWNERS reviewer.'
    return ApprovalStatus(
        has_codeowners=has_codeowners,
        review_required=review_required,
        review_valid=review_valid,
        current_pr_state_matches_review=current_pr_state_matches_review,
        reason=reason,
    )


def set_check_status(status: str, summary: str, artifact_link: str) -> dict[str, str]:
    return {'status': status, 'summary': summary, 'artifact_link': artifact_link}
