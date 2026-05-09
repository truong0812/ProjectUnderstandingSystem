"""Lightweight parsers for the V2 layered prototype."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from project_understanding_v2.models import (
    ClassNode,
    FileCategory,
    FileNode,
    FunctionNode,
    SymbolKind,
    stable_id,
)


@dataclass
class ParseResult:
    classes: list[ClassNode] = field(default_factory=list)
    functions: list[FunctionNode] = field(default_factory=list)
    imports: dict[str, list[str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def parse_repository(root_path: Path, files: list[FileNode]) -> ParseResult:
    result = ParseResult()
    for file_node in files:
        if file_node.category not in {FileCategory.SOURCE, FileCategory.TEST}:
            continue
        absolute = root_path / file_node.path
        try:
            content = absolute.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            result.errors.append(f"{file_node.path}: {exc}")
            continue

        if file_node.language == "python":
            parsed = _parse_python(file_node.path, content)
        elif file_node.language == "typescript":
            parsed = _parse_typescript(file_node.path, content)
        else:
            continue

        result.classes.extend(parsed.classes)
        result.functions.extend(parsed.functions)
        result.imports[file_node.path] = parsed.imports.get(file_node.path, [])
        result.errors.extend(parsed.errors)
    return result


def _parse_python(path: str, content: str) -> ParseResult:
    parsed = ParseResult(imports={path: []})
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        parsed.errors.append(f"{path}: {exc}")
        return parsed

    lines = content.splitlines()
    class_stack: list[ClassNode] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            parsed.imports[path].extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            parsed.imports[path].append(node.module)

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_node = _python_class_node(path, node)
            parsed.classes.append(class_node)
            class_stack.append(class_node)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    parsed.functions.append(_python_function_node(path, child, lines, class_node))
            class_stack.pop()
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parsed.functions.append(_python_function_node(path, node, lines, None))

    return parsed


def _python_class_node(path: str, node: ast.ClassDef) -> ClassNode:
    return ClassNode(
        class_id=stable_id("class", path, node.name, str(node.lineno)),
        name=node.name,
        kind=SymbolKind.CLASS,
        file_path=path,
        line_start=node.lineno,
        line_end=getattr(node, "end_lineno", node.lineno),
        responsibility=f"Class {node.name} defined in {path}.",
    )


def _python_function_node(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: list[str],
    owner: ClassNode | None,
) -> FunctionNode:
    qualified_name = f"{owner.name}.{node.name}" if owner else node.name
    calls = sorted(_collect_python_calls(node))
    risk_markers = _risk_markers("\n".join(lines[node.lineno - 1 : getattr(node, "end_lineno", node.lineno)]))
    return FunctionNode(
        function_id=stable_id("function", path, qualified_name, str(node.lineno)),
        name=node.name,
        qualified_name=qualified_name,
        file_path=path,
        line_start=node.lineno,
        line_end=getattr(node, "end_lineno", node.lineno),
        owning_class_id=owner.class_id if owner else None,
        signature=_line_at(lines, node.lineno),
        visibility="private" if node.name.startswith("_") else "public",
        parameters=[arg.arg for arg in node.args.args],
        return_type=ast.unparse(node.returns) if node.returns else "",
        calls=calls,
        side_effects=_side_effects_from_calls(calls),
        risk_markers=risk_markers,
    )


def _collect_python_calls(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.add(child.func.attr)
    return calls


def _parse_typescript(path: str, content: str) -> ParseResult:
    parsed = ParseResult(imports={path: []})
    parsed.imports[path].extend(re.findall(r"from\s+['\"]([^'\"]+)['\"]", content))
    parsed.imports[path].extend(re.findall(r"import\s+['\"]([^'\"]+)['\"]", content))

    lines = content.splitlines()
    for match in re.finditer(r"(?:export\s+)?class\s+(\w+)", content):
        line_no = content[: match.start()].count("\n") + 1
        name = match.group(1)
        parsed.classes.append(
            ClassNode(
                class_id=stable_id("class", path, name, str(line_no)),
                name=name,
                file_path=path,
                line_start=line_no,
                line_end=_find_block_end(lines, line_no),
                responsibility=f"Class {name} defined in {path}.",
            )
        )

    function_patterns = [
        r"(?:export\s+)?function\s+(\w+)\s*\(([^)]*)\)",
        r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
    ]
    for pattern in function_patterns:
        for match in re.finditer(pattern, content):
            line_no = content[: match.start()].count("\n") + 1
            name = match.group(1)
            body = "\n".join(lines[line_no - 1 : _find_block_end(lines, line_no)])
            calls = sorted(set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - {name})
            parsed.functions.append(
                FunctionNode(
                    function_id=stable_id("function", path, name, str(line_no)),
                    name=name,
                    qualified_name=name,
                    file_path=path,
                    line_start=line_no,
                    line_end=_find_block_end(lines, line_no),
                    signature=_line_at(lines, line_no),
                    parameters=[p.strip().split(":")[0].strip() for p in match.group(2).split(",") if p.strip()],
                    calls=calls,
                    side_effects=_side_effects_from_calls(calls),
                    risk_markers=_risk_markers(body),
                )
            )
    return parsed


def _line_at(lines: list[str], line_no: int) -> str:
    if 1 <= line_no <= len(lines):
        return lines[line_no - 1].strip()
    return ""


def _find_block_end(lines: list[str], line_no: int) -> int:
    brace_balance = 0
    saw_brace = False
    for idx in range(max(0, line_no - 1), len(lines)):
        brace_balance += lines[idx].count("{")
        brace_balance -= lines[idx].count("}")
        saw_brace = saw_brace or "{" in lines[idx]
        if saw_brace and brace_balance <= 0:
            return idx + 1
    return line_no


def _risk_markers(text: str) -> list[str]:
    markers: list[str] = []
    checks = {
        "authentication": r"auth|login|token|jwt|password",
        "persistence": r"save|insert|update|delete|commit|rollback|database|repo",
        "external_api": r"requests\.|httpx|fetch|urllib|api",
        "filesystem": r"open\(|write\(|unlink|remove|rename",
    }
    for marker, pattern in checks.items():
        if re.search(pattern, text, re.IGNORECASE):
            markers.append(marker)
    return markers


def _side_effects_from_calls(calls: list[str]) -> list[str]:
    effects: list[str] = []
    if any(call in {"save", "insert", "update", "delete", "commit", "rollback"} for call in calls):
        effects.append("persistence")
    if any(call in {"open", "write", "remove", "unlink", "rename"} for call in calls):
        effects.append("filesystem")
    if any(call in {"fetch", "request", "post", "get"} for call in calls):
        effects.append("external_api")
    return effects
