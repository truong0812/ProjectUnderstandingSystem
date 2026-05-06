"""Context Bundle — materialized retrieval result for AI agents.

A context bundle is the output of a retrieval query, containing
all the relevant entities, relations, summaries, and metadata
an agent needs to perform its task.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from project_understanding.models.entities import File, Module, Symbol
from project_understanding.models.relations import Relation


class ContextItem(BaseModel):
    """A single item in a context bundle with relevance scoring."""

    entity_type: str = Field(description="File, Symbol, Module, or Relation")
    entity_id: str = Field(description="ID of the entity")
    data: dict = Field(description="Serialized entity data")
    summary: str | None = Field(default=None, description="Associated summary text")
    relevance_score: float = Field(default=1.0, description="Relevance score 0-1")
    reason: str = Field(default="", description="Why this item was included")


class ContextBundle(BaseModel):
    """Materialized retrieval result for an AI agent.

    Contains all relevant context for a specific query, filtered
    and ranked according to the agent's profile.
    """

    bundle_id: str = Field(description="Unique bundle identifier")
    query_type: str = Field(description="file_context, symbol_context, module_context, change_context")
    query_params: dict = Field(description="Original query parameters")
    profile_name: str = Field(description="Agent profile used for retrieval")
    snapshot_id: str = Field(description="Snapshot this bundle was built from")
    repo_id: str = Field(description="Repository ID")

    items: list[ContextItem] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list, description="Relevant relations")
    glossary_context: str = Field(default="", description="Domain glossary formatted for agents")

    total_files: int = Field(default=0)
    total_symbols: int = Field(default=0)
    total_modules: int = Field(default=0)
    total_relations: int = Field(default=0)

    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_agent_context(self) -> str:
        """Generate a human-readable context string for an AI agent.

        Returns:
            Formatted context string suitable for prompt injection.
        """
        lines: list[str] = []
        lines.append(f"=== Project Context (profile: {self.profile_name}) ===")
        lines.append(f"Snapshot: {self.snapshot_id}")
        lines.append(f"Query: {self.query_type}({self.query_params})")
        lines.append("")

        for i, item in enumerate(self.items, 1):
            etype = item.entity_type
            score = f"{item.relevance_score:.0%}" if item.relevance_score < 1 else "direct"
            lines.append(f"--- [{i}] {etype} (relevance: {score}) ---")

            if etype == "File":
                lines.append(f"  Path: {item.data.get('path', '?')}")
                lines.append(f"  Language: {item.data.get('language', '?')}")
            elif etype == "Symbol":
                lines.append(f"  Name: {item.data.get('name', '?')}")
                lines.append(f"  Kind: {item.data.get('kind', '?')}")
                lines.append(f"  Path: {item.data.get('path', '?')}")
            elif etype == "Module":
                lines.append(f"  Name: {item.data.get('name', '?')}")
                lines.append(f"  Files: {len(item.data.get('files', []))}")

            if item.reason:
                lines.append(f"  Reason: {item.reason}")

            if item.summary:
                lines.append(f"  Summary: {item.summary}")

            lines.append("")

        if self.relations:
            lines.append(f"--- Relations ({len(self.relations)}) ---")
            for rel in self.relations[:20]:
                lines.append(
                    f"  {rel.get('source_id', '?')} --[{rel.get('relation_type', '?')}]--> "
                    f"{rel.get('target_id', '?')} ({rel.get('evidence', '')})"
                )

        if self.glossary_context:
            lines.append("")
            lines.append(self.glossary_context)

        lines.append(f"\n=== End Context ({len(self.items)} items) ===")
        return "\n".join(lines)
