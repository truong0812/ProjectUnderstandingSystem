"""Pydantic model for review context.

Matches the fields described in the layered rebuild plan.
"""

from __future__ import annotations

from typing import List, Dict, Any

from pydantic import BaseModel, Field


class ReviewContext(BaseModel):
    changed_files: List[str] = Field(default_factory=list)
    changed_symbols: List[str] = Field(default_factory=list)
    containing_classes: List[str] = Field(default_factory=list)
    owning_modules: List[str] = Field(default_factory=list)
    architecture_layers: List[str] = Field(default_factory=list)
    direct_callers: List[str] = Field(default_factory=list)
    direct_callees: List[str] = Field(default_factory=list)
    reverse_dependencies: List[str] = Field(default_factory=list)
    risk_markers: List[str] = Field(default_factory=list)
    conventions: List[str] = Field(default_factory=list)
    review_checklist: List[str] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
