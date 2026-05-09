"""Project Understanding System V2 package.

This package provides a layered approach to ingesting a code repository,
building a deterministic code graph, inferring architecture, generating
structured summaries, and producing review context for changed code.

The implementation follows the plan outlined in `docs/LAYERED_REBUILD_PLAN.md`.
"""

__all__ = [
    "scan",
    "parse",
    "graph",
    "architecture",
    "summarize",
    "review",
    "storage",
    "cli",
    "models",
]
