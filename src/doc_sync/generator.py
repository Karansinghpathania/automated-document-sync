from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .models import GeneratedDoc, GenerationRequest


class TransientAIError(RuntimeError):
    pass


class ProviderAuthenticationError(RuntimeError):
    pass


class ProviderRequestError(RuntimeError):
    pass


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


class DocumentationGenerator:
    def generate(self, payload: dict[str, Any]) -> dict[str, str]:
        raise NotImplementedError


class OpenAIProvider(DocumentationGenerator):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def generate(self, payload: dict[str, Any]) -> dict[str, str]:
        if not self.api_key:
            raise ProviderAuthenticationError('OpenAI API key is not configured for provider execution.')
        return _call_with_one_retry(payload, self.api_key)


def _provider_call(payload: dict[str, Any], api_key: str) -> dict[str, str]:
    """Invoke the configured provider when credentials are available."""
    if not api_key:
        raise ProviderAuthenticationError('OpenAI API key is not configured for provider execution.')

    request_data = {
        'model': 'gpt-4o-mini',
        'input': [
            {'role': 'system', 'content': 'Generate documentation only for approved documentation files.'},
            {'role': 'user', 'content': json.dumps({'corpus': payload.get('redacted_corpus') or payload.get('input_corpus') or {}})},
        ],
    }
    body = json.dumps(request_data).encode('utf-8')
    req = urllib.request.Request(
        'https://api.openai.com/v1/responses',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode('utf-8')
            result = json.loads(raw)
    except urllib.error.HTTPError as exc:
        if exc.code >= 500:
            raise TransientAIError(f'Transient provider failure: {exc.code}') from exc
        if exc.code in {401, 403}:
            raise ProviderAuthenticationError('Provider authentication failed.') from exc
        raise ProviderRequestError(f'Provider request failed: {exc.code}') from exc
    except urllib.error.URLError as exc:
        raise TransientAIError(f'Network failure while contacting the provider: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise ProviderRequestError(f'Malformed provider response: {exc}') from exc

    output = result.get('output') or []
    if not output:
        raise ProviderRequestError('Provider response contained no output.')

    generated: dict[str, str] = {}
    for item in output:
        if not isinstance(item, dict):
            continue
        text = str(item.get('content') or item.get('text') or '').strip()
        if text:
            for path in payload.get('affected_doc_paths') or ['README.md']:
                generated[str(path)] = text
                break
    if not generated:
        raise ProviderRequestError('Provider output did not provide document text.')
    return generated


def _call_with_one_retry(payload: dict[str, Any], api_key: str) -> dict[str, str]:
    try:
        return _provider_call(payload, api_key)
    except TransientAIError:
        return _provider_call(payload, api_key)


def generate_with_openai(payload: dict[str, Any]) -> dict[str, str]:
    """Fail closed by default when no provider credentials are available."""
    corpus = payload.get('redacted_corpus') or payload.get('input_corpus') or {}
    if not corpus:
        return {'README.md': '# Generated Documentation\n'}

    provider = str(payload.get('provider') or 'openai').lower()
    if provider != 'openai':
        raise ProviderRequestError(f'Unsupported provider: {provider}')

    api_key = str(payload.get('api_key') or os.environ.get('OPENAI_API_KEY') or '').strip()
    if not api_key:
        raise ProviderAuthenticationError('OpenAI API key is not configured for provider execution.')

    try:
        return _call_with_one_retry(payload, api_key)
    except ProviderAuthenticationError:
        raise
    except ProviderRequestError:
        raise


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
        'api_key': request.pr_context.metadata.get('openai_api_key') or os.environ.get('OPENAI_API_KEY') or '',
        'strict': True,
        'require_provider_auth': bool(request.pr_context.metadata.get('require_provider_auth', False) or request.pr_context.metadata.get('strict_provider_auth', False)),
    }
    try:
        provider_output = generate_with_openai(provider_payload)
    except (ProviderAuthenticationError, ProviderRequestError, TransientAIError) as exc:
        if bool(request.pr_context.metadata.get('allow_synthetic_fallback', False)):
            provider_output = {
                str(path): _generate_candidate_document(str(path), str(content))
                for path, content in (request.redacted_corpus or request.input_corpus or {}).items()
            }
        else:
            raise ValueError('Documentation generation is blocked because provider authentication or output validation failed.') from exc

    if not isinstance(provider_output, dict) or not provider_output:
        raise ValueError('Provider output was empty; no documentation was generated.')

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
        raise ProviderRequestError('Provider output did not produce any approved documentation files.')

    return generated
