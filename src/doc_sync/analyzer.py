from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence, cast

from .detector import classify_path
from .models import ChangedFile, ImpactAnalysis


def analyze_impact(
    changed_files: Sequence[ChangedFile | Mapping[str, object]] | Iterable[ChangedFile | Mapping[str, object]],
    repo_state: Mapping[str, object] | None = None,
) -> ImpactAnalysis:
    """Map code/API changes to a safe documentation scope."""
    state = dict(repo_state or {})
    docs_values = cast(Sequence[Any], state.get('docs', []))
    source_values = cast(Sequence[Any], state.get('source', []))
    docs_index = set(str(item) for item in docs_values)
    source_index = set(str(item) for item in source_values)

    normalized: list[ChangedFile] = []
    for entry in changed_files:
        if isinstance(entry, ChangedFile):
            normalized.append(entry)
            continue
        mapping = cast(Mapping[str, object], entry)
        relative_path = str(mapping.get('path') or mapping.get('file') or '')
        normalized.append(
            ChangedFile(
                path=relative_path,
                status=str(mapping.get('status') or 'modified'),
                content=str(mapping.get('content') or ''),
                diff_hunk=str(mapping.get('diff_hunk') or ''),
                kind=classify_path(relative_path),
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
