"""CLI entry point for Project Understanding System.

Usage:
    pus ingest <repo_path> [--no-llm] [--no-enrichment] [--output-dir DIR]
    pus list <repo_id>
    pus show <repo_id> [--snapshot-id ID]
    pus query file <path> --repo <repo_id> [--profile <name>] [--json]
    pus query symbol <name> --repo <repo_id> [--profile <name>] [--json]
    pus query module <name> --repo <repo_id> [--profile <name>] [--json]
    pus query changes <file1> <file2> ... --repo <repo_id> [--profile <name>] [--json]
    pus query semantic "<query>" --repo <repo_id> [--profile <name>] [--json] [--top-k N]
    pus profiles [--repo <repo_id>]
    pus version
"""

from __future__ import annotations

import argparse
import sys
import time

from project_understanding.config import get_settings


def _progress_callback(stage: str, current: int, total: int) -> None:
    """Print progress to stderr."""
    if stage == "complete":
        print(f"\r[OK] Ingestion complete!", file=sys.stderr)
        return

    pct = int((current / max(total, 1)) * 100)
    bar_len = 30
    filled = int(bar_len * current / max(total, 1))
    bar = "#" * filled + "-" * (bar_len - filled)

    stage_labels = {
        "scanning": "Scanning",
        "parsing": "Parsing",
        "building_relations": "Building relations",
        "summarizing": "Summarizing",
        "enriching_symbols": "Enriching symbols",
        "enriching_modules": "Enriching modules",
        "detecting_conventions": "Detecting conventions",
        "detecting_risks": "Detecting risks",
        "building_index": "Building semantic index",
        "generating_glossary": "Generating domain glossary",
    }
    label = stage_labels.get(stage, stage)

    print(f"\r  {label}: [{bar}] {pct}% ({current}/{total})", end="", file=sys.stderr)


