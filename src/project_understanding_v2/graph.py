"""Graph construction for V2 layered snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from project_understanding_v2.models import (
    ArchitectureLayer,
    ArchitectureMap,
    ClassNode,
    FileNode,
    FunctionNode,
    LayeredSummary,
    ModuleNode,
    RelationEdge,
    RelationType,
    stable_id,
)


def build_modules(files: list[FileNode], classes: list[ClassNode], functions: list[FunctionNode]) -> list[ModuleNode]:
    grouped: dict[str, list[FileNode]] = defaultdict(list)
    for file_node in files:
        grouped[_module_name(file_node.path)].append(file_node)

    modules: list[ModuleNode] = []
    for name, module_files in sorted(grouped.items()):
        module_id = stable_id("module", name)
        paths = [f.path for f in module_files]
        key_classes = [c.class_id for c in classes if c.file_path in paths]
        key_functions = [
            fn.function_id
            for fn in functions
            if fn.file_path in paths and fn.visibility == "public"
        ]
        modules.append(
            ModuleNode(
                module_id=module_id,
                name=name,
                path_patterns=[f"{name}/" if name != "root" else "*"],
                responsibility=f"Owns code and files under {name}.",
                owned_files=paths,
                public_surface=key_functions[:20],
                key_classes=key_classes[:20],
                key_functions=key_functions[:20],
                risk_markers=sorted({m for fn in functions if fn.file_path in paths for m in fn.risk_markers}),
            )
        )

    by_name = {m.name: m for m in modules}
    
    # Optimized: Build path prefix → module lookup table for O(1) dependency resolution
    # Instead of O(n²) nested loop, we now have O(n) build + O(m) lookup where m = unique prefixes
    path_to_module: dict[str, str] = {}
    for module in modules:
        path_to_module[f"{module.name}/"] = module.name
    
    imports_by_module: dict[str, set[str]] = defaultdict(set)
    for file_node in files:
        source = _module_name(file_node.path)
        # Check all path prefixes against the lookup table
        for prefix, target in path_to_module.items():
            if source != target and prefix in file_node.path:
                imports_by_module[source].add(target)
    
    for name, deps in imports_by_module.items():
        if name in by_name:
            by_name[name].dependencies = sorted(deps)
    return modules


def attach_ownership(
    modules: list[ModuleNode],
    classes: list[ClassNode],
    functions: list[FunctionNode],
) -> None:
    module_by_file: dict[str, str] = {}
    for module in modules:
        for path in module.owned_files:
            module_by_file[path] = module.module_id

    class_by_id = {klass.class_id: klass for klass in classes}
    for klass in classes:
        klass.owning_module_id = module_by_file.get(klass.file_path)
    for function in functions:
        function.owning_module_id = module_by_file.get(function.file_path)
        if function.owning_class_id and function.owning_class_id in class_by_id:
            class_by_id[function.owning_class_id].public_methods.append(function.function_id)


def build_relations(
    files: list[FileNode],
    modules: list[ModuleNode],
    classes: list[ClassNode],
    functions: list[FunctionNode],
    imports: dict[str, list[str]],
) -> list[RelationEdge]:
    relations: list[RelationEdge] = []
    file_by_path = {f.path: f for f in files}
    module_by_file = {path: module.module_id for module in modules for path in module.owned_files}
    function_by_name: dict[str, list[FunctionNode]] = defaultdict(list)
    for function in functions:
        function_by_name[function.name].append(function)

    for module in modules:
        for path in module.owned_files:
            relations.append(
                RelationEdge(
                    source_id=module.module_id,
                    target_id=file_by_path[path].file_id,
                    relation_type=RelationType.CONTAINS,
                    evidence=f"Module {module.name} owns {path}",
                )
            )
    for klass in classes:
        if klass.owning_module_id:
            relations.append(
                RelationEdge(
                    source_id=klass.owning_module_id,
                    target_id=klass.class_id,
                    relation_type=RelationType.CONTAINS,
                    evidence=f"Module contains class {klass.name}",
                    source_location=f"{klass.file_path}:{klass.line_start}",
                )
            )
    for function in functions:
        owner = function.owning_class_id or function.owning_module_id
        if owner:
            relations.append(
                RelationEdge(
                    source_id=owner,
                    target_id=function.function_id,
                    relation_type=RelationType.CONTAINS,
                    evidence=f"Owner contains function {function.qualified_name}",
                    source_location=f"{function.file_path}:{function.line_start}",
                )
            )
        for call_name in function.calls:
            for target in function_by_name.get(call_name, [])[:3]:
                if target.function_id != function.function_id:
                    relations.append(
                        RelationEdge(
                            source_id=function.function_id,
                            target_id=target.function_id,
                            relation_type=RelationType.CALLS,
                            confidence=0.7,
                            evidence=f"{function.qualified_name} calls {call_name}",
                            source_location=f"{function.file_path}:{function.line_start}",
                        )
                    )

    for source_path, imported_modules in imports.items():
        source_file = file_by_path.get(source_path)
        if not source_file:
            continue
        for imported in imported_modules:
            target_file = _resolve_import(imported, files)
            if target_file:
                relations.append(
                    RelationEdge(
                        source_id=source_file.file_id,
                        target_id=target_file.file_id,
                        relation_type=RelationType.IMPORTS,
                        confidence=0.8,
                        evidence=f"{source_path} imports {imported}",
                    )
                )
                if module_by_file.get(source_path) != module_by_file.get(target_file.path):
                    relations.append(
                        RelationEdge(
                            source_id=source_file.file_id,
                            target_id=target_file.file_id,
                            relation_type=RelationType.DEPENDS_ON,
                            confidence=0.8,
                            evidence=f"{source_path} depends on {target_file.path}",
                        )
                    )
    return relations


def infer_architecture(files: list[FileNode], modules: list[ModuleNode]) -> ArchitectureMap:
    layers: list[ArchitectureLayer] = []
    entrypoints = [
        f.path
        for f in files
        if Path(f.path).name in {"main.py", "__main__.py", "cli.py", "app.py", "index.ts", "index.tsx"}
        or "/cli/" in f.path
    ]
    module_lookup = {m.name: m.module_id for m in modules}
    rules = [
        ("interface", "Entrypoints and user-facing command/API surfaces.", ["cli", "api", "routes", "controllers"]),
        ("application", "Workflow orchestration and use-case logic.", ["service", "services", "workflow", "ingest"]),
        ("domain", "Domain models and core business concepts.", ["domain", "models", "entities", "schema"]),
        ("infrastructure", "Adapters, integrations, parsing, and external boundaries.", ["adapter", "adapters", "parse", "storage", "repository"]),
        ("tests", "Automated tests and validation fixtures.", ["test", "tests"]),
    ]
    for layer_name, responsibility, keywords in rules:
        matched = [
            module.module_id
            for module in modules
            if any(keyword in module.name.lower() for keyword in keywords)
        ]
        evidence = [module.name for module in modules if module.module_id in matched]
        if matched:
            layers.append(
                ArchitectureLayer(
                    name=layer_name,
                    responsibility=responsibility,
                    modules=matched,
                    evidence=evidence,
                )
            )
    if not layers and modules:
        layers.append(
            ArchitectureLayer(
                name="application",
                responsibility="Default layer for project modules.",
                modules=[m.module_id for m in modules],
                evidence=[m.name for m in modules],
            )
        )
    risk_zones = sorted({marker for module in modules for marker in module.risk_markers})
    confidence = min(0.95, 0.35 + 0.15 * len(layers) + (0.1 if entrypoints else 0.0))
    return ArchitectureMap(
        layers=layers,
        entrypoints=entrypoints,
        dependency_direction=[layer.name for layer in layers],
        risk_zones=risk_zones,
        confidence=confidence,
    )


def build_summaries(
    architecture: ArchitectureMap,
    modules: list[ModuleNode],
    classes: list[ClassNode],
    functions: list[FunctionNode],
) -> list[LayeredSummary]:
    summaries: list[LayeredSummary] = [
        LayeredSummary(
            summary_id=stable_id("summary", "architecture"),
            target_id="architecture",
            level="architecture",
            responsibility="Describes project layers, entrypoints, and risk zones.",
            important_behavior=[f"Layer: {layer.name}" for layer in architecture.layers],
            risk_notes=architecture.risk_zones,
            evidence=architecture.entrypoints,
            confidence=architecture.confidence,
        )
    ]
    for module in modules:
        summaries.append(
            LayeredSummary(
                summary_id=stable_id("summary", module.module_id),
                target_id=module.module_id,
                level="module",
                responsibility=module.responsibility,
                dependencies=module.dependencies,
                risk_notes=module.risk_markers,
                evidence=module.owned_files[:10],
            )
        )
    for klass in classes:
        if klass.public_methods or klass.risk_markers:
            summaries.append(
                LayeredSummary(
                    summary_id=stable_id("summary", klass.class_id),
                    target_id=klass.class_id,
                    level="class",
                    responsibility=klass.responsibility,
                    risk_notes=klass.risk_markers,
                    evidence=[f"{klass.file_path}:{klass.line_start}-{klass.line_end}"],
                )
            )
    for function in functions:
        if function.visibility == "public" or function.risk_markers:
            summaries.append(
                LayeredSummary(
                    summary_id=stable_id("summary", function.function_id),
                    target_id=function.function_id,
                    level="function",
                    responsibility=f"Function {function.qualified_name} in {function.file_path}.",
                    important_behavior=function.calls[:10],
                    side_effects=function.side_effects,
                    risk_notes=function.risk_markers,
                    evidence=[f"{function.file_path}:{function.line_start}-{function.line_end}"],
                )
            )
    return summaries


def relation_counts(relations: list[RelationEdge]) -> dict[str, int]:
    return dict(Counter(relation.relation_type.value for relation in relations))


def _module_name(path: str) -> str:
    parts = Path(path).parts
    if len(parts) <= 1:
        return "root"
    if parts[0] == "src" and len(parts) > 2:
        return parts[1]
    return parts[0]


def _resolve_import(imported: str, files: list[FileNode]) -> FileNode | None:
    normalized = imported.strip(".").replace(".", "/")
    candidates = {
        f"{normalized}.py",
        f"{normalized}.ts",
        f"{normalized}.tsx",
        f"{normalized}/__init__.py",
        f"src/{normalized}.py",
        f"src/{normalized}.ts",
        f"src/{normalized}.tsx",
    }
    for file_node in files:
        if file_node.path in candidates or file_node.path.endswith(f"/{normalized}.py"):
            return file_node
    return None
