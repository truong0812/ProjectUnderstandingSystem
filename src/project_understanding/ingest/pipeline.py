"""Ingest pipeline — orchestrates the full codebase ingestion process.

Coordinates scanning, parsing, entity extraction, relation building,
summarization, and snapshot writing.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from project_understanding.adapters.llm_base import LLMProvider
from project_understanding.adapters.llm_openai_compatible import OpenAICompatibleLLM
from project_understanding.config import get_settings
from project_understanding.ingest.entity_extractor import (
    create_file_entity,
    create_module_entities,
    create_symbol_entities,
)
from project_understanding.ingest.language_detect import is_source_file, is_supported_language
from project_understanding.ingest.parser_base import ParsedFile
from project_understanding.ingest.relation_builder import build_all_relations
from project_understanding.ingest.scanner import scan_repository
from project_understanding.ingest.summarizer import generate_file_summary
from project_understanding.ingest.domain_detector import detect_domain_llm
from project_understanding.ingest.convention_detector import detect_conventions
from project_understanding.ingest.risk_detector import detect_risks
from project_understanding.ingest.enrichment import generate_symbol_summaries, generate_module_summaries
from project_understanding.ingest.glossary_generator import generate_glossary
from project_understanding.retrieval.semantic_index import build_semantic_index, SemanticIndex
from project_understanding.models.entities import File, Repository, Snapshot, SnapshotStatus, Symbol
from project_understanding.models.relations import Relation
from project_understanding.models.snapshot import SnapshotPackage
from project_understanding.models.summaries import Summary
from project_understanding.models.conventions import Convention, RiskArea
from project_understanding.storage.snapshot_storage import SnapshotStorage


def _get_project_name(repo_path: str) -> str:
    """Detect a human-readable project name from git remote or directory.

    Priority:
        1. Parse basename from git remote URL (strip .git suffix)
        2. Use directory name of the repo path

    Returns:
        A clean, filesystem-safe project name (e.g., 'my-project').
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Extract basename from URL (works for both https and ssh)
            # e.g., "https://github.com/user/my-project.git" → "my-project"
            # e.g., "git@github.com:user/my-project.git" → "my-project"
            name = url.rstrip("/").split("/")[-1]
            if name.endswith(".git"):
                name = name[:-4]
            # Clean for filesystem safety
            name = "".join(c if c.isalnum() or c in "-_" else "-" for c in name)
            if name:
                return name
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback: directory name
    dir_name = Path(repo_path).resolve().name
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in dir_name)


def _get_repo_id(repo_path: str) -> str:
    """Generate a repository ID from path and git info."""
    abs_path = str(Path(repo_path).resolve())
    # Try to get git remote URL
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Create repo_id from URL
            return hashlib.sha256(url.encode()).hexdigest()[:16]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback: use directory name + path hash
    dir_name = Path(abs_path).name
    path_hash = hashlib.sha256(abs_path.encode()).hexdigest()[:8]
    return f"{dir_name}_{path_hash}"


def _get_git_info(repo_path: str) -> tuple[str, str]:
    """Get git branch and commit SHA."""
    branch = "main"
    commit_sha = ""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0:
            commit_sha = result.stdout.strip()[:12]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return branch, commit_sha


def _get_parser(language: str):
    """Get the appropriate parser for a language."""
    if language == "python":
        from project_understanding.ingest.parsers.python_parser import PythonParser
        return PythonParser()
    elif language == "typescript":
        from project_understanding.ingest.parsers.typescript_parser import TypeScriptParser
        return TypeScriptParser(tsx=False)
    elif language == "c_sharp":
        from project_understanding.ingest.parsers.csharp_parser import CSharpParser
        return CSharpParser()
    return None


