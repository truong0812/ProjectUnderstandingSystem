"""Business glossary for domain-specific context detection.

.. deprecated::
    This module is deprecated. Use the domain plugin system instead:

        from project_understanding.ingest.domain_plugins import registry
        metadata = registry.detect_all(code, max_terms=5)

    The logistics/cargo glossary is now available as a plugin at:
        from project_understanding.ingest.domain_plugins.logistics_vi import LogisticsViPlugin

This module is kept for backward compatibility and will be removed in a future version.
"""

from __future__ import annotations

import warnings

from project_understanding.ingest.domain_plugins import registry as _registry
from project_understanding.ingest.domain_plugins.logistics_vi import LogisticsViPlugin


def detect_business_context(code: str, max_terms: int = 5) -> str:
    """Detect business domain terms in code and return context string.

    .. deprecated::
        Use ``detect_domain_llm()`` from ``domain_detector`` instead,
        which provides LLM-based domain detection for ANY domain.

    Args:
        code: Source code or file content to analyze.
        max_terms: Maximum number of terms to include in context.

    Returns:
        Formatted context string, or empty string if no terms found.
    """
    warnings.warn(
        "detect_business_context() is deprecated. "
        "Use project_understanding.ingest.domain_detector.detect_domain_llm() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Ensure logistics plugin is loaded for backward compatibility
    if _registry.get("logistics_vi") is None:
        _registry.register(LogisticsViPlugin())
    found = _registry.detect_all(code, max_terms=max_terms)
    if not found:
        return ""
    return "Nghiệp vụ: " + "; ".join(found.values())