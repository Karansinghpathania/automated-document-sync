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
    checks: list[dict[str, object]] = []
    errors: list[str] = []
    warnings: list[str] = []
    limitations: list[str] = []
    files_checked: list[str] = []

    if not corpus:
        return ValidationResult(
            phase=phase,
            status='pass',
            errors=[],
            warnings=['No documentation content was generated; validation considered a no-op.'],
            deterministic=True,
            limitations=['No content to validate.'],
            checks=[{'name': 'empty_corpus', 'passed': True, 'file': 'n/a', 'message': 'No content was available for validation.'}],
            files_checked=[],
            blocking=False,
            human_review_required=True,
        )

    metadata = pr_context.metadata or {}
    changed_summary = metadata.get('changed_api_summary')
    documented_summary = metadata.get('documented_api_summary')
    if changed_summary is not None and documented_summary is not None:
        if str(changed_summary).strip() and str(documented_summary).strip() and str(changed_summary).strip() != str(documented_summary).strip():
            mismatch = 'Structural mismatch: the documented API summary does not match the changed API summary.'
            errors.append(mismatch)
            checks.append({'name': 'api_contract_mismatch', 'passed': False, 'file': 'api-contract', 'message': mismatch})
        else:
            checks.append({'name': 'api_contract_mismatch', 'passed': True, 'file': 'api-contract', 'message': 'Documented API summary matches the changed API summary.'})

    corpus_paths = {str(path).strip().replace('\\', '/') for path in corpus if str(path).strip()}
    for path, content in corpus.items():
        if not str(path).strip():
            errors.append('Document path cannot be empty.')
            checks.append({'name': 'path_validation', 'passed': False, 'file': 'n/a', 'message': 'Document path cannot be empty.'})
            continue
        normalized = str(path).strip().replace('\\', '/')
        files_checked.append(normalized)
        text = str(content or '')

        if normalized.endswith('.md'):
            if not text.strip():
                message = f'{normalized} is empty.'
                errors.append(message)
                checks.append({'name': 'markdown_content', 'passed': False, 'file': normalized, 'message': message})
                continue
            checks.append({'name': 'markdown_content', 'passed': True, 'file': normalized, 'message': 'Markdown content is non-empty.'})
            if '```' in text and text.count('```') % 2 != 0:
                message = f'{normalized} has an unmatched fenced code block.'
                errors.append(message)
                checks.append({'name': 'markdown_fence_validation', 'passed': False, 'file': normalized, 'message': message})
            else:
                checks.append({'name': 'markdown_fence_validation', 'passed': True, 'file': normalized, 'message': 'Fenced code blocks are balanced.'})
            if normalized in impacted_docs and '# ' not in text and '## ' not in text:
                message = f'{normalized} must include a markdown heading before it can be accepted.'
                errors.append(message)
                checks.append({'name': 'markdown_heading_validation', 'passed': False, 'file': normalized, 'message': message})
            else:
                checks.append({'name': 'markdown_heading_validation', 'passed': True, 'file': normalized, 'message': 'Markdown heading structure is acceptable.'})
            for target in _relative_link_targets(text):
                if target.startswith(('http://', 'https://', 'mailto:')):
                    continue
                candidate = target.split('#', 1)[0].strip()
                if not candidate:
                    continue
                if candidate.startswith('/'):
                    message = f'{normalized} contains an absolute-relative link that is not allowed: {candidate}'
                    errors.append(message)
                    checks.append({'name': 'relative_link_validation', 'passed': False, 'file': normalized, 'message': message})
                    continue
                resolved = ((normalized.rsplit('/', 1)[0] + '/' + candidate) if '/' in normalized else candidate).replace('\\', '/').replace('//', '/')
                if candidate.startswith('../'):
                    resolved = candidate
                if resolved not in corpus_paths and not any(candidate == doc for doc in corpus_paths):
                    message = f'{normalized} links to a missing documentation file: {candidate}'
                    errors.append(message)
                    checks.append({'name': 'relative_link_validation', 'passed': False, 'file': normalized, 'message': message})
                else:
                    checks.append({'name': 'relative_link_validation', 'passed': True, 'file': normalized, 'message': f'Link target resolved successfully: {candidate}'})
        elif _looks_like_openapi(normalized, text):
            openapi_errors = _validate_openapi(normalized, text)
            if openapi_errors:
                errors.extend(openapi_errors)
                for message in openapi_errors:
                    checks.append({'name': 'openapi_validation', 'passed': False, 'file': normalized, 'message': message})
            else:
                checks.append({'name': 'openapi_validation', 'passed': True, 'file': normalized, 'message': 'OpenAPI document structure is valid.'})

    if errors:
        return ValidationResult(
            phase=phase,
            status='fail',
            errors=errors,
            warnings=warnings,
            deterministic=True,
            limitations=limitations,
            checks=checks,
            files_checked=sorted(set(files_checked)),
            blocking=True,
            human_review_required=False,
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
        checks=checks,
        files_checked=sorted(set(files_checked)),
        blocking=False,
        human_review_required=True,
    )
