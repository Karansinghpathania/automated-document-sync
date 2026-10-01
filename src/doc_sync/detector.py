from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from .models import ChangedFile, PRContext


def classify_path(path: str) -> str:
    normalized = path.strip().replace('\\', '/')
    if normalized.startswith('docs/') or normalized.endswith('.md') or normalized in {'README.md', 'CHANGELOG.md'}:
        return 'docs'
    if normalized.startswith('src/') or normalized.endswith('.py') or normalized.endswith('.js') or normalized.endswith('.ts'):
        return 'code'
    if normalized.endswith('.yaml') or normalized.endswith('.yml') or normalized.endswith('.json'):
        return 'config'
    if normalized.endswith('.openapi.yaml') or normalized.endswith('.openapi.json') or 'openapi' in normalized.lower():
        return 'openapi'
    return 'unknown'


def detect_changes(pr_context: PRContext, raw_changes: Sequence[Mapping[str, object]] | Iterable[Mapping[str, object]]) -> list[ChangedFile]:
    """Convert raw GitHub-style change payloads into normalized ChangedFile entries."""
    detected: list[ChangedFile] = []
    for item in raw_changes:
        path = str(item.get('path') or item.get('file') or '')
        if not path:
            continue
        status = str(item.get('status') or 'modified')
        content = str(item.get('content') or item.get('diff') or '')
        diff_hunk = str(item.get('diff_hunk') or item.get('patch') or '')
        detected.append(
            ChangedFile(
                path=path.strip().replace('\\', '/'),
                status=status,
                content=content,
                diff_hunk=diff_hunk,
                kind=classify_path(path),
            )
        )
    return detected
