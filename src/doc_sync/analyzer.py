from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from .detector import classify_path
from .models import ChangedFile, ImpactAnalysis


def analyze_impact(changed_files: Sequence[Mapping[str, object]] | Iterable[Mapping[str, object]], repo_state: Mapping[str, object] | None = None) -> ImpactAnalysis:
    """Map code/API changes to a safe documentation scope."""
    repo_state = repo_state or {}
    docs_index = set(str(item) for item in repo_state.get('docs', []))
    source_index = set(str(item) for item in repo_state.get('source', []))

    normalized: list[ChangedFile] = []
    for entry in changed_files:
        if isinstance(entry, ChangedFile):
            normalized.append(entry)
            continue
        normalized.append(
            ChangedFile(
                path=str(entry.get('path') or entry.get('file') or ''),
                status=str(entry.get('status') or 'modified'),
                content=str(entry.get('content') or ''),
                diff_hunk=str(entry.get('diff_hunk') or ''),
                kind=classify_path(str(entry.get('path') or entry.get('file') or '')),
            )
        )

    affected_docs: set[str] = set()
    allowed_doc_paths: set[str] = set()
    for item in normalized:
        path = item.path.strip().replace('\\', '/')
        if path in docs_index or path.endswith('.md') or path in {'README.md', 'CHANGELOG.md'}:
            affected_docs.add(path)
            allowed_doc_paths.add(path)
        elif path.startswith('docs/') or path.endswith('.yaml') or path.endswith('.yml') or path.endswith('.json'):
            if path.startswith('docs/') or path.endswith('.md'):
                affected_docs.add(path)
                allowed_doc_paths.add(path)
        elif path in source_index or path.startswith('src/'):
            candidate_docs = {'README.md'}
            allowed_doc_paths.update(candidate_docs)
            for doc in docs_index:
                if doc.startswith('docs/') or doc.endswith('.md'):
                    allowed_doc_paths.add(doc)

    for doc in docs_index:
        if doc.startswith('docs/') or doc.endswith('.md'):
            allowed_doc_paths.add(doc)

    default_allowlist = {'README.md'}
    if not allowed_doc_paths:
        allowed_doc_paths = default_allowlist.copy()

    affected_doc_list = sorted(affected_docs)
    allowed_doc_list = sorted(allowed_doc_paths)

    return ImpactAnalysis(
        changed_files=normalized,
        affected_docs=affected_doc_list,
        allowed_doc_paths=allowed_doc_list,
        reasoning='Relevant documentation scope was restricted to approved markdown and docs files only.',
        requires_generation=bool(normalized) and bool(allowed_doc_list),
    )
