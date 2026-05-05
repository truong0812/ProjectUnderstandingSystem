"""Agent profile model — defines how an agent queries the knowledge base."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RankingMode(str, Enum):
    """How to rank retrieval results."""

    RELEVANCE = "relevance"
    DEPENDENCY_DEPTH = "dependency_depth"
    BREADTH_FIRST = "breadth_first"


class AgentProfile(BaseModel):
    """Configuration that defines how an agent reads the knowledge base.

    The profile controls which entities, relations, and summaries
    are included in a context bundle, and how they are ranked.
    """

    name: str = Field(description="Unique profile name, e.g. 'review-agent'")
    preferred_entities: list[str] = Field(
        default=["File", "Symbol", "Relation"],
        description="Entity types to prioritize in results",
    )
    preferred_relations: list[str] = Field(
        default=["imports", "calls", "depends_on"],
        description="Relation types to include",
    )
    include_conventions: bool = Field(
        default=False,
        description="Include convention matches (Phase 3)",
    )
    include_risks: bool = Field(
        default=False,
        description="Include risk area matches (Phase 3)",
    )
    include_related_files: bool = Field(
        default=True,
        description="Include files related to the primary target",
    )
    max_items: int = Field(
        default=50,
        description="Maximum number of items in a context bundle",
    )
    ranking_mode: RankingMode = Field(
        default=RankingMode.RELEVANCE,
        description="Strategy for ranking results",
    )
    summary_levels: list[str] = Field(
        default=["file"],
        description="Summary levels to include: file, symbol, module",
    )
    semantic_search_enabled: bool = Field(
        default=False,
        description="Enable semantic search (Phase 3)",
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> AgentProfile:
        """Load a profile from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            AgentProfile instance.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def to_yaml(self, path: str | Path) -> None:
        """Save this profile to a YAML file.

        Args:
            path: Output path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json")
        # Convert enums to strings for clean YAML
        data["ranking_mode"] = self.ranking_mode.value
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)