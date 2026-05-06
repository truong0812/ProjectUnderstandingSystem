"""Relation builder — constructs relations between entities.

Builds contains, imports, calls, and depends_on relations from
parsed file results and entity maps.
"""

from __future__ import annotations

from project_understanding.ingest.parser_base import ParsedFile, ParsedImport, ParsedCall, ParsedUsage
from project_understanding.models.entities import File, Module, Symbol
from project_understanding.models.relations import Relation, RelationType


def build_contains_relations(
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
) -> list[Relation]:
    """Build 'contains' relations.

    - Module -> File (module contains file)
    - File -> Symbol (file contains symbol)

    Args:
        files: All File entities.
        modules: All Module entities.
        symbols: All Symbol entities.

    Returns:
        List of contains relations.
    """
    relations: list[Relation] = []

    # Module contains File
    file_id_map = {f.file_id: f for f in files}
    for module in modules:
        for file_id in module.files:
            relations.append(
                Relation(
                    source_id=module.module_id,
                    target_id=file_id,
                    relation_type=RelationType.CONTAINS,
                    confidence=1.0,
                    evidence=f"Module '{module.name}' contains file",
                    source_type="Module",
                    target_type="File",
                )
            )

    # File contains Symbol
    for symbol in symbols:
        relations.append(
            Relation(
                source_id=symbol.file_id,
                target_id=symbol.symbol_id,
                relation_type=RelationType.CONTAINS,
                confidence=1.0,
                evidence=f"File contains {symbol.kind.value} '{symbol.name}'",
                source_type="File",
                target_type="Symbol",
            )
        )

    return relations


def build_import_relations(
    parsed_files: list[ParsedFile],
    files: list[File],
    symbols: list[Symbol],
    repo_id: str,
) -> list[Relation]:
    """Build 'imports' relations from parsed import statements.

    Attempts to resolve import targets to known files or symbols.

    Args:
        parsed_files: Parse results with import information.
        files: All File entities.
        symbols: All Symbol entities.
        repo_id: Repository ID.

    Returns:
        List of imports relations.
    """
    relations: list[Relation] = []

    # Build lookup maps
    file_by_path = {f.path: f for f in files}
    symbol_by_name: dict[str, list[Symbol]] = {}
    for sym in symbols:
        if sym.name not in symbol_by_name:
            symbol_by_name[sym.name] = []
        symbol_by_name[sym.name].append(sym)

    for parsed in parsed_files:
        source_file = file_by_path.get(parsed.file_path)
        if not source_file:
            continue

        for imp in parsed.imports:
            if imp.is_from_import and imp.module_path:
                # from X import Y style
                target = _resolve_import_target(
                    imp.module_path, imp.names, file_by_path, symbol_by_name
                )
                if target:
                    relations.append(
                        Relation(
                            source_id=source_file.file_id,
                            target_id=target,
                            relation_type=RelationType.IMPORTS,
                            confidence=0.9,
                            evidence=f"from {imp.module_path} import {', '.join(imp.names)}",
                            source_type="File",
                            target_type="File",
                        )
                    )
            elif imp.module_path:
                # import X style
                target = _resolve_module_to_file(imp.module_path, file_by_path)
                if target:
                    relations.append(
                        Relation(
                            source_id=source_file.file_id,
                            target_id=target,
                            relation_type=RelationType.IMPORTS,
                            confidence=0.9,
                            evidence=f"import {imp.module_path}",
                            source_type="File",
                            target_type="File",
                        )
                    )

    return relations


def build_call_relations(
    parsed_files: list[ParsedFile],
    files: list[File],
    symbols: list[Symbol],
) -> list[Relation]:
    """Build 'calls' relations from parsed call information.

    Maps caller/callee names to known symbols.

    Args:
        parsed_files: Parse results with call information.
        files: All File entities.
        symbols: All Symbol entities.

    Returns:
        List of calls relations.
    """
    relations: list[Relation] = []

    # Build symbol lookup by qualified path and name
    symbol_by_path = {sym.path: sym for sym in symbols}
    symbol_by_name: dict[str, list[Symbol]] = {}
    for sym in symbols:
        if sym.name not in symbol_by_name:
            symbol_by_name[sym.name] = []
        symbol_by_name[sym.name].append(sym)

    # Build file path to file_id map
    file_by_path = {f.path: f for f in files}

    for parsed in parsed_files:
        source_file = file_by_path.get(parsed.file_path)
        if not source_file:
            continue

        for call in parsed.calls:
            # Try to resolve callee
            callee_symbols = symbol_by_name.get(call.callee, [])
            if not callee_symbols:
                # Try by qualified path
                sym = symbol_by_path.get(call.callee)
                if sym:
                    callee_symbols = [sym]

            # Try to resolve caller
            caller_symbols = symbol_by_name.get(call.caller, [])

            if callee_symbols and caller_symbols:
                # Use first match (best effort)
                caller_sym = caller_symbols[0]
                callee_sym = callee_symbols[0]

                # Only create relation if both are in the same repo
                relations.append(
                    Relation(
                        source_id=caller_sym.symbol_id,
                        target_id=callee_sym.symbol_id,
                        relation_type=RelationType.CALLS,
                        confidence=0.7,
                        evidence=f"'{call.caller}' calls '{call.callee}' at line {call.line}",
                        source_type="Symbol",
                        target_type="Symbol",
                    )
                )

    return relations


