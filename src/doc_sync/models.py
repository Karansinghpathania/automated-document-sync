from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PRContext:
    repo: str
    owner: str
    pr_number: int
    head_sha: str
    base_sha: str
    event_name: str = "pull_request"
    workflow_run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str = "modified"
    content: str = ""
    diff_hunk: str = ""
    kind: str = "unknown"


@dataclass(frozen=True)
class ImpactAnalysis:
    changed_files: list[ChangedFile]
    affected_docs: list[str]
    allowed_doc_paths: list[str]
    reasoning: str = ""
    requires_generation: bool = False


@dataclass(frozen=True)
class ValidationResult:
    phase: str
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deterministic: bool = True
    limitations: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    files_checked: list[str] = field(default_factory=list)
    blocking: bool = False
    human_review_required: bool = True


@dataclass(frozen=True)
class RedactionResult:
    status: str
    redacted_content: dict[str, str] = field(default_factory=dict)
    redacted_files: list[str] = field(default_factory=list)
    secret_count: int = 0
    failure_reason: str | None = None
    blocked_reason: str | None = None
    safe_to_send: bool = True

    def __post_init__(self) -> None:
        if self.blocked_reason is None and self.failure_reason is not None:
            object.__setattr__(self, 'blocked_reason', self.failure_reason)
        if self.status == 'blocked':
            object.__setattr__(self, 'safe_to_send', False)


@dataclass(frozen=True)
class ProcessingIdentity:
    pr_number: int
    head_sha: str
    canonical_input: str
    doc_state: str
    fingerprint: str
    canonical_input_fingerprint: str = ""
    relevant_doc_state_fingerprint: str = ""
    derived_key: str = ""

    def __post_init__(self) -> None:
        if not self.canonical_input_fingerprint:
            object.__setattr__(self, 'canonical_input_fingerprint', self.fingerprint)
        if not self.relevant_doc_state_fingerprint:
            object.__setattr__(self, 'relevant_doc_state_fingerprint', self.doc_state)
        if not self.derived_key:
            object.__setattr__(self, 'derived_key', self.fingerprint)


@dataclass(frozen=True)
class GeneratedDoc:
    path: str
    content: str
    source: str = "ai"


@dataclass(frozen=True)
class GenerationRequest:
    pr_context: PRContext
    input_corpus: dict[str, str]
    affected_doc_paths: list[str]
    redacted_corpus: dict[str, str]
    processing_identity: ProcessingIdentity
    allowed_doc_paths: list[str] | None = None


@dataclass(frozen=True)
class CommitPlan:
    branch: str
    base_sha: str
    head_sha: str
    files_to_update: list[str]
    message: str
    footer: str
    bot_identity: str = "github-actions[bot]"
    repo_path: str = ""
    allowed_paths: list[str] | None = None


@dataclass(frozen=True)
class ArtifactBundle:
    workflow_run_id: str
    pr_number: int
    head_sha: str
    duration_seconds: int
    ai_calls: int = 0
    retry_count: int = 0
    changed_files: list[str] = field(default_factory=list)
    affected_docs: list[str] = field(default_factory=list)
    validation_status: str = "pending"
    final_check_state: str = "pending"
    failure_reason: str | None = None
    stale_reason: str | None = None
    commit_summary: str | None = None


@dataclass(frozen=True)
class ApprovalStatus:
    has_codeowners: bool
    review_required: bool
    review_valid: bool
    current_pr_state_matches_review: bool
    reviewer: str = ""
    review_head_sha: str = ""
    reason: str = ""


def canonicalize(value: Mapping[str, Any] | Any) -> str:
    if isinstance(value, Mapping):
        return str(dict(sorted(value.items())))
    if isinstance(value, (list, tuple, set)):
        return str(sorted(str(item) for item in value))
    return str(value)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
