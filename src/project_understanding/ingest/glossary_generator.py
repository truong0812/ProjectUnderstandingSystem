"""Domain glossary generator — auto-detect terminology from codebase.

Analyzes source code, comments, variable names, and API endpoints
to identify domain-specific terms, acronyms, and jargon.

Two modes:
    1. LLM-based: GPT/Llama analyzes summaries → rich glossary with translations
    2. Heuristic: Regex-based extraction of ALL_CAPS terms, acronyms, comments
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from project_understanding.models.glossary import (
    Glossary,
    GlossaryCategory,
    GlossaryEntry,
)
from project_understanding.models.entities import File, Symbol
from project_understanding.models.summaries import Summary

# Known tech acronyms to filter out (not domain-specific)
TECH_ACRONYMS = {
    "API", "URL", "HTTP", "HTTPS", "REST", "JSON", "XML", "HTML", "CSS",
    "SQL", "ORM", "CRUD", "JWT", "TLS", "SSL", "DNS", "TCP", "UDP",
    "SSH", "FTP", "CSV", "PDF", "PNG", "JPEG", "SVG", "GIT", "SVN",
    "CI", "CD", "CDN", "SDK", "IDE", "OS", "UI", "UX", "IO", "CPU",
    "GPU", "RAM", "ROM", "DB", "NPM", "YARN", "ESLINT", "TS", "JS",
    "TSX", "JSX", "ENV", "LOG", "ERR", "WARN", "DEBUG", "INFO",
    "TODO", "FIXME", "HACK", "NOTE", "VIP", "EOF", "UUID", "GUID",
    "POST", "GET", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS",
    "UTC", "ISO", "UTF", "ASCII", "MIME",
}

# Common English words in ALL_CAPS that aren't acronyms
NOISE_CAPS = {
    "TRUE", "FALSE", "NULL", "UNDEFINED", "NONE", "NAN", "INF",
    "DEFAULT", "EXPORT", "IMPORT", "RETURN", "THROW", "NEW", "DELETE",
    "CLASS", "FUNCTION", "CONST", "LET", "VAR", "TYPE", "INTERFACE",
    "MODULE", "PACKAGE", "PRIVATE", "PUBLIC", "PROTECTED", "STATIC",
    "FINAL", "ABSTRACT", "EXTENDS", "IMPLEMENTS", "REQUIRE", "FROM",
    "ERROR", "SUCCESS", "FAILURE", "PENDING", "ACTIVE", "DISABLED",
    "ENABLED", "HIDDEN", "VISIBLE", "SELECTED", "LOADING", "OPEN",
    "CLOSED", "LEFT", "RIGHT", "TOP", "BOTTOM", "CENTER", "START",
    "END", "BEGIN", "FINISH", "FIRST", "LAST", "NEXT", "PREV",
    "UP", "DOWN", "IN", "OUT", "ON", "OFF", "YES", "NO",
}


def generate_glossary(
    files: list[File],
    symbols: list[Symbol],
    summaries: list[Summary],
    path_contents: dict[str, str],
    llm=None,
    project_name: str = "",
) -> Glossary:
    """Generate a domain glossary from the codebase.

    Args:
        files: List of file entities.
        symbols: List of symbol entities.
        summaries: List of summaries.
        path_contents: Mapping of file path → source content.
        llm: Optional LLM provider for rich analysis.
        project_name: Project name for context.

    Returns:
        Glossary with auto-detected entries.
    """
    if llm:
        try:
            return _generate_glossary_llm(files, symbols, summaries, llm, project_name)
        except Exception:
            pass  # Fall back to heuristic

    return _generate_glossary_heuristic(files, symbols, summaries, path_contents)


def _generate_glossary_llm(
    files: list[File],
    symbols: list[Symbol],
    summaries: list[Summary],
    llm,
    project_name: str,
) -> Glossary:
    """Use LLM to analyze codebase summaries and generate glossary.

    Sends file summaries, symbol names, and module names to the LLM
    and asks it to identify domain-specific terminology.
    """
    # Build context from summaries (limit to avoid token overflow)
    context_parts = []
    char_limit = 6000
    total_chars = 0

    # Add file summaries
    for s in summaries[:50]:
        if total_chars > char_limit:
            break
        context_parts.append(f"- {s.content}")
        total_chars += len(s.content)

    # Add symbol names grouped by file
    sym_names = list({sym.name for sym in symbols[:100]})
    if sym_names:
        context_parts.append(f"\nSymbol names: {', '.join(sym_names[:50])}")

    # Add file paths for context
    paths = [f.path for f in files[:30]]
    context_parts.append(f"\nFile paths: {', '.join(paths)}")

    context = "\n".join(context_parts)

    prompt = f"""Analyze this codebase and identify domain-specific terms, acronyms, and jargon.
This is NOT a generic technical project — focus on business/domain terms unique to this codebase.

Project: {project_name}

Codebase analysis:
{context}

