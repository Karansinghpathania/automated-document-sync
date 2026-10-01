from __future__ import annotations

from .models import ApprovalStatus, PRContext


def check_pr_approval_state(pr_context: PRContext) -> ApprovalStatus:
    """Model the native GitHub approval boundary for the current PR state.

    The default is intentionally fail-closed: if the required review metadata is
    missing or inconsistent, the workflow must not treat the PR as approved.
    """
    metadata = pr_context.metadata or {}

    has_codeowners = bool(metadata.get('has_codeowners', False))
    review_required = bool(metadata.get('review_required', False))
    approved = bool(metadata.get('approved', False))
    current_pr_state_matches_review = bool(metadata.get('current_pr_state_matches_review', False))

    review_valid = has_codeowners and review_required and approved and current_pr_state_matches_review

    if not metadata:
        reason = 'Missing GitHub approval metadata: CODEOWNERS review state is not available for the current PR head.'
    elif not has_codeowners:
        reason = 'Missing or invalid CODEOWNERS configuration prevents approval enforcement.'
    elif not review_required:
        reason = 'The repository does not declare a required CODEOWNERS review for this PR.'
    elif not approved:
        reason = 'The PR is not approved by an authorized CODEOWNERS reviewer.'
    elif not current_pr_state_matches_review:
        reason = 'The current PR state does not match the approved review state.'
    else:
        reason = 'Native GitHub review requirements are satisfied for the current PR state.'

    return ApprovalStatus(
        has_codeowners=has_codeowners,
        review_required=review_required,
        review_valid=review_valid,
        current_pr_state_matches_review=current_pr_state_matches_review,
        reason=reason,
    )


def set_check_status(status: str, summary: str, artifact_link: str) -> dict[str, str]:
    return {'status': status, 'summary': summary, 'artifact_link': artifact_link}
