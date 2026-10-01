from __future__ import annotations

from .models import PRContext, ValidationResult


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

    for path, content in corpus.items():
        if not path.strip():
            errors.append('Document path cannot be empty.')
            continue
        normalized = path.strip().replace('\\', '/')
        if normalized.endswith('.md'):
            if not content.strip():
                errors.append(f'{normalized} is empty.')
                continue
            if '```' in content and content.count('```') % 2 != 0:
                errors.append(f'{normalized} has an unmatched fenced code block.')
            if normalized in impacted_docs and '# ' not in content and '## ' not in content:
                warnings.append(f'{normalized} has no heading markers; manual review may still be required.')

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
