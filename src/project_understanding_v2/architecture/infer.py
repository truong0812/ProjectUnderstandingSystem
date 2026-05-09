"""Simple architecture inference based on top‑level directories and common files.

Detects layers, entrypoints, and framework hints. Returns an ``ArchitectureMap``
model instance.
"""

from pathlib import Path
from typing import List

from ..models import ArchitectureMap


def infer_architecture(root_path: str) -> ArchitectureMap:
    root = Path(root_path).resolve()
    layers: List[str] = []
    entrypoints: List[str] = []
    frameworks: List[str] = []
    for child in root.iterdir():
        if child.is_dir():
            layers.append(child.name)
        elif child.is_file() and child.name.startswith("main"):
            entrypoints.append(str(child))
    if (root / "pyproject.toml").exists():
        frameworks.append("python")
    if (root / "package.json").exists():
        frameworks.append("node")
    return ArchitectureMap(
        detected_layers=layers,
        entrypoints=entrypoints,
        frameworks=frameworks,
        confidence=0.8,
    )
