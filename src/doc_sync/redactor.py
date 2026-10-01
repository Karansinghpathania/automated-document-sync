from __future__ import annotations

import re

from .models import RedactionResult


_SECRET_PATTERNS = [
    re.compile(r'(?i)gh[pousr]_[A-Za-z0-9_]{8,}'),
    re.compile(r'(?i)github_pat_[A-Za-z0-9_]{8,}'),
    re.compile(r'(?i)(?:AKIA|ASIA)[0-9A-Z]{12,}'),
    re.compile(r'(?i)(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*["\']?[^\s\n"\']+'),
    re.compile(r'(?i)(?:https?://)(?:[^\s:@/]+):([^@\s/]+)@'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(r'(?i)(?:mongodb|postgres(?:ql)?|mysql|redis|amqp|postgresql)://[^\s]+'),
]

_RESIDUAL_PATTERNS = [
    re.compile(r'(?i)gh[pousr]_[A-Za-z0-9_]{8,}'),
    re.compile(r'(?i)github_pat_[A-Za-z0-9_]{8,}'),
    re.compile(r'(?i)(?:AKIA|ASIA)[0-9A-Z]{12,}'),
    re.compile(r'(?i)\b(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*[^\s\n]+'),
]


def _redact_line(line: str) -> str:
    if re.search(r'(?i)\b(?:password|passwd|token|secret|api[_-]?key)\b', line) and re.search(r'(?i)(gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|(?:AKIA|ASIA)[0-9A-Z]{12,})', line):
        return '[REDACTED]'

    redacted = line
    redacted = re.sub(r'(?i)(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*["\']?[^\s\n"\']+["\']?', '[REDACTED]', redacted)
    redacted = re.sub(r'(?i)(https?://)([^\s:@/]+):([^@\s/]+)@', r'\1[REDACTED]@', redacted)
    redacted = re.sub(r'(?i)gh[pousr]_[A-Za-z0-9_]{8,}', '[REDACTED]', redacted)
    redacted = re.sub(r'(?i)github_pat_[A-Za-z0-9_]{8,}', '[REDACTED]', redacted)
    redacted = re.sub(r'(?i)(?:AKIA|ASIA)[0-9A-Z]{12,}', '[REDACTED]', redacted)
    redacted = re.sub(r'(?i)(?:mongodb|postgres(?:ql)?|mysql|redis|amqp|postgresql)://[^\s]+', '[REDACTED]', redacted)
    return redacted


def redact_corpus(corpus: dict[str, str]) -> RedactionResult:
    """Redact obvious secrets from a corpus before moving to external AI processing."""
    redacted: dict[str, str] = {}
    secret_count = 0
    blocked_reason: str | None = None

    for path, content in corpus.items():
        updated = '\n'.join(_redact_line(line) for line in str(content).splitlines())
        found = any(pattern.search(updated) for pattern in _RESIDUAL_PATTERNS)
        if found:
            blocked_reason = f'Unsafe secret candidate remains in {path}. Transmission is blocked.'
            redacted[path] = re.sub(r'(?i)(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*.*', '[REDACTED]', updated)
            continue
        if any(pattern.search(content) for pattern in _SECRET_PATTERNS):
            secret_count += 1
        redacted[path] = updated

    if blocked_reason:
        return RedactionResult(
            status='blocked',
            redacted_content=redacted,
            redacted_files=list(redacted),
            secret_count=secret_count,
            failure_reason=blocked_reason,
            blocked_reason=blocked_reason,
            safe_to_send=False,
        )

    if secret_count:
        return RedactionResult(
            status='redacted',
            redacted_content=redacted,
            redacted_files=list(redacted),
            secret_count=secret_count,
            failure_reason=None,
            blocked_reason=None,
            safe_to_send=True,
        )

    return RedactionResult(
        status='not_required',
        redacted_content=redacted,
        redacted_files=[],
        secret_count=0,
        failure_reason=None,
        blocked_reason=None,
        safe_to_send=True,
    )
