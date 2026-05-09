"""File-based storage for V2 layered snapshots."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from project_understanding_v2.models import LayeredSnapshot


class LayeredSnapshotStorage:
    """Read and write layered snapshots as JSON."""

    def __init__(self, output_dir: str | Path = "./output") -> None:
        self.output_dir = Path(output_dir)

    def write(self, snapshot: LayeredSnapshot, project_name: str | None = None) -> Path:
        name = project_name or Path(snapshot.repository.root_path).name
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        project_dir = self.output_dir / name
        snapshot_dir = project_dir / "snapshots" / timestamp
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = snapshot_dir / "layered_snapshot.json"
        quality_path = snapshot_dir / "quality_report.json"
        architecture_path = snapshot_dir / "architecture.json"
        latest_path = project_dir / "latest.json"

        snapshot_json = snapshot.model_dump_json(indent=2)
        snapshot_path.write_text(snapshot_json, encoding="utf-8")
        latest_path.write_text(snapshot_json, encoding="utf-8")
        quality_path.write_text(snapshot.quality.model_dump_json(indent=2), encoding="utf-8")
        architecture_path.write_text(snapshot.architecture.model_dump_json(indent=2), encoding="utf-8")
        return snapshot_path

    def read(self, path: str | Path) -> LayeredSnapshot:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return LayeredSnapshot.model_validate(data)
