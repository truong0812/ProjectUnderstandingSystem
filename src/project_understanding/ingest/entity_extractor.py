"""Entity extractor — converts parsed files into knowledge entities.

Transforms ParsedFile results from tree-sitter parsers into File, Module,
and Symbol entities for the knowledge base.
"""

from __future__ import annotations

from pathlib import Path

from project_understanding.ingest.language_detect import (
    detect_config_file,
    detect_entrypoint,
    detect_language,
    detect_test_file,
    is_supported_language,
)
from project_understanding.ingest.parser_base import ParsedFile, ParsedSymbol
from project_understanding.ingest.scanner import ScannedFile
from project_understanding.models.entities import File, Module, Symbol, SymbolKind


def create_file_entity(scanned: ScannedFile, snapshot_id: str, repo_id: str) -> File:
    """Create a File entity from a scanned file.

    Args:
        scanned: Scanned file metadata.
        snapshot_id: Parent snapshot ID.
        repo_id: Repository ID.

    Returns:
        File entity with detected language and file type flags.
    """
    language = detect_language(scanned.path, scanned.extension)
    is_entry = detect_entrypoint(scanned.path, language)
    is_test = detect_test_file(scanned.path)
    is_config = detect_config_file(scanned.path)

    file_id = File.make_file_id(repo_id, scanned.path, scanned.hash)

    return File(
        file_id=file_id,
        snapshot_id=snapshot_id,
        path=scanned.path,
        language=language,
        hash=scanned.hash,
        size=scanned.size,
        is_entrypoint=is_entry,
        is_test=is_test,
        is_config=is_config,
    )


def create_symbol_entities(
    parsed_symbols: list[ParsedSymbol],
    file_id: str,
    repo_id: str,
    file_path: str,
) -> list[Symbol]:
    """Create Symbol entities from parsed symbols, flattening nested children.

    Args:
        parsed_symbols: Symbols from tree-sitter parsing.
        file_id: Parent file ID.
        repo_id: Repository ID.
        file_path: File path for ID generation.

    Returns:
        Flat list of Symbol entities (including nested children).
    """
    symbols: list[Symbol] = []

    for parsed in parsed_symbols:
        # Convert kind string to SymbolKind enum
        kind = _map_symbol_kind(parsed.kind)

        symbol_id = Symbol.make_symbol_id(
            repo_id, file_path, parsed.path, parsed.hash
        )

        symbol = Symbol(
            symbol_id=symbol_id,
            file_id=file_id,
            name=parsed.name,
            kind=kind,
            path=parsed.path,
            line_start=parsed.line_start,
            line_end=parsed.line_end,
            hash=parsed.hash,
            visibility=parsed.visibility,
            is_async=parsed.is_async,
            is_static=parsed.is_static,
            parameters=parsed.parameters,
            return_type=parsed.return_type,
            docstring=parsed.docstring,
        )
        symbols.append(symbol)

        # Recursively process children (methods in class, etc.)
        if parsed.children:
            child_symbols = create_symbol_entities(
                parsed.children, file_id, repo_id, file_path
            )
            symbols.extend(child_symbols)

    return symbols


def create_module_entities(
    files: list[File],
    snapshot_id: str,
    repo_id: str,
) -> list[Module]:
    """Create Module entities by grouping files by directory.

    Uses the first directory component as module name. Files at the
    repo root are grouped into a "root" module.

    Args:
        files: List of File entities.
        snapshot_id: Parent snapshot ID.
        repo_id: Repository ID.

    Returns:
        List of Module entities.
    """
    # Group files by top-level directory
    module_map: dict[str, list[str]] = {}

    for file in files:
        parts = Path(file.path).parts
        if len(parts) > 1:
            module_name = parts[0]
        else:
            module_name = "root"

        if module_name not in module_map:
            module_map[module_name] = []
        module_map[module_name].append(file.file_id)

    modules: list[Module] = []
    for module_name, file_ids in module_map.items():
        module_id = Module.make_module_id(repo_id, module_name)
        module = Module(
            module_id=module_id,
            snapshot_id=snapshot_id,
            name=module_name,
            path_pattern=f"{module_name}/",
            files=file_ids,
        )
        modules.append(module)

    return modules


def _map_symbol_kind(kind_str: str) -> SymbolKind:
    """Map a string kind to SymbolKind enum."""
    kind_map = {
        "function": SymbolKind.FUNCTION,
        "class": SymbolKind.CLASS,
        "method": SymbolKind.METHOD,
        "interface": SymbolKind.INTERFACE,
        "type": SymbolKind.TYPE,
        "constant": SymbolKind.CONSTANT,
        "enum": SymbolKind.ENUM,
        "struct": SymbolKind.STRUCT,
        "property": SymbolKind.PROPERTY,
        "field": SymbolKind.FIELD,
        "namespace": SymbolKind.NAMESPACE,
        "variable": SymbolKind.VARIABLE,
        "constructor": SymbolKind.CONSTRUCTOR,
        "delegate": SymbolKind.DELEGATE,
    }
    return kind_map.get(kind_str, SymbolKind.FUNCTION)