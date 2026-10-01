from __future__ import annotations

from doc_sync.analyzer import analyze_impact


def test_analyze_impact_keeps_docs_scope_minimal_and_safe() -> None:
    impact = analyze_impact(
        [
            {'path': 'src/api.py', 'status': 'modified', 'content': 'def update_user(): pass'},
            {'path': 'README.md', 'status': 'modified', 'content': '# Demo'},
            {'path': '.github/workflows/ci.yml', 'status': 'modified', 'content': 'name: ci'},
        ],
        repo_state={'docs': ['README.md', 'docs/api.md'], 'source': ['src/api.py']},
    )

    assert impact.requires_generation is True
    assert 'README.md' in impact.allowed_doc_paths
    assert '.github/workflows/ci.yml' not in impact.allowed_doc_paths
    assert impact.reasoning
