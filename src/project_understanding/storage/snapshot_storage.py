"""Snapshot storage — atomic write/read for knowledge snapshots.

Stores snapshots as JSON files on disk with atomic write semantics
to prevent corruption.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from project_understanding.models.snapshot import SnapshotPackage


class SnapshotStorage:
    """Manages reading and writing of snapshot files to disk."""

    def __init__(self, output_dir: str = "./output") -> None:
        """Initialize storage.

        Args:
            output_dir: Base directory for snapshot output.
        """
        self._output_dir = Path(output_dir)

    def write(self, package: SnapshotPackage) -> str:
        """Write a snapshot package to disk atomically.

        Creates:
          - <output_dir>/<repo_id>/<snapshot_id>.json (full snapshot)
          - <output_dir>/<repo_id>/latest.json (symlink/copy of latest)

        Args:
            package: Snapshot package to write.

        Returns:
            Path to the written snapshot file.
        """
        repo_dir = self._output_dir / package.repository.repo_id
        repo_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = repo_dir / f"{package.snapshot.snapshot_id}.json"

        # Atomic write: write to temp file, then rename
        data = package.model_dump(mode="json")
        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        # Write atomically
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            dir=str(repo_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json_str)
            # On Windows, need to remove target first
            if snapshot_path.exists():
                snapshot_path.unlink()
            os.rename(tmp_path, str(snapshot_path))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Update latest pointer
        latest_path = repo_dir / "latest.json"
        try:
            if latest_path.exists():
                latest_path.unlink()
            # Write a copy (Windows doesn't support symlinks easily)
            latest_path.write_text(json_str, encoding="utf-8")
        except Exception:
            pass  # Non-critical

        return str(snapshot_path)

    def read(self, repo_id: str, snapshot_id: str | None = None) -> SnapshotPackage | None:
        """Read a snapshot package from disk.

        Args:
            repo_id: Repository identifier.
            snapshot_id: Snapshot ID, or None to read latest.

        Returns:
            SnapshotPackage or None if not found.
        """
        repo_dir = self._output_dir / repo_id
        if not repo_dir.is_dir():
            return None

        if snapshot_id:
            path = repo_dir / f"{snapshot_id}.json"
        else:
            path = repo_dir / "latest.json"

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SnapshotPackage.model_validate(data)
        except Exception:
            return None

    def list_snapshots(self, repo_id: str) -> list[str]:
        """List all snapshot IDs for a repository.

        Args:
            repo_id: Repository identifier.

        Returns:
            List of snapshot IDs (sorted by modification time, newest first).
        """
        repo_dir = self._output_dir / repo_id
        if not repo_dir.is_dir():
            return []

        snapshots = []
        for f in repo_dir.iterdir():
            if f.is_file() and f.suffix == ".json" and f.stem != "latest":
                snapshots.append((f.stat().st_mtime, f.stem))

        # Sort by modification time, newest first
        snapshots.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in snapshots]

    def delete(self, repo_id: str, snapshot_id: str) -> bool:
        """Delete a specific snapshot.

        Args:
            repo_id: Repository identifier.
            snapshot_id: Snapshot ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        path = self._output_dir / repo_id / f"{snapshot_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False