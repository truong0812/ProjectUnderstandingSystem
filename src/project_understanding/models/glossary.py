"""Domain glossary models — auto-detected project terminology.

Stores domain-specific terms, acronyms, and jargon found in the codebase.
Generated automatically via LLM analysis or heuristic extraction.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GlossaryCategory(str, Enum):
    """Category of glossary term."""

    DOMAIN = "domain"          # Business domain term (e.g., "RAMP", "AWB")
    TECHNICAL = "technical"    # Technical term (e.g., "OAuth", "JWT")
    ACRONYM = "acronym"        # Abbreviation (e.g., "API", "CRUD")
    PATTERN = "pattern"        # Design pattern (e.g., "Repository Pattern")
    FRAMEWORK = "framework"    # Framework-specific (e.g., "Expo", "React Native")


class GlossaryEntry(BaseModel):
    """A single glossary entry representing a domain-specific term.

    Attributes:
        term: The term or acronym (e.g., "RAMP", "ULD", "OAuth").
        definition: Brief explanation of the term.
        category: Classification of the term type.
        context: Where this term was found (file paths, symbol names).
        languages: Optional language-specific translations or notes.
            Key is language code (e.g., "en", "vi"), value is the translation.
        confidence: LLM confidence score (0.0-1.0). 1.0 for heuristic matches.
        source: How this entry was generated ("llm" or "heuristic").
    """

    term: str
    definition: str
    category: GlossaryCategory = GlossaryCategory.DOMAIN
    context: list[str] = Field(default_factory=list)
    languages: dict[str, str] = Field(default_factory=dict)
    confidence: float = 1.0
    source: str = "heuristic"  # "llm" or "heuristic"

    @property
    def glossary_id(self) -> str:
        """Generate a stable ID for this entry."""
        import hashlib
        return hashlib.sha256(
            f"{self.term}:{self.category.value}".encode()
        ).hexdigest()[:12]


class Glossary(BaseModel):
    """Collection of glossary entries for a project.

    Auto-generated during ingestion by analyzing the codebase for
    domain-specific terminology.
    """

    entries: list[GlossaryEntry] = Field(default_factory=list)
    project_name: str = ""
    language_hint: str = ""  # Primary natural language detected (e.g., "vi", "en")

    def get_by_category(self, category: GlossaryCategory) -> list[GlossaryEntry]:
        """Filter entries by category."""
        return [e for e in self.entries if e.category == category]

    def get_by_term(self, term: str) -> GlossaryEntry | None:
        """Look up an entry by exact term match (case-insensitive)."""
        term_lower = term.lower()
        for e in self.entries:
            if e.term.lower() == term_lower:
                return e
        return None

    def to_agent_context(self) -> str:
        """Format glossary as context for AI agents.

        Returns a Markdown-formatted string suitable for inclusion
        in context bundles.
        """
        if not self.entries:
            return ""

        lines = ["## Domain Glossary", ""]

        # Group by category
        categories = {
            GlossaryCategory.DOMAIN: "Domain Terms",
            GlossaryCategory.TECHNICAL: "Technical Terms",
            GlossaryCategory.ACRONYM: "Acronyms",
            GlossaryCategory.PATTERN: "Patterns",
            GlossaryCategory.FRAMEWORK: "Framework Terms",
        }

        for cat, cat_name in categories.items():
            entries = self.get_by_category(cat)
            if not entries:
                continue

            lines.append(f"### {cat_name}")
            lines.append("")
            for e in entries:
                line = f"- **{e.term}**: {e.definition}"
                # Add translations if available
                if e.languages:
                    translations = [
                        f"{lang}: {trans}"
                        for lang, trans in sorted(e.languages.items())
                    ]
                    line += f" ({', '.join(translations)})"
                lines.append(line)
            lines.append("")

        return "\n".join(lines)