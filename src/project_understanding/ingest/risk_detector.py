"""Risk area detector — heuristic detection of sensitive code regions.

Detects risk areas such as:
- Authentication/authorization code
- Database writes and transactions
- External API calls
- File system writes
- Config/secrets handling

Improved: Filters out config/data files to reduce false positives.
"""

from __future__ import annotations

import hashlib
import re

from project_understanding.models.conventions import RiskArea, RiskCategory
from project_understanding.models.entities import File, Symbol


# Patterns that indicate risk areas
_RISK_PATTERNS: dict[RiskCategory, list[re.Pattern[str]]] = {
    RiskCategory.AUTHENTICATION: [
        re.compile(r"(?i)(authenticate|login|logout|sign_in|sign_out|verify_password|check_password|jwt|token)"),
        re.compile(r"(?i)(session|cookie|oauth|auth_)"),
    ],
    RiskCategory.AUTHORIZATION: [
        re.compile(r"(?i)(authorize|permission|role|access_control|is_admin|has_role|check_access)"),
        re.compile(r"(?i)(rbac|acl|guard|policy)"),
    ],
    RiskCategory.DATABASE_WRITE: [
        re.compile(r"(?i)(insert|update|delete|drop|create_table|alter_table|execute_sql)"),
        re.compile(r"(?i)\.(save|create|update|delete|remove|bulk_create|bulk_update)\("),
        re.compile(r"(?i)(cursor|execute|commit|rollback)"),
    ],
    RiskCategory.EXTERNAL_API: [
        re.compile(r"(?i)(requests\.(get|post|put|delete|patch)|httpx|aiohttp|fetch|urllib)"),
        re.compile(r"(?i)(api_url|endpoint|webhook|http_client|rest_client)"),
        re.compile(r"(?i)(send_request|call_api|invoke_api|api_call)"),
    ],
    RiskCategory.FILE_SYSTEM_WRITE: [
        re.compile(r"(?i)(open\(.*['\"]w|write\(|writelines|os\.remove|os\.rename|shutil\.)"),
        re.compile(r"(?i)(pathlib.*write_|mkdir|rmtree|copy2|move)"),
    ],
    RiskCategory.CONFIG_SECRETS: [
        re.compile(r"(?i)(password|secret|api_key|access_key|private_key|token)\s*="),
        re.compile(r"(?i)(getenv|environ|os\.environ|dotenv|\.env)"),
        re.compile(r"(?i)(credential|certificate|ssl_context)"),
    ],
    RiskCategory.CACHE: [
        re.compile(r"(?i)(cache|redis|memcached|lru_cache|functools\.cache)"),
        re.compile(r"(?i)(cache_set|cache_get|cache_delete|invalidate)"),
    ],
}

# Extensions that should be excluded from risk scanning (config, data, markup)
_SKIP_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".svg", ".html", ".css", ".scss", ".less",
    ".md", ".txt", ".rst", ".lock", ".map",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".ttf", ".woff", ".woff2",
    ".env", ".example", ".sample",
}

# Filename patterns that are always config/data (checked lowercase)
_SKIP_FILENAMES = {
    "package.json", "package-lock.json", "tsconfig.json", "jsconfig.json",
    "app.json", "metro.config.js", "babel.config.js", "webpack.config.js",
    "eslint.config.js", ".eslintrc", ".eslintrc.js", ".eslintrc.json",
    ".prettierrc", ".prettierrc.js", ".prettierrc.json", ".prettierignore",
    ".editorconfig", ".gitignore", ".gitattributes",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "makefile", "cmakelists.txt",
    "pyproject.toml", "setup.py", "setup.cfg", "tox.ini",
    "requirements.txt", "constraints.txt",
    ".env", ".env.local", ".env.production", ".env.development",
    "app.config", "web.config", "nuget.config",
    "declarations.d.ts", "global.d.ts",
}


def _should_skip_file(file: File) -> bool:
    """Check if a file should be skipped for risk scanning.

    Skips config files, data files, and non-source files to avoid false positives.
    """
    from pathlib import Path

    name = Path(file.path).name.lower()
    ext = Path(file.path).suffix.lower()

    # Skip known config filenames
    if name in _SKIP_FILENAMES:
        return True

    # Skip known non-source extensions
    if ext in _SKIP_EXTENSIONS:
        return True

    # Skip files with no language detected (not source code)
    if file.language == "unknown" or not file.language:
        return True

    return False


