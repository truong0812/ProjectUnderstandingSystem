"""Parser kho code — duyệt thư mục repo và nhận diện file code.

Trả về danh sách CodeFile, không tải toàn bộ nội dung vào bộ nhớ cùng lúc.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from config.settings import SUPPORTED_EXTENSIONS, SKIP_DIRS


@dataclass
class CodeFile:
    """Đại diện cho một file code trong repo."""

    filepath: str          # Đường dẫn tuyệt đối
    rel_path: str          # Đường dẫn tương đối so với repo root
    content: str           # Nội dung file
    language: str          # Ngôn ngữ lập trình (python, javascript, ...)
    line_count: int        # Số dòng
    size_bytes: int        # Kích thước file (bytes)


def parse_repo(repo_path: str, max_file_size: int = 1_000_000) -> list[CodeFile]:
    """Parse một thư mục repo và trả về danh sách CodeFile.

    Args:
        repo_path: Đường dẫn tuyệt đối đến thư mục repo.
        max_file_size: Bỏ qua file lớn hơn ngưỡng này (bytes). Mặc định 1MB.

    Returns:
        Danh sách CodeFile đã được parse.

    Raises:
        FileNotFoundError: Nếu repo_path không tồn tại.
        ValueError: Nếu repo_path không phải thư mục.
    """
    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {repo_path}")
    if not os.path.isdir(repo_path):
        raise ValueError(f"Không phải thư mục: {repo_path}")

    code_files: list[CodeFile] = []

    for root, dirs, files in os.walk(repo_path):
        # Bỏ qua các thư mục không cần thiết (chỉnh dirs in-place)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in sorted(files):
            filepath = os.path.join(root, filename)

            # Kiểm tra extension
            _, ext = os.path.splitext(filename)
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            # Kiểm tra kích thước file
            try:
                file_size = os.path.getsize(filepath)
            except OSError:
                continue

            if file_size > max_file_size:
                continue
            if file_size == 0:
                continue

            # Đọc nội dung file
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue

            if not content.strip():
                continue

            rel_path = os.path.relpath(filepath, repo_path)
            language = SUPPORTED_EXTENSIONS[ext]
            line_count = content.count("\n") + 1

            code_files.append(CodeFile(
                filepath=filepath,
                rel_path=rel_path,
                content=content,
                language=language,
                line_count=line_count,
                size_bytes=file_size,
            ))

    return code_files


def get_repo_stats(code_files: list[CodeFile]) -> dict:
    """Thống kê cơ bản về các file đã parse.

    Returns:
        Dict chứa: total_files, total_lines, total_bytes, languages (dict).
    """
    languages: dict[str, int] = {}
    total_lines = 0
    total_bytes = 0

    for cf in code_files:
        languages[cf.language] = languages.get(cf.language, 0) + 1
        total_lines += cf.line_count
        total_bytes += cf.size_bytes

    return {
        "total_files": len(code_files),
        "total_lines": total_lines,
        "total_bytes": total_bytes,
        "languages": languages,
    }