"""Base interface for domain glossary plugins.

Each plugin provides domain-specific term detection for a particular
business area (e.g., logistics, healthcare, finance).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DomainGlossaryPlugin(ABC):
    """Abstract base class for domain glossary plugins.

    A plugin maps domain-specific keywords found in source code to
    human-readable descriptions. The summarizer uses registered plugins
    to enrich summaries with business context.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this domain plugin (e.g., 'logistics_vi')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the domain this plugin covers."""
        ...

    @abstractmethod
    def detect_context(
        self, code: str, max_terms: int = 5
    ) -> dict[str, str]:
        """Detect domain-specific terms in code and return context metadata.

        Args:
            code: Source code or file content to analyze.
            max_terms: Maximum number of terms to include.

        Returns:
            Dictionary of detected terms and their descriptions.
            Empty dict if no terms found.
        """
        ...