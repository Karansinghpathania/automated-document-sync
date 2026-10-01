from __future__ import annotations

import json
import re

from .models import PRContext, ValidationResult


def _relative_link_targets(content: str) -> list[str]:
    matches = re.findall(r'\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)', content)
    return [match.strip() for match in matches if match.strip()]


def _looks_like_openapi(path: str, content: str) -> bool:
    lowered = path.lower()
    if 'openapi' in lowered or 'swagger' in lowered:
        return True
    if lowered.endswith(('.json', '.yaml', '.yml')) and ('"openapi"' in content.lower() or "'openapi'" in content.lower() or 'swagger:' in content.lower()):
        return True
    return False


def _validate_openapi(path: str, content: str) -> list[str]:
    errors: list[str] = []
    if not _looks_like_openapi(path, content):
        return errors
    try:
        doc = json.loads(content)
    except json.JSONDecodeError as exc:
        errors.append(f'{path} is not valid JSON: {exc.msg}.')
        return errors
    if not isinstance(doc, dict):
        errors.append(f'{path} must contain a JSON object for the OpenAPI document.')
        return errors
    if 'openapi' not in doc and 'swagger' not in doc:
        errors.append(f'{path} is missing the required OpenAPI or Swagger version field.')
    return errors


def run_validators(phase: str, pr_context: PRContext, corpus: dict[str, str], impacted_docs: list[str]) -> ValidationResult:
    """Run deterministic documentation validation for the current phase."""
    errors: list[str] = []
    warnings: list[str] = []
    limitations: list[str] = []

    if not corpus:
        return ValidationResult(
            phase=phase,
            status='pass',
            errors=[],
            warnings=['No documentation content was generated; validation considered a no-op.'],
            deterministic=True,
            limitations=['No content to validate.'],
        )

    metadata = pr_context.metadata or {}
    changed_summary = metadata.get('changed_api_summary')
    documented_summary = metadata.get('documented_api_summary')
    if changed_summary is not None and documented_summary is not None:
        if str(changed_summary).strip() and str(documented_summary).strip() and str(changed_summary).strip() != str(documented_summary).strip():
            errors.append('Structural mismatch: the documented API summary does not match the changed API summary.')

    corpus_paths = {path.strip().replace('\\', '/') for path in corpus if str(path).strip()}
    for path, content in corpus.items():
        if not str(path).strip():
            errors.append('Document path cannot be empty.')
            continue
        normalized = str(path).strip().replace('\\', '/')
        text = str(content or '')

        if normalized.endswith('.md'):
            if not text.strip():
                errors.append(f'{normalized} is empty.')
                continue
            if '```' in text and text.count('```') % 2 != 0:
                errors.append(f'{normalized} has an unmatched fenced code block.')
            if normalized in impacted_docs and '# ' not in text and '## ' not in text:
                warnings.append(f'{normalized} has no heading markers; manual review may still be required.')
            for target in _relative_link_targets(text):
                if target.startswith(('http://', 'https://', 'mailto:')):
                    continue
                candidate = target.split('#', 1)[0].strip()
                if not candidate:
                    continue
                if candidate.startswith('/'):
                    errors.append(f'{normalized} contains an absolute-relative link that is not allowed: {candidate}')
                    continue
                resolved = ((normalized.rsplit('/', 1)[0] + '/' + candidate) if '/' in normalized else candidate).replace('\\', '/').replace('//', '/')
                if candidate.startswith('../'):
                    resolved = candidate
                if resolved not in corpus_paths and not any(candidate == doc for doc in corpus_paths):
                    errors.append(f'{normalized} links to a missing documentation file: {candidate}')
        elif _looks_like_openapi(normalized, text):
            errors.extend(_validate_openapi(normalized, text))

    if errors:
        return ValidationResult(
            phase=phase,
            status='fail',
            errors=errors,
            warnings=warnings,
            deterministic=True,
            limitations=limitations,
        )

    if not impacted_docs:
        limitations.append('No impacted documentation files were identified; validation was limited to the current corpus.')

    return ValidationResult(
        phase=phase,
        status='pass',
        errors=[],
        warnings=warnings,
        deterministic=True,
        limitations=limitations,
    )
