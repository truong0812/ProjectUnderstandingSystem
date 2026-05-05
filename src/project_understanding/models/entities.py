"""Entity models for the shared knowledge schema.

Core entities: Repository, Snapshot, File, Module, Symbol.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class SymbolKind(str, Enum):
    """Kind of symbol extracted from source code."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE = "type"
    CONSTANT = "constant"
    ENUM = "enum"
    STRUCT = "struct"
    PROPERTY = "property"
    FIELD = "field"
    NAMESPACE = "namespace"
    VARIABLE = "variable"
    CONSTRUCTOR = "constructor"
    DELEGATE = "delegate"


class Repository(BaseModel):
    """Repository identity and metadata."""

    repo_id: str = Field(description="Unique repository identifier")
    url: str = Field(default="", description="Repository remote URL")
    branch: str = Field(default="main", description="Current branch")
    commit_sha: str = Field(default="", description="Current commit SHA")
    ingested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp of ingestion",
    )


class SnapshotStatus(str, Enum):
    """Status of a knowledge snapshot."""

    CREATING = "creating"
    COMPLETE = "complete"
    FAILED = "failed"


class Snapshot(BaseModel):
    """Represents a knowledge snapshot of the repository at a point in time."""

    snapshot_id: str = Field(description="Unique snapshot identifier")
    repo_id: str = Field(description="Parent repository ID")
    branch: str = Field(default="main")
    commit_sha: str = Field(default="")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    status: SnapshotStatus = Field(default=SnapshotStatus.CREATING)
    file_count: int = Field(default=0, description="Number of files in snapshot")
    symbol_count: int = Field(default=0, description="Number of symbols extracted")
    relation_count: int = Field(default=0, description="Number of relations built")
    summary_count: int = Field(default=0, description="Number of summaries generated")

    @staticmethod
    def make_snapshot_id(repo_id: str, branch: str, commit_sha: str) -> str:
        """Generate deterministic snapshot ID."""
        raw = f"{repo_id}:{branch}:{commit_sha}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class File(BaseModel):
    """A source code file in the repository."""

    file_id: str = Field(description="Unique file identifier")
    snapshot_id: str = Field(description="Parent snapshot ID")
    path: str = Field(description="Relative file path from repo root")
    language: str = Field(default="unknown", description="Detected programming language")
    hash: str = Field(default="", description="Content hash (SHA-256)")
    size: int = Field(default=0, description="File size in bytes")
    is_entrypoint: bool = Field(default=False, description="Whether this is an entry point file")
    is_test: bool = Field(default=False, description="Whether this is a test file")
    is_config: bool = Field(default=False, description="Whether this is a config file")

    @staticmethod
    def make_file_id(repo_id: str, path: str, content_hash: str) -> str:
        """Generate deterministic file ID."""
        normalized = path.replace("\\", "/")
        raw = f"{repo_id}:{normalized}:{content_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Module(BaseModel):
    """Logical grouping of files (namespace, package, directory)."""

    module_id: str = Field(description="Unique module identifier")
    snapshot_id: str = Field(description="Parent snapshot ID")
    name: str = Field(description="Module name")
    path_pattern: str = Field(default="", description="Directory or glob pattern for this module")
    files: list[str] = Field(default_factory=list, description="List of file IDs in this module")
    description: str = Field(default="", description="Brief description of module purpose")

    @staticmethod
    def make_module_id(repo_id: str, name: str) -> str:
        """Generate deterministic module ID."""
        raw = f"{repo_id}:module:{name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class Symbol(BaseModel):
    """A named code construct: function, class, method, etc."""

    symbol_id: str = Field(description="Unique symbol identifier")
    file_id: str = Field(description="Parent file ID")
    name: str = Field(description="Symbol name")
    kind: SymbolKind = Field(description="Type of symbol")
    path: str = Field(description="Qualified name (e.g., module.ClassName.method)")
    line_start: int = Field(default=0, description="Start line number (1-based)")
    line_end: int = Field(default=0, description="End line number (1-based)")
    hash: str = Field(default="", description="Content hash of the symbol body")
    visibility: str = Field(default="unknown", description="Visibility: public, private, protected, internal")
    is_async: bool = Field(default=False, description="Whether this is an async symbol")
    is_static: bool = Field(default=False, description="Whether this is a static symbol")
    parameters: list[str] = Field(default_factory=list, description="Parameter names")
    return_type: str = Field(default="", description="Return type annotation")
    docstring: str = Field(default="", description="Docstring or comment")

    @staticmethod
    def make_symbol_id(repo_id: str, file_path: str, symbol_path: str, symbol_hash: str) -> str:
        """Generate deterministic symbol ID."""
        normalized = file_path.replace("\\", "/")
        raw = f"{repo_id}:{normalized}:{symbol_path}:{symbol_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]