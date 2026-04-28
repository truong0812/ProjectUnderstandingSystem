"""Bộ chia code — chia file code thành các chunk (hàm/class/module).

Chiến lược:
- Python: Dùng ast module để trích xuất chính xác hàm, class, method.
- Ngôn ngữ khác: Regex-based splitting trên pattern function/class.
- Fallback: Chia nguyên file theo ranh giới ~max_lines dòng.
"""

import ast
import re
from dataclasses import dataclass

from config.settings import CHUNK_MAX_LINES
from parser.repo_parser import CodeFile


@dataclass
class CodeChunk:
    """Một đoạn code đã được chia nhỏ."""

    file_path: str        # Đường dẫn tương đối
    name: str             # Tên (hàm/class/file)
    chunk_type: str       # "function", "class", "method", "module"
    language: str         # Ngôn ngữ lập trình
    start_line: int       # Dòng bắt đầu (1-based)
    end_line: int         # Dòng kết thúc
    content: str          # Nội dung code
    line_count: int       # Số dòng

    @property
    def unique_id(self) -> str:
        """ID duy nhất cho chunk này."""
        return f"{self.file_path}::{self.name}::{self.start_line}"


# ────────────────────────────────────────────────────────────────────
# Python chunking — dùng ast module
# ────────────────────────────────────────────────────────────────────

def _chunk_python(code_file: CodeFile) -> list[CodeChunk]:
    """Chia file Python thành các chunk bằng ast module."""
    chunks: list[CodeChunk] = []
    lines = code_file.content.split("\n")
    source = code_file.content

    try:
        tree = ast.parse(source, filename=code_file.rel_path)
    except SyntaxError:
        # Nếu không parse được, fallback chia nguyên file
        return _chunk_fallback(code_file)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk = _make_chunk(code_file, node, lines, "function")
            if chunk:
                chunks.append(chunk)

        elif isinstance(node, ast.ClassDef):
            # Chunk cho cả class (bao gồm docstring + attributes)
            class_chunk = _make_chunk(code_file, node, lines, "class")
            if class_chunk:
                chunks.append(class_chunk)

            # Chunk cho từng method trong class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_chunk = _make_chunk(
                        code_file, item, lines, "method",
                        parent=node.name,
                    )
                    if method_chunk:
                        chunks.append(method_chunk)

    # Phần code còn lại (module-level, imports, globals)
    covered_lines = set()
    for chunk in chunks:
        for i in range(chunk.start_line, chunk.end_line + 1):
            covered_lines.add(i)

    remaining_lines = []
    remaining_start = None
    for i, line in enumerate(lines, start=1):
        if i not in covered_lines and line.strip():
            if remaining_start is None:
                remaining_start = i
            remaining_lines.append(line)
        elif remaining_lines:
            content = "\n".join(remaining_lines)
            if len(content.strip()) > 20:  # Bỏ qua đoạn quá ngắn
                chunks.append(CodeChunk(
                    file_path=code_file.rel_path,
                    name=f"{code_file.rel_path}::module_level",
                    chunk_type="module",
                    language=code_file.language,
                    start_line=remaining_start,
                    end_line=remaining_start + len(remaining_lines) - 1,
                    content=content,
                    line_count=len(remaining_lines),
                ))
            remaining_lines = []
            remaining_start = None

    # Đoạn cuối cùng
    if remaining_lines and len(remaining_lines) > 3:
        content = "\n".join(remaining_lines)
        chunks.append(CodeChunk(
            file_path=code_file.rel_path,
            name=f"{code_file.rel_path}::module_level",
            chunk_type="module",
            language=code_file.language,
            start_line=remaining_start or 1,
            end_line=(remaining_start or 1) + len(remaining_lines) - 1,
            content=content,
            line_count=len(remaining_lines),
        ))

    if not chunks:
        return _chunk_fallback(code_file)

    return chunks


def _make_chunk(
    code_file: CodeFile,
    node: ast.AST,
    lines: list[str],
    chunk_type: str,
    parent: str | None = None,
) -> CodeChunk | None:
    """Tạo CodeChunk từ một AST node."""
    start = node.lineno
    end = node.end_lineno or start
    content = "\n".join(lines[start - 1:end])

    if not content.strip():
        return None

    name = node.name
    if parent:
        name = f"{parent}.{name}"

    return CodeChunk(
        file_path=code_file.rel_path,
        name=name,
        chunk_type=chunk_type,
        language=code_file.language,
        start_line=start,
        end_line=end,
        content=content,
        line_count=end - start + 1,
    )


# ────────────────────────────────────────────────────────────────────
# Regex-based chunking cho ngôn ngữ khác
# ────────────────────────────────────────────────────────────────────

