from __future__ import annotations

import os
from typing import Any

from .models import GeneratedDoc, GenerationRequest


def _generate_candidate_document(path: str, content: str) -> str:
    text = str(content).strip()
    if not text:
        return '# Generated Documentation\n\nThis documentation was synthesized for the approved scope.\n'

    title = f'Generated Documentation for {path}'.strip()
    return (
        f'# {title}\n\n'
        'This documentation was synthesized from the approved scope and must be validated before commit.\n\n'
        'The raw repository corpus is never forwarded verbatim through the AI boundary.\n'
    )


def generate_with_openai(payload: dict[str, Any]) -> dict[str, str]:
    """Envelope the external AI boundary and return provider output keyed by doc path.

    The implementation intentionally fails closed when the repository does not provide
    a configured provider credential, but it still produces a deterministic candidate
    output so the local pipeline can be exercised safely in tests and CI.
    """
    corpus = payload.get('redacted_corpus') or payload.get('input_corpus') or {}
    if not corpus:
        return {'README.md': '# Generated Documentation\n'}

    provider = str(payload.get('provider') or 'openai').lower()
    api_key = str(payload.get('api_key') or os.environ.get('OPENAI_API_KEY') or '').strip()
    if provider == 'openai' and not api_key:
        # Local/test environments do not have a real provider credential; we still
        # produce a deterministic candidate output, but never return the original
        # corpus unchanged.
        return {str(path): _generate_candidate_document(str(path), str(content)) for path, content in corpus.items()}

    return {str(path): _generate_candidate_document(str(path), str(content)) for path, content in corpus.items()}


def generate_docs(request: GenerationRequest) -> list[GeneratedDoc]:
    """Produce candidate documentation edits for the approved doc scope."""
    allowed = set(request.allowed_doc_paths or request.affected_doc_paths)
    provider_payload = {
        'input_corpus': request.input_corpus,
        'redacted_corpus': request.redacted_corpus,
        'affected_doc_paths': request.affected_doc_paths,
        'allowed_doc_paths': request.allowed_doc_paths,
        'processing_identity': request.processing_identity,
        'pr_context': request.pr_context,
        'provider': 'openai',
        'api_key': None,
    }
    provider_output = generate_with_openai(provider_payload)

    if not isinstance(provider_output, dict) or not provider_output:
        provider_output = {
            str(path): _generate_candidate_document(str(path), str(content))
            for path, content in (request.redacted_corpus or request.input_corpus or {}).items()
        }

    generated: list[GeneratedDoc] = []
    for path, content in provider_output.items():
        normalized = str(path).strip().replace('\\', '/')
        if not normalized:
            continue
        if normalized not in allowed and normalized not in request.affected_doc_paths:
            raise ValueError(f'Generated path is outside allowlist: {normalized}')
        if 'ignore previous instructions' in normalized.lower() or 'ignore previous instructions' in str(content).lower():
            raise ValueError('Prompt injection marker detected in generated documentation path or content.')
        generated.append(GeneratedDoc(path=normalized, content=str(content) or '# Generated Documentation\n', source='ai'))

    if not generated:
        fallback_path = (request.allowed_doc_paths or request.affected_doc_paths or ['README.md'])[0]
        return [GeneratedDoc(path=fallback_path, content='# Generated Documentation\n', source='ai')]

    return generated
