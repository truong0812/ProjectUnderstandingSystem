"""Simple JSON storage for layered snapshots.

Writes snapshots to ``output/<project>/snapshots/<timestamp>/layered_snapshot.json``
and creates a ``latest.json`` symlink for easy access.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _timestamp_dir(base: Path) -> Path:
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    return base / ts


def write_snapshot(project_name: str, snapshot: Dict[str, Any], output_dir: str = "output") -> Path:
    base = Path(output_dir) / project_name / "snapshots"
    target = _timestamp_dir(base)
    os.makedirs(target, exist_ok=True)
    (target / "layered_snapshot.json").write_text(
        json.dumps(snapshot, default=str, indent=2), encoding="utf-8"
    )
    latest = base / "latest.json"
    if latest.exists():
        latest.unlink()
    latest.symlink_to(target / "layered_snapshot.json")
    return target


def load_snapshot(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