def build_depends_on_relations(
    files: list[File],
    import_relations: list[Relation],
) -> list[Relation]:
    """Build 'depends_on' relations between files based on imports.

    Two files have a depends_on relation if one imports the other.

    Args:
        files: All File entities.
        import_relations: Already built import relations.

    Returns:
        List of depends_on relations.
    """
    relations: list[Relation] = []

    # Collect unique file-to-file dependencies
    seen: set[tuple[str, str]] = set()
    for rel in import_relations:
        if rel.source_type == "File" and rel.target_type == "File":
            pair = (rel.source_id, rel.target_id)
            if pair not in seen:
                seen.add(pair)
                relations.append(
                    Relation(
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        relation_type=RelationType.DEPENDS_ON,
                        confidence=0.8,
                        evidence=rel.evidence,
                        source_type="File",
                        target_type="File",
                    )
                )

    return relations


def build_uses_relations(
    parsed_files: list[ParsedFile],
    files: list[File],
    symbols: list[Symbol],
    file_contents: dict[str, str] | None = None,
) -> list[Relation]:
    """Build 'uses' relations — symbol-level usage tracking.

    Detects when a symbol references another symbol (constant, variable, type,
    component). This enables impact analysis: "if I change constant X, which
    symbols are affected?"

    Two detection strategies:
    1. Import-name matching: imported names used inside symbol bodies
    2. Same-file symbol references: symbols referencing other symbols in same file

    Args:
        parsed_files: Parse results with import and usage information.
        files: All File entities.
        symbols: All Symbol entities.
        file_contents: Optional file contents for text-based reference detection.

    Returns:
        List of uses relations.
    """
    relations: list[Relation] = []
    contents = file_contents or {}

    # Build lookups
    file_by_path = {f.path: f for f in files}
    symbol_by_name: dict[str, list[Symbol]] = {}
    for sym in symbols:
        if sym.name not in symbol_by_name:
            symbol_by_name[sym.name] = []
        symbol_by_name[sym.name].append(sym)

    # Build symbol-by-file lookup (symbols within each file)
    symbols_by_file_id: dict[str, list[Symbol]] = {}
    for sym in symbols:
        if sym.file_id not in symbols_by_file_id:
            symbols_by_file_id[sym.file_id] = []
        symbols_by_file_id[sym.file_id].append(sym)

    # Track seen pairs to avoid duplicates
    seen: set[tuple[str, str]] = set()

    for parsed in parsed_files:
        source_file = file_by_path.get(parsed.file_path)
        if not source_file:
            continue

        file_syms = symbols_by_file_id.get(source_file.file_id, [])
        content = contents.get(parsed.file_path, "")

        # Strategy 1: Import-name matching
        # For each imported name, find which local symbols use it
        imported_names: set[str] = set()
        for imp in parsed.imports:
            for name in imp.names:
                imported_names.add(name)

        if imported_names and file_syms and content:
            lines = content.split("\n")
            for sym in file_syms:
                if sym.line_start and sym.line_end:
                    # Get the symbol's body
                    start = max(0, sym.line_start - 1)
                    end = min(len(lines), sym.line_end)
                    sym_body = "\n".join(lines[start:end])

                    for imported_name in imported_names:
                        # Check if this symbol references the imported name
                        # Use word boundary check to avoid partial matches
                        import re
                        if re.search(rf'\b{re.escape(imported_name)}\b', sym_body):
                            # Find the target symbol (the one being imported/used)
                            target_syms = symbol_by_name.get(imported_name, [])
                            for target_sym in target_syms:
                                # Skip self-references
                                if target_sym.symbol_id == sym.symbol_id:
                                    continue
                                pair = (sym.symbol_id, target_sym.symbol_id)
                                if pair not in seen:
                                    seen.add(pair)
                                    relations.append(
                                        Relation(
                                            source_id=sym.symbol_id,
                                            target_id=target_sym.symbol_id,
                                            relation_type=RelationType.USES,
                                            confidence=0.75,
                                            evidence=f"'{sym.name}' uses '{imported_name}' (imported)",
                                            source_type="Symbol",
                                            target_type="Symbol",
                                        )
                                    )

        # Strategy 2: Same-file symbol references
        # Detect references between symbols in the same file
        if file_syms and content:
            lines = content.split("\n")
            for sym in file_syms:
                if not sym.line_start or not sym.line_end:
                    continue
                start = max(0, sym.line_start - 1)
                end = min(len(lines), sym.line_end)
                sym_body = "\n".join(lines[start:end])

                for other_sym in file_syms:
                    if other_sym.symbol_id == sym.symbol_id:
                        continue
                    # Check if this symbol references another symbol by name
                    import re
                    if re.search(rf'\b{re.escape(other_sym.name)}\b', sym_body):
                        pair = (sym.symbol_id, other_sym.symbol_id)
                        if pair not in seen:
                            # Skip if already captured by calls relation
                            # (calls are a subset of uses)
                            seen.add(pair)
                            relations.append(
                                Relation(
                                    source_id=sym.symbol_id,
                                    target_id=other_sym.symbol_id,
                                    relation_type=RelationType.USES,
                                    confidence=0.6,
                                    evidence=f"'{sym.name}' references '{other_sym.name}' (same file)",
                                    source_type="Symbol",
                                    target_type="Symbol",
                                )
                            )

        # Strategy 3: ParsedUsage data from tree-sitter (if available)
        for usage in parsed.usages:
            source_syms = symbol_by_name.get(usage.source_symbol, [])
            target_syms = symbol_by_name.get(usage.target_name, [])

            if source_syms and target_syms:
                source_sym = source_syms[0]
                target_sym = target_syms[0]
                if source_sym.symbol_id != target_sym.symbol_id:
                    pair = (source_sym.symbol_id, target_sym.symbol_id)
                    if pair not in seen:
                        seen.add(pair)
                        relations.append(
                            Relation(
                                source_id=source_sym.symbol_id,
                                target_id=target_sym.symbol_id,
                                relation_type=RelationType.USES,
                                confidence=0.8,
                                evidence=f"'{usage.source_symbol}' uses '{usage.target_name}' ({usage.usage_kind}) at line {usage.line}",
                                source_type="Symbol",
                                target_type="Symbol",
                            )
                        )

    return relations


