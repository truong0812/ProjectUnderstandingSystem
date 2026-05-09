"""Build a :class:`ReviewContext` from the generated code graph.

The implementation extracts changed symbols from the supplied list of changed
files and then walks ``calls`` relations to collect direct callers and callees.
"""

from typing import List, Dict, Any

from ..models import ReviewContext


def build_review_context(
    changed_files: List[str],
    graph: Dict[str, Any],
    max_depth: int = 2,
):
    """Create a ``ReviewContext`` for *changed_files* using *graph*.

    ``max_depth`` is currently unused – the function only gathers direct callers
    and callees, which satisfies the minimal requirements of the plan.
    """
    changed_symbols: List[str] = []
    for fn in graph.get("functions", []):
        if fn.file_path in changed_files:
            changed_symbols.append(fn.function_id)
    for cls in graph.get("classes", []):
        if cls.file_path in changed_files:
            changed_symbols.append(cls.class_id)

    callers: List[str] = []
    callees: List[str] = []
    for rel in graph.get("relations", []):
        if rel.relation_type == "calls":
            if rel.target_id in changed_symbols:
                callers.append(rel.source_id)
            if rel.source_id in changed_symbols:
                callees.append(rel.target_id)

    return ReviewContext(
        changed_files=changed_files,
        changed_symbols=changed_symbols,
        containing_classes=[],
        owning_modules=[],
        architecture_layers=[],
        direct_callers=callers,
        direct_callees=callees,
        reverse_dependencies=[],
        risk_markers=[],
        conventions=[],
        review_checklist=["behavior change", "API contract", "error handling"],
        evidence_references=[],
    )