Respond in JSON format only (no markdown, no code fences):
{{
  "entries": [
    {{
      "term": "TERM",
      "definition": "Brief explanation",
      "category": "domain|technical|acronym|pattern|framework",
      "languages": {{"vi": "Vietnamese translation (if applicable)"}}
    }}
  ]
}}

Rules:
- Focus on BUSINESS DOMAIN terms, not generic tech (skip API, URL, etc.)
- Include acronyms that are specific to this project's domain
- If the domain appears to be Vietnamese/international, add Vietnamese translations
- Limit to 15-25 most important terms
- Category must be one of: domain, technical, acronym, pattern, framework
"""

    response = llm.generate(prompt, max_tokens=2000, temperature=0.3)

    # Parse LLM response
    import json
    entries = []

    # Try to extract JSON from response
    response = response.strip()
    # Remove code fences if present
    if response.startswith("```"):
        response = re.sub(r"^```\w*\n?", "", response)
        response = re.sub(r"\n?```$", "", response)

    try:
        data = json.loads(response)
        for item in data.get("entries", []):
            cat_str = item.get("category", "domain")
            try:
                category = GlossaryCategory(cat_str)
            except ValueError:
                category = GlossaryCategory.DOMAIN

            entries.append(GlossaryEntry(
                term=item.get("term", ""),
                definition=item.get("definition", ""),
                category=category,
                languages=item.get("languages", {}),
                confidence=0.85,
                source="llm",
            ))
    except (json.JSONDecodeError, KeyError):
        # Fallback: parse line by line
        pass

    return Glossary(
        entries=entries,
        project_name=project_name,
    )


def _generate_glossary_heuristic(
    files: list[File],
    symbols: list[Symbol],
    summaries: list[Summary],
    path_contents: dict[str, str],
) -> Glossary:
    """Extract glossary terms using heuristic pattern matching.

    Detects:
        - ALL_CAPS identifiers (potential acronyms)
        - PascalCase compound names (potential domain terms)
        - Comments with term definitions
    """
    entries: list[GlossaryEntry] = []
    seen_terms: set[str] = set()

    # 1. Extract ALL_CAPS identifiers from source code
    caps_counter: Counter = Counter()
    caps_context: dict[str, list[str]] = {}

    for path, content in path_contents.items():
        # Find ALL_CAPS words (2+ chars)
        matches = re.findall(r'\b([A-Z]{2,}(?:_[A-Z]+)*)\b', content)
        for match in matches:
            # Skip known tech acronyms and noise
            word = match.split("_")[0] if "_" in match else match
            if word in TECH_ACRONYMS or word in NOISE_CAPS:
                continue
            if len(word) < 2:
                continue

            caps_counter[match] += 1
            if match not in caps_context:
                caps_context[match] = []
            if len(caps_context[match]) < 3:
                caps_context[match].append(path)

    # Add top ALL_CAPS terms as acronyms
    for term, count in caps_counter.most_common(20):
        if term in seen_terms:
            continue
        if count < 2:  # Must appear at least twice
            continue
        seen_terms.add(term)
        entries.append(GlossaryEntry(
            term=term,
            definition=f"Acronym/constant used in {len(caps_context.get(term, []))} files",
            category=GlossaryCategory.ACRONYM,
            context=caps_context.get(term, [])[:3],
            confidence=0.6,
            source="heuristic",
        ))

    # 2. Extract domain terms from symbol names (PascalCase compounds)
    sym_counter: Counter = Counter()
    for sym in symbols:
        # Split PascalCase into words
        words = re.findall(r'[A-Z][a-z]+', sym.name)
        for word in words:
            if len(word) > 3:  # Skip short common words
                sym_counter[word] += 1

    for word, count in sym_counter.most_common(15):
        if word in seen_terms or count < 3:
            continue
        seen_terms.add(word)
        entries.append(GlossaryEntry(
            term=word,
            definition=f"Domain concept (found in {count} symbols)",
            category=GlossaryCategory.DOMAIN,
            confidence=0.5,
            source="heuristic",
        ))

    # 3. Extract terms from file path segments
    path_segments: Counter = Counter()
    for f in files:
        parts = Path(f.path).parts
        for part in parts:
            # Skip common non-domain parts
            if part in {"src", "lib", "app", "test", "tests", "components",
                        "utils", "services", "api", "types", "models",
                        "hooks", "screens", "views", "pages", "index.ts",
                        "index.tsx", "index.js"}:
                continue
            stem = Path(part).stem
            if stem and len(stem) > 3:
                path_segments[stem.lower()] += 1

    for seg, count in path_segments.most_common(10):
        if seg in seen_terms or count < 2:
            continue
        # Convert to title case
        title = seg.replace("_", " ").replace("-", " ").title()
        seen_terms.add(seg)
        entries.append(GlossaryEntry(
            term=title,
            definition=f"Module/directory concept (in {count} paths)",
            category=GlossaryCategory.DOMAIN,
            confidence=0.4,
            source="heuristic",
        ))

    return Glossary(entries=entries)