def ingest_repository(
    repo_path: str,
    use_llm: bool = True,
    output_dir: str | None = None,
    skip_patterns: list[str] | None = None,
    no_enrichment: bool = False,
    project_name: str | None = None,
    progress_callback=None,
) -> SnapshotPackage:
    """Run the full ingestion pipeline on a repository.

    Steps:
        1. Scan repository for files
        2. Parse each source file with tree-sitter
        3. Extract entities (Files, Symbols, Modules)
        4. Build relations (contains, imports, calls, depends_on)
        5. Generate file summaries (LLM or heuristic)
        6. Write snapshot to disk

    Args:
        repo_path: Path to the repository root.
        use_llm: Whether to use LLM for summaries.
        output_dir: Override output directory.
        skip_patterns: Override skip patterns.
        no_enrichment: Skip symbol/module LLM enrichment.
        project_name: Human-readable project name (auto-detected if None).
        progress_callback: Optional callback(stage, current, total) for progress.

    Returns:
        Complete SnapshotPackage with all extracted knowledge.
    """
    repo_path = str(Path(repo_path).resolve())

    if not Path(repo_path).is_dir():
        raise ValueError(f"Not a directory: {repo_path}")

    settings = get_settings()

    # --- Step 0: Prepare metadata ---
    repo_id = _get_repo_id(repo_path)
    resolved_project_name = project_name or _get_project_name(repo_path)
    branch, commit_sha = _get_git_info(repo_path)
    snapshot_id = Snapshot.make_snapshot_id(repo_id, branch, commit_sha)

    repository = Repository(
        repo_id=repo_id,
        url="",
        branch=branch,
        commit_sha=commit_sha,
    )

    snapshot = Snapshot(
        snapshot_id=snapshot_id,
        repo_id=repo_id,
        branch=branch,
        commit_sha=commit_sha,
    )

    if progress_callback:
        progress_callback("scanning", 0, 1)

    # --- Step 1: Scan ---
    scan_result = scan_repository(repo_path, skip_patterns=skip_patterns)

    if progress_callback:
        progress_callback("scanning", 1, 1)

    # --- Step 2: Parse & Extract ---
    files: list[File] = []
    all_symbols: list[Symbol] = []
    all_parsed: list[ParsedFile] = []
    file_contents: dict[str, str] = {}
    file_symbols: dict[str, list[Symbol]] = {}

    total_files = len(scan_result.files)

    for idx, scanned_file in enumerate(scan_result.files):
        if progress_callback:
            progress_callback("parsing", idx, total_files)

        # Create file entity
        file_entity = create_file_entity(scanned_file, snapshot_id, repo_id)
        files.append(file_entity)

        # Read content
        try:
            with open(scanned_file.absolute_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            content = ""

        file_contents[file_entity.file_id] = content

        # Parse if supported language
        if is_source_file(scanned_file.path, scanned_file.extension) and content:
            language = file_entity.language
            if is_supported_language(language):
                parser = _get_parser(language)
                if parser:
                    try:
                        parsed = parser.parse(scanned_file.path, content)
                        all_parsed.append(parsed)

                        # Extract symbols
                        symbols = create_symbol_entities(
                            parsed.symbols,
                            file_entity.file_id,
                            repo_id,
                            scanned_file.path,
                        )
                        all_symbols.extend(symbols)
                        file_symbols[file_entity.file_id] = symbols
                    except Exception as e:
                        parsed = ParsedFile(
                            file_path=scanned_file.path,
                            language=language,
                            errors=[str(e)],
                        )
                        all_parsed.append(parsed)

    # --- Step 3: Build modules ---
    modules = create_module_entities(files, snapshot_id, repo_id)

    # Build path -> content mapping (needed for relations + enrichment)
    path_contents = {}
    for f in files:
        content = file_contents.get(f.file_id, "")
        if content:
            path_contents[f.path] = content

    # --- Step 4: Build relations ---
    if progress_callback:
        progress_callback("building_relations", 0, 1)

    relations = build_all_relations(all_parsed, files, modules, all_symbols, repo_id, path_contents)

    if progress_callback:
        progress_callback("building_relations", 1, 1)

    # --- Step 5: Generate summaries ---
    summaries: list[Summary] = []
    llm = None

    if use_llm:
        try:
            llm = OpenAICompatibleLLM()
        except Exception:
            llm = None

    # --- Step 4.5: Detect business domain via LLM (1 call, shared across all summaries) ---
    domain_metadata: dict[str, str] = {}
    if llm:
        code_samples = [c for c in file_contents.values() if c.strip()][:10]
        if code_samples:
            domain_metadata = detect_domain_llm(code_samples, llm)

    if llm:
        # Concurrent LLM summarization (5 workers)
        import threading
        _lock = threading.Lock()
        _completed = [0]

        def _summarize_one(idx_file):
            idx, file_entity = idx_file
            content = file_contents.get(file_entity.file_id, "")
            syms = file_symbols.get(file_entity.file_id, [])
            summary = generate_file_summary(file_entity, content, syms, llm, domain_metadata=domain_metadata)
            with _lock:
                _completed[0] += 1
                if progress_callback:
                    progress_callback("summarizing", _completed[0], len(files))
            return (idx, summary)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(_summarize_one, (i, f)) for i, f in enumerate(files)]
            results = {}
            for future in as_completed(futures):
                idx, summary = future.result()
                results[idx] = summary
        
        # Preserve original file order
        summaries = [results[i] for i in range(len(files))]
    else:
        for idx, file_entity in enumerate(files):
            if progress_callback:
                progress_callback("summarizing", idx, len(files))

            content = file_contents.get(file_entity.file_id, "")
            syms = file_symbols.get(file_entity.file_id, [])

            summary = generate_file_summary(file_entity, content, syms, None, domain_metadata=domain_metadata)
            summaries.append(summary)

    if not no_enrichment:
        # --- Step 5b: Symbol-level summaries (Phase 3) ---
        if progress_callback:
            progress_callback("enriching_symbols", 0, 1)

        symbol_summaries = generate_symbol_summaries(all_symbols, files, path_contents, llm, progress_callback=progress_callback)
        summaries.extend(symbol_summaries)

        if progress_callback:
            progress_callback("enriching_symbols", 1, 1)

        # --- Step 5c: Module-level summaries (Phase 3) ---
        if progress_callback:
            progress_callback("enriching_modules", 0, 1)

        module_summaries = generate_module_summaries(modules, files, all_symbols, summaries, llm)
        summaries.extend(module_summaries)

        if progress_callback:
            progress_callback("enriching_modules", 1, 1)

    # --- Step 5d: Convention detection (Phase 3) ---
    if progress_callback:
        progress_callback("detecting_conventions", 0, 1)

    conventions = detect_conventions(files, modules, all_symbols, relations, path_contents)

    if progress_callback:
        progress_callback("detecting_conventions", 1, 1)

    # --- Step 5e: Risk area detection (Phase 3) ---
    if progress_callback:
        progress_callback("detecting_risks", 0, 1)

    risks = detect_risks(files, all_symbols, path_contents)

    if progress_callback:
        progress_callback("detecting_risks", 1, 1)

    # --- Step 5f: Build semantic index (Phase 3) ---
    if progress_callback:
        progress_callback("building_index", 0, 1)

    semantic_index = build_semantic_index(summaries, files, all_symbols, path_contents)

    if progress_callback:
        progress_callback("building_index", 1, 1)

    # --- Step 5g: Generate domain glossary ---
    if progress_callback:
        progress_callback("generating_glossary", 0, 1)

    glossary = generate_glossary(
        files=files,
        symbols=all_symbols,
        summaries=summaries,
        path_contents=path_contents,
        llm=llm,
        project_name=resolved_project_name,
    )

    if progress_callback:
        progress_callback("generating_glossary", 1, 1)

    # --- Step 6: Assemble and write ---
    snapshot.file_count = len(files)
    snapshot.symbol_count = len(all_symbols)
    snapshot.relation_count = len(relations)
    snapshot.summary_count = len(summaries)
    snapshot.status = SnapshotStatus.COMPLETE

    package = SnapshotPackage(
        repository=repository,
        snapshot=snapshot,
        files=files,
        modules=modules,
        symbols=all_symbols,
        relations=relations,
        summaries=summaries,
        conventions=conventions,
        risks=risks,
        glossary=glossary,
    )

    # Write to disk
    out_dir = output_dir or settings.snapshot_output_dir
    storage = SnapshotStorage(output_dir=out_dir)
    output_path = storage.write(package, project_name=resolved_project_name)

    # Save semantic index alongside snapshot
    try:
        index_dir = Path(out_dir) / resolved_project_name / "indexes"
        semantic_index.save(index_dir / "semantic_index.json")
    except Exception:
        pass  # Non-critical

    if progress_callback:
        progress_callback("complete", 1, 1)

    return package
