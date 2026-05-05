"""Enrichment summarizer — generates symbol-level and module-level summaries.

Extends Phase 1 file-level summaries with deeper granularity:
- Symbol-level summaries for functions, classes, methods
- Module-level summaries for logical module groups
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from project_understanding.adapters.llm_base import LLMProvider
from project_understanding.models.entities import File, Module, Symbol
from project_understanding.models.summaries import Summary, SummaryLevel, SummarySource


def generate_symbol_summaries(
    symbols: list[Symbol],
    files: list[File],
    contents: dict[str, str],
    llm: LLMProvider | None = None,
) -> list[Summary]:
    """Generate summaries for individual symbols.

    Args:
        symbols: All symbols to summarize.
        files: All files (for file path lookup).
        contents: Mapping of file_path -> file_content.
        llm: Optional LLM provider.

    Returns:
        List of symbol-level summaries.
    """
    file_map = {f.file_id: f for f in files}
    summaries: list[Summary] = []

    for symbol in symbols:
        file = file_map.get(symbol.file_id)
        if not file:
            continue

        content = contents.get(file.path, "")
        if not content:
            continue

        # Extract symbol's source code
        lines = content.split("\n")
        start = max(0, symbol.line_start - 1)
        end = min(len(lines), symbol.line_end)
        symbol_code = "\n".join(lines[start:end])

        if not symbol_code.strip():
            continue

        summary_id = Summary.make_summary_id(symbol.symbol_id, SummaryLevel.SYMBOL)
        text = _summarize_symbol(symbol, symbol_code, file, llm)
        source = SummarySource.LLM if llm else SummarySource.HEURISTIC

        summaries.append(Summary(
            summary_id=summary_id,
            target_id=symbol.symbol_id,
            target_type="symbol",
            content=text,
            level=SummaryLevel.SYMBOL,
            generated_by=source,
            language=file.language,
        ))

    return summaries


def generate_module_summaries(
    modules: list[Module],
    files: list[File],
    symbols: list[Symbol],
    file_summaries: list[Summary],
    llm: LLMProvider | None = None,
) -> list[Summary]:
    """Generate summaries for modules.

    Args:
        modules: All modules to summarize.
        files: All files.
        symbols: All symbols.
        file_summaries: Existing file-level summaries for context.
        llm: Optional LLM provider.

    Returns:
        List of module-level summaries.
    """
    # Index files and summaries
    file_by_module: dict[str, list[File]] = defaultdict(list)
    for f in files:
        for m in modules:
            if _file_in_module(f, m):
                file_by_module[m.module_id].append(f)

    summary_by_file: dict[str, str] = {}
    for s in file_summaries:
        if s.target_type == "file":
            summary_by_file[s.target_id] = s.content

    symbol_by_file: dict[str, list[Symbol]] = defaultdict(list)
    for sym in symbols:
        symbol_by_file[sym.file_id].append(sym)

    summaries: list[Summary] = []

    for module in modules:
        mod_files = file_by_module.get(module.module_id, [])
        if not mod_files:
            continue

        summary_id = Summary.make_summary_id(module.module_id, SummaryLevel.MODULE)

        # Build context from file summaries and symbols
        file_descs: list[str] = []
        for f in mod_files[:15]:
            desc = f"  - {f.path}"
            fs = summary_by_file.get(f.file_id)
            if fs:
                desc += f": {fs[:100]}"
            file_symbols = symbol_by_file.get(f.file_id, [])
            if file_symbols:
                kinds = defaultdict(list)
                for sym in file_symbols:
                    kinds[sym.kind.value].append(sym.name)
                kind_str = ", ".join(
                    f"{k}({', '.join(v[:3])})" for k, v in kinds.items()
                )
                desc += f" [{kind_str}]"
            file_descs.append(desc)

        text = _summarize_module(module, file_descs, llm)
        source = SummarySource.LLM if llm else SummarySource.HEURISTIC

        summaries.append(Summary(
            summary_id=summary_id,
            target_id=module.module_id,
            target_type="module",
            content=text,
            level=SummaryLevel.MODULE,
            generated_by=source,
            language="",
        ))

    return summaries


def _summarize_symbol(
    symbol: Symbol,
    code: str,
    file: File,
    llm: LLMProvider | None = None,
) -> str:
    """Generate a summary for a single symbol."""
    if llm and len(code.strip()) > 20:
        prompt = f"""Summarize this {symbol.kind.value} in 1-2 sentences.
Focus on: purpose, parameters (if function), return value, side effects.

Name: {symbol.name}
File: {file.path}

```{file.language}
{code[:1500]}
```"""
        result = llm.generate(prompt=prompt, system="You are a code documentation assistant.")
        if not result.startswith("[LLM Error:"):
            return result.strip()

    # Heuristic summary
    parts = [f"{symbol.kind.value.capitalize()} '{symbol.name}'"]
    line_count = code.count("\n") + 1

    if symbol.kind.value == "class":
        # Count methods
        method_lines = [l for l in code.split("\n") if l.strip().startswith("def ")]
        if method_lines:
            parts.append(f"with {len(method_lines)} method(s)")
        parts.append(f"({line_count} lines)")
    elif symbol.kind.value in ("function", "method"):
        # Check for parameters
        first_line = code.split("\n")[0] if code else ""
        if "(" in first_line and ")" in first_line:
            parts.append(f"defined at line {symbol.line_start}")
        parts.append(f"({line_count} lines)")
    else:
        parts.append(f"({line_count} lines)")

    return ". ".join(parts)


def _summarize_module(
    module: Module,
    file_descriptions: list[str],
    llm: LLMProvider | None = None,
) -> str:
    """Generate a summary for a module."""
    if llm and file_descriptions:
        prompt = f"""Summarize this code module in 2-3 sentences.
Focus on: overall responsibility, key components, design patterns.

Module: {module.name}
Files ({len(file_descriptions)}):
{chr(10).join(file_descriptions[:15])}"""
        result = llm.generate(prompt=prompt, system="You are a code documentation assistant.")
        if not result.startswith("[LLM Error:"):
            return result.strip()

    # Heuristic summary
    parts = [f"Module '{module.name}'"]
    if file_descriptions:
        parts.append(f"contains {len(file_descriptions)} file(s)")
        # Extract key symbol kinds
        parts.append(f"Files include: {', '.join(d.strip('- ').split(':')[0] for d in file_descriptions[:5])}")
    else:
        parts.append("(empty module)")

    return ". ".join(parts)


def _file_in_module(file: File, module: Module) -> bool:
    """Check if a file belongs to a module based on path pattern."""
    if module.path_pattern and module.path_pattern != "*":
        import fnmatch
        return fnmatch.fnmatch(file.path, module.path_pattern)
    return file.path.startswith(module.name.replace(".", "/")) or \
           any(f.path == file.path for f in [])