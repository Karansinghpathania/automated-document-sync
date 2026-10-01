from __future__ import annotations

from .models import ArtifactBundle


def publish_artifact(bundle: ArtifactBundle) -> str:
    """Create a private artifact URI for a workflow run."""
    return f"artifacts/{bundle.workflow_run_id}/bundle.json"