# Patterns cho các ngôn ngữ khác
FUNCTION_PATTERNS: dict[str, list[tuple[str, str]]] = {
    "javascript": [
        (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(", "function"),
        (r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>", "function"),
        (r"class\s+(\w+)", "class"),
    ],
    "typescript": [
        (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]", "function"),
        (r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=])\s*=>", "function"),
        (r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", "class"),
        (r"(?:export\s+)?interface\s+(\w+)", "interface"),
    ],
    "java": [
        (r"(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{", "function"),
        (r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)", "class"),
        (r"(?:public|private|protected)?\s*interface\s+(\w+)", "interface"),
    ],
    "go": [
        (r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", "function"),
        (r"type\s+(\w+)\s+struct", "class"),
        (r"type\s+(\w+)\s+interface", "interface"),
    ],
    "rust": [
        (r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", "function"),
        (r"(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)", "class"),
    ],
    "c": [
        (r"(?:static\s+)?[\w*]+\s+(\w+)\s*\([^)]*\)\s*\{", "function"),
    ],
    "cpp": [
        (r"(?:[\w:*&<>]+\s+)+(\w+)\s*\([^)]*\)\s*(?:const)?\s*(?:override)?\s*\{", "function"),
        (r"(?:class|struct)\s+(\w+)", "class"),
    ],
    "csharp": [
        (r"(?:public|private|protected|internal|static)\s+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)", "function"),
        (r"(?:public|private|protected|internal)?\s*(?:class|struct|interface)\s+(\w+)", "class"),
    ],
    "ruby": [
        (r"def\s+(\w+)", "function"),
        (r"class\s+(\w+)", "class"),
        (r"module\s+(\w+)", "module"),
    ],
    "php": [
        (r"(?:public|private|protected)?\s*(?:static\s+)?function\s+(\w+)", "function"),
        (r"(?:abstract\s+)?class\s+(\w+)", "class"),
    ],
    "swift": [
        (r"func\s+(\w+)", "function"),
        (r"(?:class|struct|enum|protocol)\s+(\w+)", "class"),
    ],
    "kotlin": [
        (r"fun\s+(?:<[^>]+>\s+)?(\w+)", "function"),
        (r"(?:class|object|interface)\s+(\w+)", "class"),
    ],
}


def _chunk_regex(code_file: CodeFile) -> list[CodeChunk]:
    """Chia file bằng regex cho các ngôn ngữ không phải Python."""
    language = code_file.language
    patterns = FUNCTION_PATTERNS.get(language, [])

    if not patterns:
        return _chunk_fallback(code_file)

    lines = code_file.content.split("\n")
    chunks: list[CodeChunk] = []

    for pattern, chunk_type in patterns:
        for match in re.finditer(pattern, code_file.content):
            name = match.group(1)

            # Tìm dòng bắt đầu
            start_line = code_file.content[:match.start()].count("\n") + 1

            # Ước lượng dòng kết thúc (tìm dấu đóng ngoặc nhon hoặc dùng max_lines)
            end_line = _find_block_end(lines, start_line - 1)

            content = "\n".join(lines[start_line - 1:end_line])
            if not content.strip():
                continue

            chunks.append(CodeChunk(
                file_path=code_file.rel_path,
                name=name,
                chunk_type=chunk_type,
                language=language,
                start_line=start_line,
                end_line=end_line,
                content=content,
                line_count=end_line - start_line + 1,
            ))

    if not chunks:
        return _chunk_fallback(code_file)

    return chunks


def _find_block_end(lines: list[str], start_idx: int) -> int:
    """Tìm dòng kết thúc của một khối code dựa trên brace matching."""
    brace_count = 0
    found_open = False

    for i in range(start_idx, min(start_idx + CHUNK_MAX_LINES, len(lines))):
        line = lines[i]
        for ch in line:
            if ch == "{":
                brace_count += 1
                found_open = True
            elif ch == "}":
                brace_count -= 1
                if found_open and brace_count <= 0:
                    return i + 1  # 1-based
        # Nếu không có brace (Python-like), dùng indentation
        if not found_open and i > start_idx:
            stripped = lines[i].strip()
            if stripped and not lines[i][0].isspace() and i > start_idx + 1:
                return i  # 1-based

    return min(start_idx + CHUNK_MAX_LINES, len(lines))


# ────────────────────────────────────────────────────────────────────
# Fallback — chia nguyên file
# ────────────────────────────────────────────────────────────────────

def _chunk_fallback(code_file: CodeFile) -> list[CodeChunk]:
    """Chia file thành các chunk theo ranh giới max_lines."""
    lines = code_file.content.split("\n")

    if len(lines) <= CHUNK_MAX_LINES:
        return [CodeChunk(
            file_path=code_file.rel_path,
            name=code_file.rel_path,
            chunk_type="module",
            language=code_file.language,
            start_line=1,
            end_line=len(lines),
            content=code_file.content,
            line_count=len(lines),
        )]

    chunks: list[CodeChunk] = []
    idx = 0
    part = 1

    while idx < len(lines):
        end = min(idx + CHUNK_MAX_LINES, len(lines))
        content = "\n".join(lines[idx:end])

        if content.strip():
            chunks.append(CodeChunk(
                file_path=code_file.rel_path,
                name=f"{code_file.rel_path}::part{part}",
                chunk_type="module",
                language=code_file.language,
                start_line=idx + 1,
                end_line=end,
                content=content,
                line_count=end - idx,
            ))
            part += 1

        idx = end

    return chunks


# ────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────

def chunk_file(code_file: CodeFile) -> list[CodeChunk]:
    """Chia một CodeFile thành danh sách CodeChunk.

    Args:
        code_file: File code cần chia.

    Returns:
        Danh sách các CodeChunk.
    """
    if code_file.language == "python":
        return _chunk_python(code_file)
    elif code_file.language in FUNCTION_PATTERNS:
        return _chunk_regex(code_file)
    else:
        return _chunk_fallback(code_file)


def chunk_all(code_files: list[CodeFile]) -> list[CodeChunk]:
    """Chia danh sách CodeFile thành danh sách CodeChunk.

    Args:
        code_files: Danh sách file code đã parse.

    Returns:
        Danh sách tất cả CodeChunk từ tất cả file.
    """
    all_chunks: list[CodeChunk] = []

    for code_file in code_files:
        chunks = chunk_file(code_file)
        all_chunks.extend(chunks)

    return all_chunks