def detect_risks(
    files: list[File],
    symbols: list[Symbol],
    contents: dict[str, str] | None = None,
) -> list[RiskArea]:
    """Run all risk detectors on the codebase.

    Args:
        files: All files in the snapshot.
        symbols: All symbols in the snapshot.
        contents: Optional mapping of file_path -> file_content.

    Returns:
        List of detected risk areas.
    """
    contents = contents or {}
    risks: list[RiskArea] = []

    # Build symbol lookup by file
    symbols_by_file: dict[str, list[Symbol]] = {}
    for sym in symbols:
        if sym.file_id not in symbols_by_file:
            symbols_by_file[sym.file_id] = []
        symbols_by_file[sym.file_id].append(sym)

    for file in files:
        # Skip config/data/non-source files to reduce false positives
        if _should_skip_file(file):
            continue

        content = contents.get(file.path, "")
        if not content:
            continue

        file_symbols = symbols_by_file.get(file.file_id, [])

        for category, patterns in _RISK_PATTERNS.items():
            file_risks = _detect_risks_in_file(file, content, file_symbols, category, patterns)
            risks.extend(file_risks)

    return risks


def _detect_risks_in_file(
    file: File,
    content: str,
    symbols: list[Symbol],
    category: RiskCategory,
    patterns: list[re.Pattern[str]],
) -> list[RiskArea]:
    """Detect risks of a specific category in a single file."""
    risks: list[RiskArea] = []
    matches: list[tuple[int, str, str | None]] = []  # (line, evidence, symbol_name)

    lines = content.split("\n")
    for line_no, line in enumerate(lines, 1):
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                # Find which symbol this line belongs to
                sym_name = _find_symbol_for_line(symbols, line_no)
                matches.append((line_no, line.strip()[:100], sym_name))

    if not matches:
        return risks

    # Deduplicate by symbol
    seen_symbols: set[str | None] = set()
    unique_matches: list[tuple[int, str, str | None]] = []
    for line_no, evidence, sym_name in matches:
        key = sym_name or evidence
        if key not in seen_symbols:
            seen_symbols.add(key)
            unique_matches.append((line_no, evidence, sym_name))

    # Determine severity
    severity = _determine_severity(category, len(unique_matches))

    # Group into risk areas
    if unique_matches:
        first_line = unique_matches[0][0]
        last_line = unique_matches[-1][0]
        sym_name = None
        # Prefer a named symbol
        for _, _, sn in unique_matches:
            if sn:
                sym_name = sn
                break

        # Dynamic confidence based on context
        confidence = _calculate_confidence(file, len(unique_matches), sym_name)

        risks.append(RiskArea(
            risk_id=_make_id(category.value, file.file_id, str(first_line)),
            category=category,
            name=f"{category.value.replace('_', ' ').title()} in {file.path}",
            description=f"Detected {category.value.replace('_', ' ')} operations in {file.path}",
            file_path=file.path,
            symbol_name=sym_name,
            line_range=(first_line, last_line),
            evidence=[ev for _, ev, _ in unique_matches[:5]],
            confidence=confidence,
            severity=severity,
        ))

    return risks


def _calculate_confidence(file: File, match_count: int, sym_name: str | None) -> float:
    """Calculate dynamic confidence score based on context.

    Higher confidence when:
    - Match is inside a named symbol (function/class/method)
    - Multiple matches in the same file
    - File is clearly source code (has language)

    Lower confidence when:
    - No symbol context (top-level code, could be config)
    - Only 1 match (could be comment or string literal)
    """
    base = 0.7

    # Boost: inside a named symbol
    if sym_name:
        base += 0.1

    # Boost: multiple matches confirm the pattern
    if match_count >= 3:
        base += 0.1
    elif match_count >= 5:
        base += 0.15

    # Boost: file has many lines (real source file, not snippet)
    if hasattr(file, 'size') and file.size and file.size > 500:
        base += 0.05

    # Cap at 0.95
    return min(base, 0.95)


def _find_symbol_for_line(
    symbols: list[Symbol], line_no: int
) -> str | None:
    """Find which symbol contains the given line number."""
    for sym in symbols:
        if sym.line_start <= line_no <= sym.line_end:
            return sym.name
    return None


def _determine_severity(category: RiskCategory, match_count: int) -> str:
    """Determine severity based on category and match count."""
    high_categories = {
        RiskCategory.AUTHENTICATION,
        RiskCategory.AUTHORIZATION,
        RiskCategory.CONFIG_SECRETS,
    }
    medium_categories = {
        RiskCategory.DATABASE_WRITE,
        RiskCategory.EXTERNAL_API,
        RiskCategory.FILE_SYSTEM_WRITE,
    }

    if category in high_categories:
        return "high"
    elif category in medium_categories:
        return "medium" if match_count <= 5 else "high"
    else:
        return "low" if match_count <= 3 else "medium"


def _make_id(*parts: str) -> str:
    """Generate deterministic risk ID."""
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]