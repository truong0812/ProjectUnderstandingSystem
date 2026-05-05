"""Convention detector — heuristic detection of codebase patterns.

Detects conventions such as:
- Naming patterns (snake_case, camelCase, PascalCase)
- Module structure (src/ layout, flat layout)
- Service/Repository/Controller patterns
- Error handling patterns
- Config organization patterns
"""

from __future__ import annotations

import hashlib
import re
from pathlib import PurePosixPath

from project_understanding.models.conventions import Convention, ConventionType
from project_understanding.models.entities import File, Module, Symbol
from project_understanding.models.relations import Relation


def detect_conventions(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str] | None = None,
) -> list[Convention]:
    """Run all convention detectors on the codebase.

    Args:
        files: All files in the snapshot.
        modules: All modules in the snapshot.
        symbols: All symbols in the snapshot.
        relations: All relations in the snapshot.
        contents: Optional mapping of file_path -> file_content.

    Returns:
        List of detected conventions.
    """
    detectors = [
        _detect_naming_patterns,
        _detect_module_structure,
        _detect_service_repository_pattern,
        _detect_error_handling,
        _detect_config_organization,
        _detect_entrypoint_pattern,
        _detect_dependency_direction,
    ]

    conventions: list[Convention] = []
    for detector in detectors:
        try:
            results = detector(files, modules, symbols, relations, contents or {})
            conventions.extend(results)
        except Exception:
            continue  # Never fail the whole pipeline

    return conventions


def _make_id(*parts: str) -> str:
    """Generate deterministic convention ID."""
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ─── Individual detectors ─────────────────────────────────────────────


