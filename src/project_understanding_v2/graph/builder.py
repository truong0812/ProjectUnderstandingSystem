"""Construct a deterministic code graph from parsed source data.

Creates ``ModuleNode``, ``ClassNode``, ``FunctionNode`` and ``RelationEdge``
instances based on the simple parsing results.
"""

import os
from typing import Dict, List, Any

from ..models import ModuleNode, ClassNode, FunctionNode, RelationEdge


def _module_id_from_path(path: str) -> str:
    parts = path.split(os.sep)
    return parts[0] if parts else "root"


def build_code_graph(parsed_data: Dict[str, Any]) -> Dict[str, List[Any]]:
    modules: Dict[str, ModuleNode] = {}
    classes: List[ClassNode] = []
    functions: List[FunctionNode] = []
    relations: List[RelationEdge] = []

    for file_path, data in parsed_data.items():
        mod_id = _module_id_from_path(file_path)
        module = modules.setdefault(
            mod_id,
            ModuleNode(
                module_id=mod_id,
                name=mod_id,
                owned_files=[file_path],
            ),
        )
        if file_path not in module.owned_files:
            module.owned_files.append(file_path)

        for imp in data.get("imports", []):
            target_mod = imp.split(".")[0]
            relations.append(
                RelationEdge(
                    source_id=module.module_id,
                    target_id=target_mod,
                    relation_type="imports",
                )
            )

        for cls in data.get("classes", []):
            class_node = ClassNode(
                class_id=f"{module.module_id}.{cls['name']}",
                name=cls["name"],
                file_path=file_path,
                owning_module=module.module_id,
                public_methods=[m["name"] for m in cls.get("methods", [])],
            )
            classes.append(class_node)
            relations.append(
                RelationEdge(
                    source_id=module.module_id,
                    target_id=class_node.class_id,
                    relation_type="contains",
                )
            )

        for fn in data.get("functions", []):
            func_node = FunctionNode(
                function_id=f"{module.module_id}.{fn['name']}",
                name=fn["name"],
                qualified_path=f"{module.module_id}.{fn['name']}",
                file_path=file_path,
                owning_module=module.module_id,
                line_range=(fn["lineno"], fn["lineno"]),
                parameters=fn.get("args", []),
            )
            functions.append(func_node)
            relations.append(
                RelationEdge(
                    source_id=module.module_id,
                    target_id=func_node.function_id,
                    relation_type="contains",
                )
            )

    return {
        "modules": list(modules.values()),
        "classes": classes,
        "functions": functions,
        "relations": relations,
    }
