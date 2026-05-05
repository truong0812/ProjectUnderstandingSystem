"""Repository scanner — walks a repo tree and collects file metadata.

Respects skip rules to avoid scanning irrelevant directories and files.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

from project_understanding.config import DEFAULT_SKIP_PATTERNS


@dataclass
class ScannedFile:
    """Metadata for a single file found during scanning."""

    path: str  # Relative path from repo root
    absolute_path: str  # Absolute path on disk
    size: int = 0
    hash: str = ""
    extension: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of file content."""
        sha256 = hashlib.sha256()
        try:
            with open(self.absolute_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        except (OSError, PermissionError):
            pass
        self.hash = sha256.hexdigest()
        return self.hash


@dataclass
class ScanResult:
    """Result of scanning a repository."""

    root_path: str
    files: list[ScannedFile] = field(default_factory=list)
    skipped_dirs: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


def _should_skip_dir(dirname: str, skip_patterns: list[str]) -> bool:
    """Check if a directory should be skipped."""
    for pattern in skip_patterns:
        if fnmatch(dirname, pattern) or dirname == pattern:
            return True
    return False


def _should_skip_file(filename: str, skip_patterns: list[str]) -> bool:
    """Check if a file should be skipped."""
    for pattern in skip_patterns:
        if fnmatch(filename, pattern) or filename == pattern:
            return True
    return False


def scan_repository(
    repo_path: str | Path,
    skip_patterns: list[str] | None = None,
    max_file_size: int = 1024 * 1024,  # 1MB default limit
) -> ScanResult:
    """Scan a repository directory tree and collect file metadata.

    Args:
        repo_path: Path to the repository root.
        skip_patterns: Glob patterns for dirs/files to skip. Uses defaults if None.
        max_file_size: Maximum file size in bytes. Larger files are skipped.

    Returns:
        ScanResult with all discovered files and metadata.
    """
    repo_path = Path(repo_path).resolve()
    if not repo_path.is_dir():
        raise ValueError(f"Not a directory: {repo_path}")

    patterns = skip_patterns or DEFAULT_SKIP_PATTERNS
    result = ScanResult(root_path=str(repo_path))

    for root, dirs, files in os.walk(str(repo_path)):
        # Filter directories in-place to prevent os.walk from descending
        filtered_dirs = []
        for d in dirs:
            if _should_skip_dir(d, patterns):
                result.skipped_dirs.append(os.path.join(root, d))
            else:
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs

        for filename in files:
            if _should_skip_file(filename, patterns):
                result.skipped_files.append(os.path.join(root, filename))
                continue

            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, str(repo_path))

            # Normalize path separators to forward slashes
            rel_path = rel_path.replace("\\", "/")

            try:
                file_size = os.path.getsize(abs_path)
            except OSError:
                file_size = 0

            # Skip files that are too large
            if file_size > max_file_size:
                result.skipped_files.append(abs_path)
                continue

            # Skip binary files (rough heuristic: check for null bytes in first 8KB)
            try:
                with open(abs_path, "rb") as f:
                    chunk = f.read(8192)
                if b"\x00" in chunk:
                    result.skipped_files.append(abs_path)
                    continue
            except (OSError, PermissionError):
                result.skipped_files.append(abs_path)
                continue

            ext = Path(filename).suffix.lower()

            scanned = ScannedFile(
                path=rel_path,
                absolute_path=abs_path,
                size=file_size,
                extension=ext,
            )
            scanned.compute_hash()
            result.files.append(scanned)

    return result