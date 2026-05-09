"""Pydantic model for layered summaries.

The ``LayeredSummary`` model captures structured summary information for a given
entity level (architecture, module, class, function). It is deliberately
lightweight – additional fields can be added later as needed.
"""

from __future__ import annotations

from typing import List, Dict, Any

from pydantic import BaseModel, Field


class LayeredSummary(BaseModel):
    level: str = Field(..., description="One of architecture, module, class, function")
    identifier: str = Field(..., description="Unique identifier for the entity being summarized")
    responsibility: str | None = None
    important_behavior: str | None = None
    dependencies: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    generated_by: str | None = None
    confidence: float = 1.0
    extra: Dict[str, Any] = Field(default_factory=dict)
