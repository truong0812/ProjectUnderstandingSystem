"""Review Agent context builder for V2 snapshots."""

from __future__ import annotations

from project_understanding_v2.models import (
    FileNode,
    FunctionNode,
    LayeredSnapshot,
    RelationType,
    ReviewContext,
)


def build_review_context(
    snapshot: LayeredSnapshot,
    changed_files: list[str],
    changed_symbols: list[str] | None = None,
    max_depth: int = 2,
) -> ReviewContext:
    """Build layered review context for changed files or symbols."""
    changed_symbols = changed_symbols or []
    files_by_path = {file_node.path: file_node for file_node in snapshot.files}
    functions_by_id = {function.function_id: function for function in snapshot.functions}
    classes_by_id = {klass.class_id: klass for klass in snapshot.classes}
    modules_by_id = {module.module_id: module for module in snapshot.modules}
    file_by_id = {file_node.file_id: file_node for file_node in snapshot.files}

    changed_file_set = set(changed_files)
    changed_function_nodes = [
        function
        for function in snapshot.functions
        if function.file_path in changed_file_set
        or function.name in changed_symbols
        or function.qualified_name in changed_symbols
    ]

    containing_class_ids = {fn.owning_class_id for fn in changed_function_nodes if fn.owning_class_id}
    containing_classes = [classes_by_id[class_id] for class_id in containing_class_ids if class_id in classes_by_id]

    module_ids = {fn.owning_module_id for fn in changed_function_nodes if fn.owning_module_id}
    module_ids.update(klass.owning_module_id for klass in containing_classes if klass.owning_module_id)
    owning_modules = [modules_by_id[module_id] for module_id in module_ids if module_id in modules_by_id]

    architecture_layers = [
        layer
        for layer in snapshot.architecture.layers
        if any(module.module_id in layer.modules for module in owning_modules)
    ]

    changed_function_ids = {fn.function_id for fn in changed_function_nodes}
    direct_callee_ids = {
        relation.target_id
        for relation in snapshot.relations
        if relation.relation_type == RelationType.CALLS and relation.source_id in changed_function_ids
    }
    direct_caller_ids = {
        relation.source_id
        for relation in snapshot.relations
        if relation.relation_type == RelationType.CALLS and relation.target_id in changed_function_ids
    }
    direct_callees = [functions_by_id[fn_id] for fn_id in direct_callee_ids if fn_id in functions_by_id]
    direct_callers = [functions_by_id[fn_id] for fn_id in direct_caller_ids if fn_id in functions_by_id]

    changed_file_ids = {files_by_path[path].file_id for path in changed_files if path in files_by_path}
    reverse_dependency_ids = {
        relation.source_id
        for relation in snapshot.relations
        if relation.relation_type in {RelationType.IMPORTS, RelationType.DEPENDS_ON}
        and relation.target_id in changed_file_ids
    }
    reverse_dependencies = [file_by_id[file_id] for file_id in reverse_dependency_ids if file_id in file_by_id]

    risk_markers = sorted(
        {
            marker
            for item in [*changed_function_nodes, *containing_classes, *owning_modules]
            for marker in item.risk_markers
        }
    )
    evidence = _evidence(changed_function_nodes, containing_classes, owning_modules, reverse_dependencies)
    return ReviewContext(
        changed_files=changed_files,
        changed_functions=changed_function_nodes,
        containing_classes=containing_classes,
        owning_modules=owning_modules,
        architecture_layers=architecture_layers,
        direct_callers=direct_callers[: max_depth * 10],
        direct_callees=direct_callees[: max_depth * 10],
        reverse_dependencies=reverse_dependencies[: max_depth * 10],
        risk_markers=risk_markers,
        conventions=_conventions(snapshot),
        review_checklist=_review_checklist(risk_markers, bool(reverse_dependencies), bool(direct_callers)),
        evidence=evidence,
    )


def _evidence(
    changed_functions: list[FunctionNode],
    containing_classes,
    owning_modules,
    reverse_dependencies: list[FileNode],
) -> list[str]:
    evidence: list[str] = []
    for function in changed_functions:
        evidence.append(f"{function.file_path}:{function.line_start}-{function.line_end}")
    for klass in containing_classes:
        evidence.append(f"{klass.file_path}:{klass.line_start}-{klass.line_end}")
    for module in owning_modules:
        evidence.extend(module.owned_files[:5])
    for file_node in reverse_dependencies:
        evidence.append(file_node.path)
    return sorted(dict.fromkeys(evidence))


def _conventions(snapshot: LayeredSnapshot) -> list[str]:
    conventions: list[str] = []
    if any(file_node.path.startswith("src/") for file_node in snapshot.files):
        conventions.append("Source code is organized under src/.")
    if any(file_node.category.value == "test" for file_node in snapshot.files):
        conventions.append("Repository includes test files.")
    if snapshot.architecture.dependency_direction:
        conventions.append(
            "Detected architecture direction: "
            + " -> ".join(snapshot.architecture.dependency_direction)
        )
    return conventions


def _review_checklist(risk_markers: list[str], has_reverse_deps: bool, has_callers: bool) -> list[str]:
    checklist = [
        "Verify the behavior change matches the intended contract.",
        "Check direct callees and side effects for regressions.",
        "Confirm tests cover the changed path.",
    ]
    if has_callers:
        checklist.append("Inspect callers for assumptions broken by the change.")
    if has_reverse_deps:
        checklist.append("Inspect reverse dependencies that import or depend on changed files.")
    if "authentication" in risk_markers:
        checklist.append("Review authentication and authorization edge cases.")
    if "persistence" in risk_markers:
        checklist.append("Review data integrity, transactions, and persistence side effects.")
    if "external_api" in risk_markers:
        checklist.append("Review external API failures, timeouts, and response contracts.")
    if "filesystem" in risk_markers:
        checklist.append("Review filesystem paths, overwrite behavior, and cleanup.")
    return checklist
