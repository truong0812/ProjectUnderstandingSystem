"""Snapshot storage — atomic write/read for knowledge snapshots.

Stores snapshots with human-readable naming:
    output/
    ├── <project-name>/
    │   ├── snapshots/
    │   │   └── 2026-05-06/
    │   │       └── snapshot.json
    │   ├── indexes/
    │   │   └── semantic_index.json
    │   ├── latest.json           ← copy of newest snapshot
    │   └── metadata.json         ← last commit, branch, stats
    └── USE_GUIDE.md              ← auto-generated usage guide

Output directory is configurable via:
    1. CLI --output-dir flag
    2. .env SNAPSHOT_OUTPUT_DIR variable
    3. Default: ./output

Backward compatible with old hash-based format:
    output/<repo_id>/<snapshot_id>.json
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
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

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        package: SnapshotPackage,
        project_name: str | None = None,
    ) -> str:
        """Write a snapshot package to disk atomically.

        Creates:
          - <output_dir>/<project-name>/snapshots/<date>/snapshot.json
          - <output_dir>/<project-name>/latest.json (copy of latest)
          - <output_dir>/<project-name>/metadata.json
          - <output_dir>/<project-name>/USE_GUIDE.md  (if not exists)

        Args:
            package: Snapshot package to write.
            project_name: Human-readable project name. Falls back to repo_id.

        Returns:
            Path to the written snapshot file.
        """
        name = project_name or package.repository.repo_id
        project_dir = self._output_dir / name

        # Date-based snapshot directory
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        snapshot_dir = project_dir / "snapshots" / date_str
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = snapshot_dir / "snapshot.json"

        # Serialize
        data = package.model_dump(mode="json")
        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        # Atomic write
        self._atomic_write(snapshot_path, json_str)

        # Update latest pointer
        latest_path = project_dir / "latest.json"
        try:
            self._atomic_write(latest_path, json_str)
        except Exception:
            pass  # Non-critical

        # Write metadata
        self._write_metadata(project_dir, package, name, date_str)

        # Generate USE_GUIDE.md (only if not exists at project level)
        use_guide_path = project_dir / "USE_GUIDE.md"
        try:
            self._write_use_guide(use_guide_path, package, name)
        except Exception:
            pass  # Non-critical

        return str(snapshot_path)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(
        self,
        repo_id: str,
        snapshot_id: str | None = None,
    ) -> SnapshotPackage | None:
        """Read a snapshot package from disk.

        Tries new naming first, then falls back to old hash-based format.

        Args:
            repo_id: Repository identifier OR project name.
            snapshot_id: Snapshot ID, or None to read latest.

        Returns:
            SnapshotPackage or None if not found.
        """
        # Try 1: New naming — <project-name>/latest.json or snapshots/<date>/snapshot.json
        pkg = self._read_new_format(repo_id, snapshot_id)
        if pkg:
            return pkg

        # Try 2: Old hash-based — <repo_id>/<snapshot_id>.json
        pkg = self._read_legacy_format(repo_id, snapshot_id)
        if pkg:
            return pkg

        return None

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_snapshots(self, repo_id: str) -> list[str]:
        """List all snapshot IDs for a repository.

        Args:
            repo_id: Repository identifier or project name.

        Returns:
            List of snapshot IDs (sorted by modification time, newest first).
        """
        # Try new format first
        project_dir = self._output_dir / repo_id
        if project_dir.is_dir():
            snapshots = []

            # Check snapshots/YYYY-MM-DD/ directories
            snap_base = project_dir / "snapshots"
            if snap_base.is_dir():
                for date_dir in snap_base.iterdir():
                    snap_file = date_dir / "snapshot.json"
                    if snap_file.exists():
                        snapshots.append((snap_file.stat().st_mtime, date_dir.name))

            # Also check for legacy .json files at root level
            for f in project_dir.iterdir():
                if f.is_file() and f.suffix == ".json" and f.stem != "latest" and f.stem != "metadata":
                    snapshots.append((f.stat().st_mtime, f.stem))

            snapshots.sort(key=lambda x: x[0], reverse=True)
            return [s[1] for s in snapshots]

        # Try legacy format
        legacy_dir = self._output_dir / repo_id
        if not legacy_dir.is_dir():
            return []

        snapshots = []
        for f in legacy_dir.iterdir():
            if f.is_file() and f.suffix == ".json" and f.stem != "latest":
                snapshots.append((f.stat().st_mtime, f.stem))

        snapshots.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in snapshots]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, repo_id: str, snapshot_id: str) -> bool:
        """Delete a specific snapshot.

        Args:
            repo_id: Repository identifier or project name.
            snapshot_id: Snapshot ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        # Try new format: snapshots/YYYY-MM-DD/snapshot.json
        snap_path = self._output_dir / repo_id / "snapshots" / snapshot_id / "snapshot.json"
        if snap_path.exists():
            snap_path.unlink()
            return True

        # Try legacy format
        legacy_path = self._output_dir / repo_id / f"{snapshot_id}.json"
        if legacy_path.exists():
            legacy_path.unlink()
            return True

        return False

    # ------------------------------------------------------------------
    # Resolve project name from repo_id (legacy compat)
    # ------------------------------------------------------------------

    def resolve_project_name(self, repo_id: str) -> str | None:
        """Try to find the project name for a legacy repo_id.

        Scans metadata.json files to find which project maps to a repo_id.

        Returns:
            Project name or None.
        """
        if not self._output_dir.is_dir():
            return None

        for project_dir in self._output_dir.iterdir():
            if not project_dir.is_dir():
                continue
            meta_path = project_dir / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if meta.get("repo_id") == repo_id:
                        return project_dir.name
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to file atomically."""
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json",
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            # On Windows, need to remove target first
            if path.exists():
                path.unlink()
            os.rename(tmp_path, str(path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _read_new_format(
        self, repo_id: str, snapshot_id: str | None = None
    ) -> SnapshotPackage | None:
        """Read snapshot using new naming convention."""
        project_dir = self._output_dir / repo_id
        if not project_dir.is_dir():
            return None

        if snapshot_id:
            # Could be a date like "2026-05-06" or a legacy hash
            path = project_dir / "snapshots" / snapshot_id / "snapshot.json"
            if not path.exists():
                return None
        else:
            path = project_dir / "latest.json"
            if not path.exists():
                return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SnapshotPackage.model_validate(data)
        except Exception:
            return None

    def _read_legacy_format(
        self, repo_id: str, snapshot_id: str | None = None
    ) -> SnapshotPackage | None:
        """Read snapshot using old hash-based naming."""
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

    def _write_metadata(
        self, project_dir: Path, package: SnapshotPackage, name: str, date_str: str
    ) -> None:
        """Write metadata.json with project stats."""
        snap = package.snapshot
        metadata = {
            "project_name": name,
            "repo_id": package.repository.repo_id,
            "last_snapshot": date_str,
            "branch": snap.branch,
            "commit_sha": snap.commit_sha,
            "stats": {
                "files": snap.file_count,
                "symbols": snap.symbol_count,
                "relations": snap.relation_count,
                "summaries": snap.summary_count,
            },
        }
        meta_path = project_dir / "metadata.json"
        self._atomic_write(meta_path, json.dumps(metadata, indent=2, ensure_ascii=False))

    def _write_use_guide(
        self, path: Path, package: SnapshotPackage, name: str
    ) -> None:
        """Generate USE_GUIDE.md for the knowledge base."""
        if path.exists():
            return  # Don't overwrite user-customized guide

        snap = package.snapshot
        repo = package.repository

        # Collect file extensions
        ext_counts: dict[str, int] = {}
        for f in package.files:
            ext = f.path.rsplit(".", 1)[-1] if "." in f.path else "other"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        top_exts = sorted(ext_counts.items(), key=lambda x: -x[1])[:5]

        # Collect symbol kinds
        kind_counts: dict[str, int] = {}
        for s in package.symbols:
            kind_counts[s.kind.value] = kind_counts.get(s.kind.value, 0) + 1
        top_kinds = sorted(kind_counts.items(), key=lambda x: -x[1])[:5]

        guide = f"""# Knowledge Base: {name}

