from __future__ import annotations

from typing import List, Dict, Any

from pydantic import BaseModel, Field


class ArchitectureMap(BaseModel):
    detected_layers: List[str] = Field(default_factory=list)
    entrypoints: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    dependency_direction: str | None = None
    major_flows: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    risk_zones: List[str] = Field(default_factory=list)


class ModuleNode(BaseModel):
    module_id: str
    name: str
    path_patterns: List[str] = Field(default_factory=list)
    responsibility: str | None = None
    owned_files: List[str] = Field(default_factory=list)
    public_surface: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    key_classes: List[str] = Field(default_factory=list)
    key_functions: List[str] = Field(default_factory=list)
    risk_markers: List[str] = Field(default_factory=list)


class ClassNode(BaseModel):
    class_id: str
    name: str
    kind: str | None = None
    file_path: str
    line_range: tuple[int, int] | None = None
    owning_module: str | None = None
    responsibility: str | None = None
    public_methods: List[str] = Field(default_factory=list)
    state_fields: List[str] = Field(default_factory=list)
    collaborators: List[str] = Field(default_factory=list)
    risk_markers: List[str] = Field(default_factory=list)


class FunctionNode(BaseModel):
    function_id: str
    name: str
    qualified_path: str
    file_path: str
    line_range: tuple[int, int] | None = None
    owning_class: str | None = None
    owning_module: str | None = None
    signature: str | None = None
    visibility: str | None = None
    parameters: List[str] = Field(default_factory=list)
    return_type: str | None = None
    calls: List[str] = Field(default_factory=list)
    usages: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    risk_markers: List[str] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)


class RelationEdge(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0
    evidence: str | None = None
    source_location: str | None = None
