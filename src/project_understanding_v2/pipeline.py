"""V2 layered ingest pipeline."""

from __future__ import annotations

import subprocess
from pathlib import Path

from project_understanding_v2.graph import (
    attach_ownership,
    build_modules,
    build_relations,
    build_summaries,
    infer_architecture,
    relation_counts,
)
from project_understanding_v2.models import LayeredSnapshot, QualityReport, RepositoryInfo, stable_id
from project_understanding_v2.parse import parse_repository
from project_understanding_v2.scan import scan_repository
from project_understanding_v2.storage import LayeredSnapshotStorage


def ingest_repository(
    repo_path: str,
    output_dir: str | None = None,
    use_llm: bool = False,
    project_name: str | None = None,
) -> LayeredSnapshot:
    """Ingest a repository into a layered V2 snapshot.

    `use_llm` is reserved for the next implementation phase. The current
    slice is deterministic and heuristic-only.
    """
    root = Path(repo_path).resolve()
    scan = scan_repository(root)
    parsed = parse_repository(scan.root_path, scan.files)
    modules = build_modules(scan.files, parsed.classes, parsed.functions)
    attach_ownership(modules, parsed.classes, parsed.functions)
    relations = build_relations(scan.files, modules, parsed.classes, parsed.functions, parsed.imports)
    architecture = infer_architecture(scan.files, modules)
    summaries = build_summaries(architecture, modules, parsed.classes, parsed.functions)
    counts = relation_counts(relations)
    quality = QualityReport(
        files_scanned=len(scan.files),
        files_parsed=len({fn.file_path for fn in parsed.functions} | {klass.file_path for klass in parsed.classes}),
        files_skipped=len(scan.skipped),
        unknown_language_count=sum(1 for file_node in scan.files if file_node.language == "unknown"),
        parser_error_count=len(parsed.errors),
        class_count=len(parsed.classes),
        function_count=len(parsed.functions),
        module_count=len(modules),
        relation_count_by_type=counts,
        architecture_confidence=architecture.confidence,
        summary_coverage_by_level=relation_counts_by_level(summaries),
        warnings=parsed.errors + ([] if not use_llm else ["LLM summarization is not implemented in this V2 slice."]),
    )
    snapshot = LayeredSnapshot(
        repository=RepositoryInfo(
            repo_id=stable_id("repo", str(root)),
            root_path=str(root),
            branch=_git("rev-parse", "--abbrev-ref", "HEAD", cwd=root) or "unknown",
            commit_sha=(_git("rev-parse", "HEAD", cwd=root) or "")[:12],
        ),
        architecture=architecture,
        files=scan.files,
        modules=modules,
        classes=parsed.classes,
        functions=parsed.functions,
        relations=relations,
        summaries=summaries,
        quality=quality,
    )
    if output_dir:
        LayeredSnapshotStorage(output_dir).write(snapshot, project_name=project_name)
    return snapshot


def relation_counts_by_level(summaries) -> dict[str, int]:
    counts: dict[str, int] = {}
    for summary in summaries:
        counts[summary.level] = counts.get(summary.level, 0) + 1
    return counts


def _git(*args: str, cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()
