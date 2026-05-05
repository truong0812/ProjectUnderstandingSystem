"""Summary model for the shared knowledge schema.

Summaries describe files, modules, and symbols at different levels of detail.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal
import hashlib

from pydantic import BaseModel, Field


class SummaryLevel(str, Enum):
    """Level of detail for a summary."""

    FILE = "file"
    MODULE = "module"
    SYMBOL = "symbol"


class SummarySource(str, Enum):
    """How the summary was generated."""

    HEURISTIC = "heuristic"
    LLM = "llm"


class Summary(BaseModel):
    """A structured summary for a file, module, or symbol.

    Summaries are stored separately from entities so they can be
    updated independently and consumed selectively by agent profiles.
    """

    summary_id: str = Field(description="Unique summary identifier")
    target_id: str = Field(description="ID of the entity being summarized")
    target_type: Literal["file", "module", "symbol"] = Field(
        description="Type of the entity being summarized",
    )
    content: str = Field(description="Summary text content")
    level: SummaryLevel = Field(description="Granularity level of the summary")
    generated_by: SummarySource = Field(
        default=SummarySource.LLM,
        description="How the summary was generated",
    )
    language: str = Field(
        default="",
        description="Programming language of the target (for file/symbol summaries)",
    )

    @staticmethod
    def make_summary_id(target_id: str, level: SummaryLevel) -> str:
        """Generate deterministic summary ID."""
        raw = f"summary:{target_id}:{level.value}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]