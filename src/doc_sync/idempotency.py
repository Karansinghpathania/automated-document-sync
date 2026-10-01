from __future__ import annotations

import hashlib
from typing import Iterable, Mapping, Sequence

from .models import PRContext, ProcessingIdentity


def _normalize(item: object) -> str:
    if isinstance(item, Mapping):
        items = []
        for key in sorted(item):
            items.append(f'{key}:{_normalize(item[key])}')
        return '|'.join(items)
    if isinstance(item, (list, tuple, set)):
        return '|'.join(_normalize(sub) for sub in sorted(str(sub) for sub in item))
    return str(item)


def compute_processing_identity(pr_context: PRContext, affected_docs: Sequence[str], changes: Sequence[Mapping[str, object]] | Iterable[Mapping[str, object]]) -> ProcessingIdentity:
    raw = {
        'repo': pr_context.repo,
        'pr_number': pr_context.pr_number,
        'head_sha': pr_context.head_sha,
        'docs': sorted(str(item) for item in affected_docs),
        'changes': [_normalize(item) for item in changes],
    }
    canonical = _normalize(raw)
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:32]
    return ProcessingIdentity(
        pr_number=pr_context.pr_number,
        head_sha=pr_context.head_sha,
        canonical_input=canonical,
        doc_state='|'.join(sorted(str(item) for item in affected_docs)),
        fingerprint=digest,
    )


def is_stale_run(current_head_sha: str, captured_head_sha: str) -> bool:
    return bool(current_head_sha and captured_head_sha and current_head_sha != captured_head_sha)


def resolve_existing_successful_processing(
    pr_context: PRContext,
    processing_identity: ProcessingIdentity,
    historical_commits: Sequence[Mapping[str, object]] | None = None,
) -> Mapping[str, object] | None:
    if historical_commits is None:
        return None
    for commit in historical_commits:
        if str(commit.get('pr_number')) == str(pr_context.pr_number):
            fingerprint = str(commit.get('fingerprint') or commit.get('processing_identity_fingerprint') or '')
            if fingerprint and fingerprint == processing_identity.fingerprint:
                return commit
    return None
