"""CLI for the V2 layered prototype."""

from __future__ import annotations

import argparse
import sys

from project_understanding_v2.pipeline import ingest_repository
from project_understanding_v2.review import build_review_context
from project_understanding_v2.storage import LayeredSnapshotStorage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="puv2", description="Layered Project Understanding V2")
    sub = parser.add_subparsers(dest="command")

    ingest = sub.add_parser("ingest", help="Ingest a repository into a layered snapshot")
    ingest.add_argument("repo_path")
    ingest.add_argument("--output-dir", default="./output")
    ingest.add_argument("--project-name", default=None)
    ingest.add_argument("--use-llm", action="store_true")

    show_arch = sub.add_parser("show-architecture", help="Show architecture for a snapshot")
    show_arch.add_argument("snapshot")

    show_module = sub.add_parser("show-module", help="Show a module from a snapshot")
    show_module.add_argument("snapshot")
    show_module.add_argument("module_name")

    review = sub.add_parser("review-context", help="Build review context")
    review.add_argument("snapshot")
    review.add_argument("--changed-file", action="append", default=[])
    review.add_argument("--changed-symbol", action="append", default=[])
    review.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        snapshot = ingest_repository(
            args.repo_path,
            output_dir=args.output_dir,
            use_llm=args.use_llm,
            project_name=args.project_name,
        )
        print(snapshot.model_dump_json(indent=2))
        return 0
    if args.command == "show-architecture":
        snapshot = LayeredSnapshotStorage().read(args.snapshot)
        print(snapshot.architecture.model_dump_json(indent=2))
        return 0
    if args.command == "show-module":
        snapshot = LayeredSnapshotStorage().read(args.snapshot)
        for module in snapshot.modules:
            if module.name == args.module_name or module.module_id == args.module_name:
                print(module.model_dump_json(indent=2))
                return 0
        print(f"Module not found: {args.module_name}", file=sys.stderr)
        return 1
    if args.command == "review-context":
        snapshot = LayeredSnapshotStorage().read(args.snapshot)
        context = build_review_context(snapshot, args.changed_file, args.changed_symbol)
        if args.json:
            print(context.model_dump_json(indent=2))
        else:
            _print_review_context(context)
        return 0

    parser.print_help()
    return 0


def _print_review_context(context) -> None:
    print("Review Context")
    print(f"Changed files: {', '.join(context.changed_files) or '-'}")
    print(f"Changed functions: {', '.join(fn.qualified_name for fn in context.changed_functions) or '-'}")
    print(f"Modules: {', '.join(module.name for module in context.owning_modules) or '-'}")
    print(f"Layers: {', '.join(layer.name for layer in context.architecture_layers) or '-'}")
    if context.risk_markers:
        print(f"Risks: {', '.join(context.risk_markers)}")
    print("Checklist:")
    for item in context.review_checklist:
        print(f"- {item}")


if __name__ == "__main__":
    raise SystemExit(main())