> Auto-generated by **Project Understanding System** on {snap.created_at[:10]}

## Structure

```
{name}/
├── snapshots/           # Historical snapshots by date
│   └── YYYY-MM-DD/
│       └── snapshot.json
├── indexes/             # Semantic search indexes
│   └── semantic_index.json
├── latest.json          # Current snapshot (copy of newest)
├── metadata.json        # Project metadata & stats
└── USE_GUIDE.md         # This file
```

## Statistics

| Metric | Count |
|--------|-------|
| Files | {snap.file_count} |
| Symbols | {snap.symbol_count} |
| Relations | {snap.relation_count} |
| Summaries | {snap.summary_count} |

**Last commit:** `{snap.commit_sha}` on branch `{snap.branch}`

**Top file types:** {", ".join(f"`.{ext}` ({n})" for ext, n in top_exts)}

**Top symbol kinds:** {", ".join(f"`{k}` ({n})" for k, n in top_kinds)}

## How to Update

```bash
# Basic ingestion (heuristic summaries)
python -m project_understanding.cli.main ingest /path/to/{name} --project-name {name}

# With LLM summaries (recommended)
python -m project_understanding.cli.main ingest /path/to/{name} --project-name {name}

# Skip enrichment for faster results
python -m project_understanding.cli.main ingest /path/to/{name} --project-name {name} --no-enrichment
```

## Query Examples

```bash
# Get context for a specific file
python -m project_understanding.cli.main query file "src/api/auth.ts" --repo {name} --profile review-agent

# Search for a symbol
python -m project_understanding.cli.main query symbol "LoginRequest" --repo {name} --profile dev-agent

# Semantic search
python -m project_understanding.cli.main query semantic "authentication flow" --repo {name} --profile review-agent

# Change impact analysis
python -m project_understanding.cli.main query changes "src/api/auth.ts" "src/utils/token.ts" --repo {name} --profile review-agent
```

## Agent Profiles

| Profile | Use Case |
|---------|----------|
| `review-agent` | Code review, PR analysis |
| `dev-agent` | Development assistance, debugging |
| `doc-agent` | Documentation generation |

## Output Format

Each query returns a **ContextBundle** containing:
- **Items**: Files, symbols, modules relevant to the query
- **Relations**: Dependencies and call graphs
- **Summaries**: LLM-generated or heuristic descriptions
- **Conventions**: Detected coding patterns
- **Risks**: Identified risk areas

---

*This file was auto-generated. Edit freely — it won't be overwritten on re-ingest.*
"""
        path.write_text(guide, encoding="utf-8")