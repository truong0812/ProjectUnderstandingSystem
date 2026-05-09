"""CLI for the Project Understanding System V2.

Provides two commands:

* ``ingest`` – scans a repository, parses Python files, builds a deterministic
  code graph, infers a simple architecture, and writes a layered snapshot.
* ``show-architecture`` – prints the architecture map from a snapshot JSON file.
"""

import json
import sys
from pathlib import Path
import click

from ..scan import scan_repository
from ..parse import parse_python_file
from ..graph import build_code_graph
from ..architecture import infer_architecture
from ..storage import write_snapshot


@click.group()
def cli() -> None:
    """Root command group for ``puv2`` CLI."""


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True, file_okay=False))
@click.option("--output-dir", default="output", help="Directory to store snapshots")
def ingest(repo_path: str, output_dir: str) -> None:
    """Ingest *repo_path* and produce a layered snapshot."""
    click.echo(f"Scanning repository at {repo_path} …")
    scan_result = scan_repository(repo_path)

    click.echo("Parsing source files …")
    parsed: dict = {}
    for file_path in scan_result.get("source", []):
        if file_path.endswith('.py'):
            parsed[file_path] = parse_python_file(file_path)

    click.echo("Building code graph …")
    graph = build_code_graph(parsed)

    click.echo("Inferring architecture …")
    arch = infer_architecture(repo_path)

    snapshot = {
        "architecture": arch.dict(),
        "graph": {k: [obj.dict() for obj in v] for k, v in graph.items()},
    }

    project_name = Path(repo_path).name
    click.echo(f"Writing snapshot for project {project_name} …")
    write_snapshot(project_name, snapshot, output_dir)
    click.echo("Ingest complete.")


@cli.command()
@click.argument("snapshot_path", type=click.Path(exists=True, dir_okay=False))
def show_architecture(snapshot_path: str) -> None:
    """Print the architecture map from a snapshot JSON file."""
    data = json.load(open(snapshot_path, "r", encoding="utf-8"))
    arch = data.get("architecture")
    click.echo(json.dumps(arch, indent=2))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
