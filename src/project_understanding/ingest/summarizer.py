"""File-level summarizer using LLM.

Generates structured summaries for files, with heuristic fallback
when LLM is unavailable.
"""

from __future__ import annotations

from pathlib import Path

from project_understanding.adapters.llm_base import LLMProvider
from project_understanding.ingest.parser_base import ParsedFile
from project_understanding.models.entities import File, Symbol
from project_understanding.ingest.business_glossary import detect_business_context
from project_understanding.models.summaries import Summary, SummaryLevel, SummarySource


SYSTEM_PROMPT = """You are a code analysis assistant. Summarize the following source code file concisely.
Focus on:
1. Main purpose and responsibility of the file
2. Key classes, functions, or components defined
3. Notable dependencies or interactions
Keep the summary to 2-4 sentences. Be specific and technical.

If the code relates to logistics, airport cargo, shipping, or freight operations,
also append a brief note about the business domain in Vietnamese."""


def generate_file_summary(
    file: File,
    content: str,
    symbols: list[Symbol],
    llm: LLMProvider | None = None,
) -> Summary:
    """Generate a summary for a source code file.

    Uses LLM if available, otherwise falls back to heuristic summary.

    Args:
        file: File entity.
        content: File content as string.
        symbols: Symbols found in the file.
        llm: Optional LLM provider.

    Returns:
        Summary entity for the file.
    """
    summary_id = Summary.make_summary_id(file.file_id, SummaryLevel.FILE)

    # Detect business context in Vietnamese from code content
    business_ctx = detect_business_context(content) if content.strip() else ""

    if llm and content.strip():
        text = _generate_llm_summary(file, content, symbols, llm)
        source = SummarySource.LLM
    else:
        text = _generate_heuristic_summary(file, content, symbols)
        source = SummarySource.HEURISTIC

    return Summary(
        summary_id=summary_id,
        target_id=file.file_id,
        target_type="file",
        content=text,
        level=SummaryLevel.FILE,
        generated_by=source,
        language=file.language,
        business_context=business_ctx,
    )


def _generate_llm_summary(
    file: File,
    content: str,
    symbols: list[Symbol],
    llm: LLMProvider,
) -> str:
    """Generate summary using LLM."""
    # Build context with symbol list
    symbol_list = ", ".join(
        f"{s.kind.value} '{s.name}'" for s in symbols[:20]
    )

    prompt = f"""File: {file.path}
Language: {file.language}
Symbols defined: {symbol_list if symbol_list else 'None detected'}

```{file.language}
{content[:3000]}
{'... (truncated)' if len(content) > 3000 else ''}
```"""

    result = llm.generate(prompt=prompt, system=SYSTEM_PROMPT)
    if result.startswith("[LLM Error:"):
        # Fall back to heuristic
        return _generate_heuristic_summary(file, content, symbols)
    return result.strip()


def _generate_heuristic_summary(
    file: File,
    content: str,
    symbols: list[Symbol],
) -> str:
    """Generate a heuristic summary without LLM."""
    parts: list[str] = []

    # File description
    parts.append(f"File '{Path(file.path).name}' ({file.language})")

    # Symbol summary
    if symbols:
        kinds: dict[str, list[str]] = {}
        for sym in symbols:
            if sym.kind.value not in kinds:
                kinds[sym.kind.value] = []
            kinds[sym.kind.value].append(sym.name)

        kind_parts = []
        for kind, names in kinds.items():
            if len(names) <= 3:
                kind_parts.append(f"{kind}(s): {', '.join(names)}")
            else:
                kind_parts.append(f"{kind}(s): {', '.join(names[:3])} +{len(names) - 3} more")

        parts.append("Contains " + "; ".join(kind_parts))

    # Size indicator
    line_count = content.count("\n") + 1
    parts.append(f"({line_count} lines)")

    return ". ".join(parts)