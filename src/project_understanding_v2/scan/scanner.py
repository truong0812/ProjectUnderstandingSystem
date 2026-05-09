"""File scanner and classifier for Project Understanding V2.

Classifies files based on their extension into categories used by the ingest
pipeline. The categories follow the plan (source, test, config, docs, asset,
generated, dependency, unknown).
"""

import os
from pathlib import Path
from typing import Dict, List

# Simple mapping from file extension to category
EXTENSION_MAP: Dict[str, str] = {
    ".py": "source",
    ".ts": "source",
    ".js": "source",
    ".json": "config",
    ".yml": "config",
    ".yaml": "config",
    ".md": "docs",
    ".rst": "docs",
    ".png": "asset",
    ".jpg": "asset",
    ".jpeg": "asset",
    ".gif": "asset",
}


def classify_file(path: Path) -> str:
    """Return the category for a single file based on its suffix."""
    return EXTENSION_MAP.get(path.suffix.lower(), "unknown")


def classify_files(root: Path) -> Dict[str, List[Path]]:
    """Recursively walk *root* and group files by category.

    Returns a dict mapping category name to a list of :class:`Path` objects.
    """
    categories: Dict[str, List[Path]] = {}
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            fpath = Path(dirpath) / fname
            cat = classify_file(fpath)
            categories.setdefault(cat, []).append(fpath)
    return categories


def scan_repository(repo_path: str) -> Dict[str, List[str]]:
    """Public API used by the CLI.

    Returns a JSON‑serialisable mapping of category -> list of string paths.
    """
    root = Path(repo_path).resolve()
    raw = classify_files(root)
    return {cat: [str(p) for p in paths] for cat, paths in raw.items()}
