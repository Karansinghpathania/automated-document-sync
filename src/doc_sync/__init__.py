"""Automated Documentation Sync package."""

from .analyzer import analyze_impact
from .artifacts import publish_artifact
from .committer import prepare_commit, write_atomic_commit
from .detector import detect_changes
from .generator import generate_docs
from .github_client import check_pr_approval_state, set_check_status
from .idempotency import compute_processing_identity, is_stale_run, resolve_existing_successful_processing
from .models import (
    ApprovalStatus,
    ArtifactBundle,
    ChangedFile,
    CommitPlan,
    GenerationRequest,
    ImpactAnalysis,
    PRContext,
    ProcessingIdentity,
    RedactionResult,
    ValidationResult,
)
from .orchestrator import process_pull_request, run_documentation_sync
from .redactor import redact_corpus
from .validator import run_validators

__version__ = "0.1.0"
__all__ = [
    'ApprovalStatus',
    'ArtifactBundle',
    'ChangedFile',
    'CommitPlan',
    'GenerationRequest',
    'ImpactAnalysis',
    'PRContext',
    'ProcessingIdentity',
    'RedactionResult',
    'ValidationResult',
    'analyze_impact',
    'check_pr_approval_state',
    'compute_processing_identity',
    'detect_changes',
    'generate_docs',
    'is_stale_run',
    'prepare_commit',
    'process_pull_request',
    'publish_artifact',
    'redact_corpus',
    'resolve_existing_successful_processing',
    'run_documentation_sync',
    'run_validators',
    'set_check_status',
    'write_atomic_commit',
]