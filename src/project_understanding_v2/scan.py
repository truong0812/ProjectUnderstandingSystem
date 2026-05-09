"""Repository scanning and file classification for V2."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from project_understanding_v2.models import FileCategory, FileNode, stable_id


SKIP_PATTERNS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
    "*.pyc",
    "*.min.js",
}


@dataclass
class ScanOutput:
    root_path: Path
    files: list[FileNode]
    skipped: list[str]


def scan_repository(repo_path: str | Path, max_file_size: int = 1024 * 1024) -> ScanOutput:
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    files: list[FileNode] = []
    skipped: list[str] = []

    for current_root, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if not _matches_skip(d)]
        for filename in filenames:
            if _matches_skip(filename):
                skipped.append(str(Path(current_root) / filename))
                continue

            absolute = Path(current_root) / filename
            rel_path = absolute.relative_to(root).as_posix()
            try:
                size = absolute.stat().st_size
            except OSError:
                skipped.append(rel_path)
                continue
            if size > max_file_size or _is_binary(absolute):
                skipped.append(rel_path)
                continue

            language = detect_language(rel_path)
            file_hash = _hash_file(absolute)
            files.append(
                FileNode(
                    file_id=stable_id("file", rel_path, file_hash),
                    path=rel_path,
                    language=language,
                    category=classify_file(rel_path, language),
                    size=size,
                    hash=file_hash,
                )
            )

    return ScanOutput(root_path=root, files=files, skipped=skipped)


def detect_language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
    }.get(suffix, "unknown")


def classify_file(path: str, language: str) -> FileCategory:
    lower = path.lower()
    name = Path(lower).name
    if "/test" in lower or lower.startswith("test") or name.startswith("test_") or ".test." in name:
        return FileCategory.TEST
    if language in {"python", "typescript", "javascript"}:
        return FileCategory.SOURCE
    if language == "markdown":
        return FileCategory.DOCS
    if language in {"json", "yaml", "toml"} or name in {".env", ".gitignore"}:
        return FileCategory.CONFIG
    if Path(lower).suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico"}:
        return FileCategory.ASSET
    return FileCategory.UNKNOWN


def _matches_skip(name: str) -> bool:
    return any(fnmatch(name, pattern) or name == pattern for pattern in SKIP_PATTERNS)


def _is_binary(path: Path) -> bool:
    try:
        return b"\x00" in path.read_bytes()[:8192]
    except OSError:
        return True


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()
