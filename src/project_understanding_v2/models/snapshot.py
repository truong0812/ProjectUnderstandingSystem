from __future__ import annotations

from datetime import datetime
from typing import Dict, Any

from pydantic import BaseModel, Field


class RepositorySnapshot(BaseModel):
    """Metadata about the repository ingest operation."""

    repo_id: str = Field(..., description="Unique identifier for the repository")
    repo_path: str = Field(..., description="Local path or remote URL of the repo")
    branch: str | None = Field(None, description="Git branch name")
    commit_sha: str | None = Field(None, description="Commit SHA at ingest time")
    created_timestamp: datetime = Field(default_factory=datetime.utcnow)
    scan_stats: Dict[str, Any] = Field(default_factory=dict)
    quality_stats: Dict[str, Any] = Field(default_factory=dict)
