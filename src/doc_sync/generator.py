from __future__ import annotations

from .models import GeneratedDoc, GenerationRequest


def generate_docs(request: GenerationRequest) -> list[GeneratedDoc]:
    """Produce candidate documentation edits for the approved doc scope."""
    allowed = set(request.allowed_doc_paths or request.affected_doc_paths)
    generated: list[GeneratedDoc] = []

    for path, content in request.redacted_corpus.items():
        normalized = path.strip().replace('\\', '/')
        if normalized not in allowed and normalized not in request.affected_doc_paths:
            raise ValueError(f'Generated path is outside allowlist: {normalized}')
        if 'ignore previous instructions' in normalized.lower() or 'ignore previous instructions' in content.lower():
            raise ValueError('Prompt injection marker detected in generated documentation path or content.')
        generated.append(GeneratedDoc(path=normalized, content=content or '# Generated Documentation\n', source='ai'))

    if not generated:
        return [GeneratedDoc(path='README.md', content='# Generated Documentation\n', source='ai')]

    return generated