def cmd_ingest(args: argparse.Namespace) -> int:
    """Execute the ingest command."""
    from project_understanding.ingest.pipeline import ingest_repository

    repo_path = args.repo_path
    use_llm = not args.no_llm
    output_dir = args.output_dir
    project_name = getattr(args, 'project_name', None)
    no_enrichment = getattr(args, 'no_enrichment', False)

    print(f"[...] Ingesting repository: {repo_path}", file=sys.stderr)
    if project_name:
        print(f"  Project name: {project_name}", file=sys.stderr)
    if not use_llm:
        print("  (LLM summarization disabled, using heuristics)", file=sys.stderr)
    if no_enrichment:
        print("  (Symbol/module enrichment skipped)", file=sys.stderr)

    start_time = time.time()

    try:
        package = ingest_repository(
            repo_path=repo_path,
            use_llm=use_llm,
            output_dir=output_dir,
            no_enrichment=no_enrichment,
            project_name=project_name,
            progress_callback=_progress_callback,
        )
    except Exception as e:
        print(f"\n[ERROR] {e}", file=sys.stderr)
        return 1

    elapsed = time.time() - start_time

    # Print summary
    snap = package.snapshot
    print(f"\nSnapshot: {snap.snapshot_id}", file=sys.stderr)
    print(f"  Repository: {package.repository.repo_id}", file=sys.stderr)
    print(f"  Branch: {snap.branch} @ {snap.commit_sha}", file=sys.stderr)
    print(f"  Files:     {snap.file_count}", file=sys.stderr)
    print(f"  Symbols:   {snap.symbol_count}", file=sys.stderr)
    print(f"  Relations: {snap.relation_count}", file=sys.stderr)
    print(f"  Summaries: {snap.summary_count}", file=sys.stderr)
    print(f"  Time:      {elapsed:.1f}s", file=sys.stderr)

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List snapshots for a repository."""
    from project_understanding.storage.snapshot_storage import SnapshotStorage

    settings = get_settings()
    storage = SnapshotStorage(output_dir=settings.snapshot_output_dir)

    snapshots = storage.list_snapshots(args.repo_id)
    if not snapshots:
        print(f"No snapshots found for repository: {args.repo_id}", file=sys.stderr)
        return 0

    print(f"Snapshots for {args.repo_id}:")
    for snap_id in snapshots:
        pkg = storage.read(args.repo_id, snap_id)
        if pkg:
            s = pkg.snapshot
            status_icon = "[OK]" if s.status == "complete" else "[!]"
            print(f"  {status_icon} {snap_id} - {s.file_count} files, {s.symbol_count} symbols @ {s.created_at[:19]}")

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Show details of a snapshot."""
    from project_understanding.storage.snapshot_storage import SnapshotStorage

    settings = get_settings()
    storage = SnapshotStorage(output_dir=settings.snapshot_output_dir)

    package = storage.read(args.repo_id, args.snapshot_id)
    if not package:
        print("Snapshot not found.", file=sys.stderr)
        return 1

    snap = package.snapshot
    repo = package.repository

    print(f"Snapshot: {snap.snapshot_id}")
    print(f"Repository: {repo.repo_id}")
    print(f"Branch: {snap.branch}")
    print(f"Commit: {snap.commit_sha}")
    print(f"Created: {snap.created_at}")
    print(f"Status: {snap.status.value}")
    print()
    print(f"Files:     {snap.file_count}")
    print(f"Symbols:   {snap.symbol_count}")
    print(f"Relations: {snap.relation_count}")
    print(f"Summaries: {snap.summary_count}")
    print()

    # Show modules
    if package.modules:
        print("Modules:")
        for mod in package.modules:
            print(f"  [DIR] {mod.name} ({len(mod.files)} files)")

    # Show entry points
    entrypoints = [f for f in package.files if f.is_entrypoint]
    if entrypoints:
        print("\nEntry points:")
        for f in entrypoints:
            print(f"  >> {f.path} ({f.language})")

    # Show symbols summary by kind
    if package.symbols:
        kind_counts: dict[str, int] = {}
        for sym in package.symbols:
            kind_counts[sym.kind.value] = kind_counts.get(sym.kind.value, 0) + 1
        print("\nSymbol breakdown:")
        for kind, count in sorted(kind_counts.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {count}")

    return 0


def _load_engine_and_profile(args):
    """Helper to load engine and profile for query commands."""
    from project_understanding.storage.snapshot_storage import SnapshotStorage
    from project_understanding.profiles.registry import ProfileRegistry
    from project_understanding.retrieval.engine import RetrievalEngine
    from project_understanding.config import get_settings

    settings = get_settings()
    storage = SnapshotStorage(output_dir=settings.snapshot_output_dir)
    package = storage.read(args.repo, args.snapshot_id)
    if not package:
        print("Snapshot not found.", file=sys.stderr)
        return None, None

    registry = ProfileRegistry()
    profile_name = getattr(args, "profile", "review-agent")
    profile = registry.get(profile_name)
    if not profile:
        print(f"Profile '{profile_name}' not found.", file=sys.stderr)
        return None, None

    engine = RetrievalEngine(package)
    return engine, profile


def cmd_query(args: argparse.Namespace) -> int:
    """Execute query subcommands."""
    engine, profile = _load_engine_and_profile(args)
    if not engine or not profile:
        return 1

    as_json = getattr(args, "json", False)
    bundle = None

    if args.query_type == "file":
        bundle = engine.file_context(args.target, profile)
    elif args.query_type == "symbol":
        bundle = engine.symbol_context(args.target, profile)
    elif args.query_type == "module":
        bundle = engine.module_context(args.target, profile)
    elif args.query_type == "changes":
        if not args.files:
            print("Error: --files is required for changes query", file=sys.stderr)
            return 1
        bundle = engine.change_context(args.files, profile)
    elif args.query_type == "semantic":
        query_text = args.target
        if not query_text:
            print("Error: search query text is required for semantic query", file=sys.stderr)
            return 1
        top_k = getattr(args, "top_k", 10)
        bundle = engine.semantic_context(query_text, profile, top_k=top_k)
    else:
        print(f"Unknown query type: {args.query_type}", file=sys.stderr)
        return 1

    if as_json:
        print(bundle.model_dump_json(indent=2))
    else:
        print(bundle.to_agent_context())
        print(f"\n--- Bundle: {bundle.bundle_id} | Items: {len(bundle.items)} | Relations: {bundle.total_relations} ---", file=sys.stderr)

    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    """List available agent profiles."""
    from project_understanding.profiles.registry import ProfileRegistry

    registry = ProfileRegistry()
    profiles = registry.list_profiles()

    print("Available profiles:")
    for name in profiles:
        p = registry.get(name)
        if p:
            print(f"  {name}")
            print(f"    Entities: {', '.join(p.preferred_entities)}")
            print(f"    Relations: {', '.join(p.preferred_relations)}")
            print(f"    Ranking: {p.ranking_mode.value}")
            print(f"    Max items: {p.max_items}")
            print()

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Print version information."""
    print("Project Understanding System v0.1.0")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pus",
        description="Project Understanding System — codebase knowledge extraction",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a repository")
    ingest_parser.add_argument("repo_path", help="Path to the repository to ingest")
    ingest_parser.add_argument("--no-llm", action="store_true", help="Disable LLM summarization")
    ingest_parser.add_argument("--no-enrichment", action="store_true", help="Skip symbol/module LLM enrichment")
    ingest_parser.add_argument("--output-dir", default=None, help="Output directory")
    ingest_parser.add_argument("--project-name", default=None, help="Human-readable project name (auto-detected from git remote if not set)")

    # list
    list_parser = subparsers.add_parser("list", help="List snapshots for a repository")
    list_parser.add_argument("repo_id", help="Repository ID")

    # show
    show_parser = subparsers.add_parser("show", help="Show snapshot details")
    show_parser.add_argument("repo_id", help="Repository ID")
    show_parser.add_argument("--snapshot-id", default=None, help="Snapshot ID (default: latest)")

    # query
    query_parser = subparsers.add_parser("query", help="Query knowledge base")
    query_parser.add_argument("query_type", choices=["file", "symbol", "module", "changes", "semantic"], help="Query type")
    query_parser.add_argument("target", nargs="?", default=None, help="Target (file path, symbol name, module name, or search query)")
    query_parser.add_argument("--repo", required=True, help="Repository ID")
    query_parser.add_argument("--snapshot-id", default=None, help="Snapshot ID")
    query_parser.add_argument("--profile", default="review-agent", help="Agent profile (default: review-agent)")
    query_parser.add_argument("--files", nargs="+", default=[], help="Changed files (for 'changes' query)")
    query_parser.add_argument("--top-k", type=int, default=10, help="Max results for semantic search")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # profiles
    subparsers.add_parser("profiles", help="List available agent profiles")

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args(argv)

    if args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "show":
        return cmd_show(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "profiles":
        return cmd_profiles(args)
    elif args.command == "version":
        return cmd_version(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())