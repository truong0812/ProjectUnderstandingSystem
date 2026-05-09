"""Placeholder summarizer that creates a :class:`LayeredSummary`.

In a real implementation this would invoke an LLM and validate JSON output.
Here we simply construct a deterministic summary from the provided data.
"""

from typing import Dict, Any

from ..models import LayeredSummary


def summarize_entity(level: str, identifier: str, data: Dict[str, Any]) -> LayeredSummary:
    """Return a ``LayeredSummary`` for *level* and *identifier* using *data*.

    The *data* dict may contain keys such as ``responsibility``, ``description``,
    ``dependencies``, ``side_effects``, ``risk`` and ``evidence``. Missing keys
    default to empty values.
    """
    return LayeredSummary(
        level=level,
        identifier=identifier,
        responsibility=data.get("responsibility"),
        important_behavior=data.get("description"),
        dependencies=data.get("dependencies", []),
        side_effects=data.get("side_effects", []),
        risk_notes=data.get("risk", []),
        evidence=data.get("evidence", []),
        generated_by="local_summarizer",
        confidence=1.0,
    )
