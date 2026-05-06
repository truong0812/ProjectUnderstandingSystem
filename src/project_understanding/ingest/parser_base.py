"""Abstract parser interface using tree-sitter.

Defines the common interface that all language parsers must implement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class ParsedImport:
    """An import statement found in source code."""

    module_path: str = ""  # What is being imported from
    names: list[str] = field(default_factory=list)  # Specific names imported
    is_from_import: bool = False  # True for 'from X import Y' style
    line: int = 0


@dataclass
class ParsedSymbol:
    """A symbol (function, class, etc.) found in source code."""

    name: str
    kind: str  # function, class, method, interface, etc.
    path: str  # Qualified name
    line_start: int = 0
    line_end: int = 0
    hash: str = ""
    visibility: str = "unknown"
    is_async: bool = False
    is_static: bool = False
    parameters: list[str] = field(default_factory=list)
    return_type: str = ""
    docstring: str = ""
    children: list[ParsedSymbol] = field(default_factory=list)  # Nested symbols (methods in class)


@dataclass
class ParsedCall:
    """A function/method call found in source code."""

    caller: str = ""  # Name of the calling symbol
    callee: str = ""  # Name of the called symbol
    line: int = 0


@dataclass
class ParsedUsage:
    """A symbol usage/reference (constant, variable, type, component reference)."""

    source_symbol: str = ""  # Name of the symbol containing the usage
    target_name: str = ""     # Name of the referenced symbol
    usage_kind: str = ""      # "constant", "variable", "type", "component", "identifier"
    line: int = 0


@dataclass
class ParsedFile:
    """Complete parse result for a single file."""

    file_path: str
    language: str
    symbols: list[ParsedSymbol] = field(default_factory=list)
    imports: list[ParsedImport] = field(default_factory=list)
    calls: list[ParsedCall] = field(default_factory=list)
    usages: list[ParsedUsage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ParserInterface(Protocol):
    """Interface that all language parsers must implement."""

    def parse(self, file_path: str, content: str) -> ParsedFile:
        """Parse a source file and extract symbols, imports, and calls.

        Args:
            file_path: Relative file path.
            content: File content as string.

        Returns:
            ParsedFile with extracted information.
        """
        ...


def compute_symbol_hash(content: str, line_start: int, line_end: int) -> str:
    """Compute a hash for a symbol based on its content.

    Uses the text content between line_start and line_end to create
    a stable hash that identifies the symbol's body.

    Args:
        content: Full file content.
        line_start: Start line (1-based).
        line_end: End line (1-based).

    Returns:
        SHA-256 hex digest of the symbol body.
    """
    import hashlib

    lines = content.split("\n")
    # Convert 1-based to 0-based indexing
    start_idx = max(0, line_start - 1)
    end_idx = min(len(lines), line_end)
    symbol_text = "\n".join(lines[start_idx:end_idx])
    return hashlib.sha256(symbol_text.encode()).hexdigest()[:12]


def extract_docstring(content: str, line_start: int) -> str:
    """Extract docstring following a symbol definition.

    Looks for triple-quoted strings or // comments immediately after
    the symbol definition line.

    Args:
        content: Full file content.
        line_start: Line where the symbol starts (1-based).

    Returns:
        Extracted docstring or empty string.
    """
    lines = content.split("\n")
    if line_start >= len(lines):
        return ""

    # Look at the line of the definition and a few lines after
    start_idx = line_start  # 0-based, line after definition
    if start_idx >= len(lines):
        return ""

    # Check for triple-quoted docstring (Python style)
    line = lines[start_idx].strip()
    if line.startswith('"""') or line.startswith("'''"):
        quote = line[:3]
        # Single-line docstring
        if line.endswith(quote) and len(line) > 3:
            return line[3:-3].strip()
        # Multi-line docstring
        doc_lines = []
        for i in range(start_idx, min(start_idx + 20, len(lines))):
            doc_line = lines[i].strip()
            if i > start_idx and doc_line.endswith(quote):
                doc_lines.append(doc_line[:-3])
                break
            if i == start_idx:
                doc_lines.append(doc_line[3:])
            else:
                doc_lines.append(doc_line)
        return " ".join(doc_lines).strip()

    # Check for // comment (C-style)
    if line.startswith("//"):
        comment_lines = []
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            doc_line = lines[i].strip()
            if doc_line.startswith("//"):
                comment_lines.append(doc_line[2:].strip())
            else:
                break
        return " ".join(comment_lines).strip()

    # Check for /// XML doc comment (C# style)
    if line.startswith("///"):
        comment_lines = []
        for i in range(start_idx, min(start_idx + 10, len(lines))):
            doc_line = lines[i].strip()
            if doc_line.startswith("///"):
                comment_lines.append(doc_line[3:].strip())
            else:
                break
        return " ".join(comment_lines).strip()

    return ""