def _detect_naming_patterns(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect naming conventions across the codebase."""
    conventions: list[Convention] = []

    # Check Python naming (snake_case files)
    py_files = [f for f in files if f.language == "python"]
    if py_files:
        snake_case_files = [
            f for f in py_files
            if re.match(r"^[a-z_][a-z0-9_]*\.py$", PurePosixPath(f.path).name)
        ]
        if len(snake_case_files) >= len(py_files) * 0.7:
            conventions.append(Convention(
                convention_id=_make_id("naming", "python_snake_case"),
                convention_type=ConventionType.NAMING_PATTERN,
                name="Python snake_case file naming",
                description="Python files follow snake_case naming convention",
                evidence=[f.path for f in snake_case_files[:10]],
                confidence=min(len(snake_case_files) / max(len(py_files), 1), 1.0),
                affected_files=[f.path for f in snake_case_files],
            ))

    # Check symbol naming patterns
    py_symbols = [s for s in symbols if s.kind.value in ("class", "function")]
    if py_symbols:
        class_names = [s.name for s in py_symbols if s.kind.value == "class"]
        func_names = [s.name for s in py_symbols if s.kind.value == "function"]

        pascal_classes = [n for n in class_names if re.match(r"^[A-Z][a-zA-Z0-9]*$", n)]
        snake_funcs = [n for n in func_names if re.match(r"^[a-z_][a-z0-9_]*$", n)]

        if class_names and len(pascal_classes) >= len(class_names) * 0.7:
            conventions.append(Convention(
                convention_id=_make_id("naming", "pascal_class"),
                convention_type=ConventionType.NAMING_PATTERN,
                name="PascalCase class naming",
                description="Classes follow PascalCase naming convention",
                evidence=pascal_classes[:10],
                confidence=min(len(pascal_classes) / max(len(class_names), 1), 1.0),
            ))

        if func_names and len(snake_funcs) >= len(func_names) * 0.7:
            conventions.append(Convention(
                convention_id=_make_id("naming", "snake_func"),
                convention_type=ConventionType.NAMING_PATTERN,
                name="snake_case function naming",
                description="Functions follow snake_case naming convention",
                evidence=snake_funcs[:10],
                confidence=min(len(snake_funcs) / max(len(func_names), 1), 1.0),
            ))

    return conventions


def _detect_module_structure(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect module/directory organization patterns."""
    conventions: list[Convention] = []

    # Check for src/ layout
    src_files = [f for f in files if f.path.startswith("src/")]
    if src_files and len(src_files) >= len(files) * 0.5:
        conventions.append(Convention(
            convention_id=_make_id("module", "src_layout"),
            convention_type=ConventionType.MODULE_STRUCTURE,
            name="src/ directory layout",
            description="Source code is organized under a src/ directory, separating it from config/docs",
            evidence=[f.path for f in src_files[:5]],
            confidence=0.9,
            affected_files=[f.path for f in src_files],
        ))

    # Check for package-based modules (Python packages with __init__.py)
    init_files = [f for f in files if f.path.endswith("__init__.py")]
    if len(init_files) >= 3:
        conventions.append(Convention(
            convention_id=_make_id("module", "python_packages"),
            convention_type=ConventionType.MODULE_STRUCTURE,
            name="Python package modules",
            description="Modules are organized as Python packages with __init__.py files",
            evidence=[f.path for f in init_files[:10]],
            confidence=0.9,
            affected_files=[f.path for f in init_files],
        ))

    return conventions


def _detect_service_repository_pattern(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect service/repository/controller architectural patterns."""
    conventions: list[Convention] = []
    pattern_keywords = {
        "service": ["service", "handler", "manager"],
        "repository": ["repository", "repo", "store", "storage", "dal"],
        "controller": ["controller", "router", "endpoint", "api", "resource"],
        "model": ["model", "entity", "schema", "domain"],
    }

    for pattern_name, keywords in pattern_keywords.items():
        matching_files = []
        matching_symbols = []
        for f in files:
            fname = PurePosixPath(f.path).name.lower()
            fpath = f.path.lower()
            if any(kw in fname or kw in fpath for kw in keywords):
                matching_files.append(f.path)

        for s in symbols:
            sname = s.name.lower()
            if any(kw in sname for kw in keywords):
                matching_symbols.append(s.symbol_id)

        if matching_files or matching_symbols:
            conventions.append(Convention(
                convention_id=_make_id("pattern", pattern_name),
                convention_type=ConventionType.SERVICE_REPOSITORY_PATTERN,
                name=f"{pattern_name.capitalize()} pattern",
                description=f"Codebase uses {pattern_name} pattern for separation of concerns",
                evidence=matching_files[:5] or matching_symbols[:5],
                confidence=0.8 if matching_files else 0.6,
                affected_files=matching_files,
                affected_symbols=matching_symbols,
            ))

    return conventions


def _detect_error_handling(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect error handling patterns."""
    conventions: list[Convention] = []

    # Check for custom exception classes
    exception_symbols = [
        s for s in symbols
        if "error" in s.name.lower() or "exception" in s.name.lower()
        or s.kind.value == "class"
    ]
    exception_classes = [
        s for s in exception_symbols
        if "error" in s.name.lower() or "exception" in s.name.lower()
    ]

    if exception_classes:
        conventions.append(Convention(
            convention_id=_make_id("error", "custom_exceptions"),
            convention_type=ConventionType.ERROR_HANDLING,
            name="Custom exception classes",
            description="Codebase defines custom exception/error classes for structured error handling",
            evidence=[s.name for s in exception_classes[:10]],
            confidence=0.9,
            affected_symbols=[s.symbol_id for s in exception_classes],
        ))

    # Check for try/except patterns in Python files
    files_with_try = []
    for path, content in contents.items():
        if path.endswith(".py") and ("try:" in content or "except " in content):
            files_with_try.append(path)

    if len(files_with_try) >= 3:
        conventions.append(Convention(
            convention_id=_make_id("error", "try_except"),
            convention_type=ConventionType.ERROR_HANDLING,
            name="Explicit try/except error handling",
            description="Python files use explicit try/except blocks for error handling",
            evidence=files_with_try[:10],
            confidence=0.8,
            affected_files=files_with_try,
        ))

    return conventions


def _detect_config_organization(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect configuration organization patterns."""
    conventions: list[Convention] = []

    config_files = [
        f for f in files
        if any(kw in f.path.lower() for kw in [
            "config", "settings", ".env", "pyproject.toml",
            "setup.py", "setup.cfg", "dockerfile", "docker-compose",
        ])
    ]

    if config_files:
        conventions.append(Convention(
            convention_id=_make_id("config", "organization"),
            convention_type=ConventionType.CONFIG_ORGANIZATION,
            name="Centralized configuration",
            description="Configuration is organized in dedicated config files",
            evidence=[f.path for f in config_files],
            confidence=0.9,
            affected_files=[f.path for f in config_files],
        ))

    return conventions


def _detect_entrypoint_pattern(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect entry point patterns."""
    conventions: list[Convention] = []

    # Check for CLI entrypoints
    entrypoints = [f for f in files if f.is_entrypoint]
    if entrypoints:
        conventions.append(Convention(
            convention_id=_make_id("entrypoint", "cli"),
            convention_type=ConventionType.ENTRYPOINT_PATTERN,
            name="CLI entrypoint",
            description="Application has defined CLI entry points",
            evidence=[f.path for f in entrypoints],
            confidence=0.95,
            affected_files=[f.path for f in entrypoints],
        ))

    # Check for __main__.py pattern
    main_files = [f for f in files if f.path.endswith("__main__.py")]
    if main_files:
        conventions.append(Convention(
            convention_id=_make_id("entrypoint", "main_module"),
            convention_type=ConventionType.ENTRYPOINT_PATTERN,
            name="__main__.py entrypoint pattern",
            description="Modules use __main__.py for direct execution",
            evidence=[f.path for f in main_files],
            confidence=0.9,
            affected_files=[f.path for f in main_files],
        ))

    return conventions


def _detect_dependency_direction(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    relations: list[Relation],
    contents: dict[str, str],
) -> list[Convention]:
    """Detect dependency direction patterns."""
    conventions: list[Convention] = []

    # Check if cli -> ingest -> models direction is followed
    cli_files = [f for f in files if "/cli/" in f.path]
    model_files = [f for f in files if "/models/" in f.path]
    ingest_files = [f for f in files if "/ingest/" in f.path]

    if cli_files and model_files and ingest_files:
        conventions.append(Convention(
            convention_id=_make_id("dep", "layered"),
            convention_type=ConventionType.LAYERED_ARCHITECTURE,
            name="Layered architecture",
            description="Code follows layered architecture: CLI → business logic (ingest/retrieval) → models",
            evidence=[
                f"CLI layer: {len(cli_files)} files",
                f"Business logic: {len(ingest_files)} files",
                f"Models: {len(model_files)} files",
            ],
            confidence=0.8,
            affected_files=[f.path for f in cli_files + ingest_files + model_files],
        ))

    return conventions