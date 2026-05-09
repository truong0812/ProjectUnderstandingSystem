"""Layered knowledge models for Project Understanding V2."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def stable_id(*parts: str) -> str:
    """Create a stable short identifier from text parts."""
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:16]


class FileCategory(str, Enum):
    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCS = "docs"
    ASSET = "asset"
    UNKNOWN = "unknown"


class SymbolKind(str, Enum):
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    COMPONENT = "component"


class RelationType(str, Enum):
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    USES = "uses"
    DEPENDS_ON = "depends_on"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"


class RepositoryInfo(BaseModel):
    repo_id: str
    root_path: str
    branch: str = "unknown"
    commit_sha: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FileNode(BaseModel):
    file_id: str
    path: str
    language: str = "unknown"
    category: FileCategory = FileCategory.UNKNOWN
    size: int = 0
    hash: str = ""


class FunctionNode(BaseModel):
    function_id: str
    name: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    owning_class_id: str | None = None
    owning_module_id: str | None = None
    signature: str = ""
    visibility: str = "public"
    parameters: list[str] = Field(default_factory=list)
    return_type: str = ""
    calls: list[str] = Field(default_factory=list)
    uses: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    risk_markers: list[str] = Field(default_factory=list)


class ClassNode(BaseModel):
    class_id: str
    name: str
    kind: SymbolKind = SymbolKind.CLASS
    file_path: str
    line_start: int
    line_end: int
    owning_module_id: str | None = None
    responsibility: str = ""
    public_methods: list[str] = Field(default_factory=list)
    state_fields: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    risk_markers: list[str] = Field(default_factory=list)


class ModuleNode(BaseModel):
    module_id: str
    name: str
    path_patterns: list[str] = Field(default_factory=list)
    responsibility: str = ""
    owned_files: list[str] = Field(default_factory=list)
    public_surface: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    key_classes: list[str] = Field(default_factory=list)
    key_functions: list[str] = Field(default_factory=list)
    risk_markers: list[str] = Field(default_factory=list)


class ArchitectureLayer(BaseModel):
    name: str
    responsibility: str
    modules: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class ArchitectureMap(BaseModel):
    layers: list[ArchitectureLayer] = Field(default_factory=list)
    entrypoints: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    dependency_direction: list[str] = Field(default_factory=list)
    risk_zones: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class RelationEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: RelationType
    confidence: float = 1.0
    evidence: str = ""
    source_location: str = ""


class LayeredSummary(BaseModel):
    summary_id: str
    target_id: str
    level: str
    responsibility: str = ""
    important_behavior: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    generated_by: str = "heuristic"
    confidence: float = 0.7


class QualityReport(BaseModel):
    files_scanned: int = 0
    files_parsed: int = 0
    files_skipped: int = 0
    unknown_language_count: int = 0
    parser_error_count: int = 0
    class_count: int = 0
    function_count: int = 0
    module_count: int = 0
    relation_count_by_type: dict[str, int] = Field(default_factory=dict)
    architecture_confidence: float = 0.0
    summary_coverage_by_level: dict[str, int] = Field(default_factory=dict)
    llm_success_count: int = 0
    llm_fallback_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class LayeredSnapshot(BaseModel):
    repository: RepositoryInfo
    architecture: ArchitectureMap = Field(default_factory=ArchitectureMap)
    files: list[FileNode] = Field(default_factory=list)
    modules: list[ModuleNode] = Field(default_factory=list)
    classes: list[ClassNode] = Field(default_factory=list)
    functions: list[FunctionNode] = Field(default_factory=list)
    relations: list[RelationEdge] = Field(default_factory=list)
    summaries: list[LayeredSummary] = Field(default_factory=list)
    quality: QualityReport = Field(default_factory=QualityReport)


class ReviewContext(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    changed_functions: list[FunctionNode] = Field(default_factory=list)
    containing_classes: list[ClassNode] = Field(default_factory=list)
    owning_modules: list[ModuleNode] = Field(default_factory=list)
    architecture_layers: list[ArchitectureLayer] = Field(default_factory=list)
    direct_callers: list[FunctionNode] = Field(default_factory=list)
    direct_callees: list[FunctionNode] = Field(default_factory=list)
    reverse_dependencies: list[FileNode] = Field(default_factory=list)
    risk_markers: list[str] = Field(default_factory=list)
    conventions: list[str] = Field(default_factory=list)
    review_checklist: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
