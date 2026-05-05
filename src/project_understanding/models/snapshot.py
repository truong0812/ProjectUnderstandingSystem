"""Snapshot package model for the shared knowledge schema.

A snapshot package contains all artifacts from a single ingest run.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from project_understanding.models.entities import File, Module, Repository, Snapshot, Symbol
from project_understanding.models.relations import Relation
from project_understanding.models.summaries import Summary
from project_understanding.models.conventions import Convention, RiskArea


class SnapshotPackage(BaseModel):
    """Complete knowledge snapshot package.

    Contains all entities, relations, and summaries from one ingest run.
    This is the top-level container that gets serialized to disk.
    """

    repository: Repository = Field(description="Source repository metadata")
    snapshot: Snapshot = Field(description="Snapshot metadata")
    files: list[File] = Field(default_factory=list, description="All files in the snapshot")
    modules: list[Module] = Field(default_factory=list, description="All modules in the snapshot")
    symbols: list[Symbol] = Field(default_factory=list, description="All symbols in the snapshot")
    relations: list[Relation] = Field(default_factory=list, description="All relations in the snapshot")
    summaries: list[Summary] = Field(default_factory=list, description="All summaries in the snapshot")
    conventions: list[Convention] = Field(default_factory=list, description="Detected conventions (Phase 3)")
    risks: list[RiskArea] = Field(default_factory=list, description="Detected risk areas (Phase 3)")