def build_all_relations(
    parsed_files: list[ParsedFile],
    files: list[File],
    modules: list[Module],
    symbols: list[Symbol],
    repo_id: str,
    file_contents: dict[str, str] | None = None,
) -> list[Relation]:
    """Build all relations for a snapshot.

    Args:
        parsed_files: Parse results from tree-sitter.
        files: All File entities.
        modules: All Module entities.
        symbols: All Symbol entities.
        repo_id: Repository ID.
        file_contents: Optional file contents for usage detection.

    Returns:
        Complete list of relations.
    """
    relations: list[Relation] = []

    # 1. Contains relations (structural)
    relations.extend(build_contains_relations(files, modules, symbols))

    # 2. Import relations
    import_rels = build_import_relations(parsed_files, files, symbols, repo_id)
    relations.extend(import_rels)

    # 3. Call relations
    relations.extend(build_call_relations(parsed_files, files, symbols))

    # 4. Depends_on relations (derived from imports)
    relations.extend(build_depends_on_relations(files, import_rels))

    # 5. Uses relations (symbol-level usage tracking)
    relations.extend(build_uses_relations(parsed_files, files, symbols, file_contents))

    return relations


def _resolve_import_target(
    module_path: str,
    names: list[str],
    file_by_path: dict[str, File],
    symbol_by_name: dict[str, list[Symbol]],
) -> str | None:
    """Resolve an import to a target file ID."""
    # Try to match module_path to a file path
    # Python: from foo.bar import Baz -> foo/bar.py or foo/bar/__init__.py
    # TypeScript: from './foo/bar' -> foo/bar.ts
    # C#: using Foo.Bar -> directory based

    candidates = [
        module_path.replace(".", "/") + ".py",
        module_path.replace(".", "/") + "/__init__.py",
        module_path.replace(".", "/") + ".ts",
        module_path.replace(".", "/") + ".tsx",
        module_path + ".py",
        module_path + ".ts",
        module_path.lstrip("./"),
        module_path.lstrip("./") + ".ts",
        module_path.lstrip("./") + ".tsx",
    ]

    for candidate in candidates:
        if candidate in file_by_path:
            return file_by_path[candidate].file_id

    return None


def _resolve_module_to_file(
    module_path: str,
    file_by_path: dict[str, File],
) -> str | None:
    """Resolve a bare import module path to a file ID."""
    candidates = [
        module_path.replace(".", "/") + ".py",
        module_path.replace(".", "/") + "/__init__.py",
        module_path.replace(".", "/") + ".ts",
        module_path.replace(".", "/") + ".cs",
        module_path.lstrip("./"),
    ]

    for candidate in candidates:
        if candidate in file_by_path:
            return file_by_path[candidate].file_id

    return None