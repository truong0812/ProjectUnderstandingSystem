"""Relation model for the shared knowledge schema.

Relations describe connections between entities (imports, calls, contains, etc.).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    """Types of relations between entities."""

    # Phase 1 relations
    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    DEPENDS_ON = "depends_on"

    # Symbol-level usage (constant/variable/type references)
    USES = "uses"

    # Phase 3 relations (enrichment)
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    ENTRYPOINT_TO = "entrypoint_to"
    RELATED_TO = "related_to"


class Relation(BaseModel):
    """A directed relationship between two entities.

    Relations connect entities in the knowledge graph. Each relation has
    a source, target, type, and optional confidence/evidence.
    """

    source_id: str = Field(description="ID of the source entity")
    target_id: str = Field(description="ID of the target entity")
    relation_type: RelationType = Field(description="Type of relationship")
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0). Heuristic = 1.0, inferred < 1.0",
    )
    evidence: str = Field(
        default="",
        description="Human-readable evidence for this relation",
    )
    source_type: str = Field(
        default="",
        description="Entity type of source (File, Symbol, Module)",
    )
    target_type: str = Field(
        default="",
        description="Entity type of target (File, Symbol, Module)",
    )

    @property
    def is_structural(self) -> bool:
        """Whether this relation is structurally determined (high confidence)."""
        return self.relation_type in (
            RelationType.CONTAINS,
            RelationType.IMPORTS,
            RelationType.ENTRYPOINT_TO,
        )