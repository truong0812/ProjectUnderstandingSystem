# Project Understanding System

Project Understanding System is a new project for building a `Project Understanding Agent`.

Its job is to transform a source code repository into a `shared knowledge base` that other AI agents can use without rereading the entire codebase every time they work.

This project is not just about code summarization. It is about building a reusable `AI-readable project memory` for agents such as:

- Review Agent
- Dev Agent
- Doc Agent
- Test Agent
- other specialized agents in the future

## Why this project exists

In most AI-assisted engineering workflows, each agent repeatedly has to:

- scan many files from the repository
- rebuild its own understanding of modules and dependencies
- work without shared context from other agents
- spend extra tokens and time on the same discovery work
- produce inconsistent conclusions across agents

Project Understanding System solves this with a shared architecture:

`Codebase -> Structured Knowledge Base -> AI Agents`

Instead of forcing every agent to read the repository from scratch, the system ingests the codebase once, converts it into structured knowledge, and lets downstream agents consume that knowledge through their own profiles.

## Product vision

The system has two major layers.

### 1. Knowledge Producer

The producer is responsible for:

- ingesting a codebase
- parsing repository structure
- extracting entities and relations
- summarizing files, modules, and symbols
- identifying conventions and risk areas
- building semantic indexes
- materializing a versioned knowledge snapshot

### 2. Knowledge Consumers

Consumer agents such as `Review Agent`, `Dev Agent`, and `Doc Agent` should not need their own separate repository-understanding pipelines.

They all use the same knowledge base, but read it differently through `agent profiles`.

This approach improves:

- consistency across agents
- speed of review and development workflows
- token efficiency
- reuse of repository understanding

## MVP definition

The MVP is designed as a shared knowledge system, not a single-agent feature.

The first validation consumer is `Review Agent`, but the knowledge model must remain generic enough for other agents from the start.

### MVP goals

- build a shared knowledge base for multiple agents
- store knowledge as `file-based shared memory`
- support manual ingest for `1 repo / 1 branch / 1 snapshot`
- support hybrid retrieval: structured + semantic
- support agent-specific behavior through `JSON/YAML profiles`
- keep the architecture multi-language and parser-agnostic

### Out of scope for MVP

- dashboard UI
- required live API service
- automatic sync on every code change
- multi-repo orchestration
- auth and multi-tenant support

## Knowledge snapshot output

Each ingest run should create a versioned snapshot package with artifacts such as:

- `snapshot.json`
- `entities.jsonl`
- `relations.jsonl`
- `summaries.jsonl`
- `conventions.jsonl`
- `risks.jsonl`
- `indexes/`
- `profiles/`

These artifacts act as shared memory files that downstream agents can read directly.

## Shared knowledge model

The MVP uses a single shared schema for all consumer agents.

Core entities:

- `Repository`
- `Snapshot`
- `File`
- `Module`
- `Symbol`
- `Relation`
- `Summary`
- `Convention`
- `RiskArea`

This model keeps the knowledge base generic enough for multiple agents while still preserving enough structure for agent-specific retrieval.

## Agent profiles

Each consumer agent uses a profile to decide:

- which entities to prioritize
- which relations matter most
- whether conventions should be included
- whether risks should be included
- whether related files should be included
- how retrieval results should be ranked
- what summary depth is needed

The MVP should start with three profiles:

- `review-agent`
- `dev-agent`
- `doc-agent`

The knowledge base is shared.
The retrieval behavior is profile-specific.

## High-level architecture

At a high level, the system works like this:

1. Read repository metadata and current revision
2. Walk the repository tree with skip rules
3. Detect languages and parse supported files
4. Extract structural entities and relations
5. Generate summaries at file, module, and symbol levels
6. Detect conventions and risk areas
7. Build embeddings and semantic indexes
8. Write a snapshot package atomically
9. Let consumer agents query the snapshot through profiles

## Tech stack direction

Current MVP direction:

- `Python 3.12`
- `Pydantic v2`
- `tree-sitter`
- `JSON/JSONL` for structured artifact storage
- local vector index behind an internal abstraction
- provider-agnostic adapters for embeddings and LLMs
- `pytest`
- `ruff`
- `black`
- `mypy`

This stack is chosen to:

- move quickly on the MVP
- fit parsing and AI workflow needs
- avoid early lock-in to one provider or serving layer
- keep the architecture open for later expansion

## Shared memory strategy

The long-term direction is to treat shared memory as a combination of:

- a structured knowledge layer
- a semantic retrieval layer

The structured layer remains the source of truth for:

- repository and snapshot identity
- files, modules, and symbols
- relations and dependency structure
- conventions and risk areas

The vector database is intended to act as a `semantic memory layer`, not as the entire knowledge base.

It will be used for:

- semantic retrieval of relevant summaries
- natural-language search over project knowledge
- ranking candidate context for downstream agents

It should not replace the structured layer for:

- deterministic entity lookup
- snapshot versioning
- relation integrity
- change impact analysis

In practice, the expected direction is:

`Structured Knowledge Base + Vector Database -> Shared Memory for AI Agents`

## Success criteria

The MVP is successful when it can:

1. ingest a repository into a valid knowledge snapshot
2. validate the snapshot against a clear schema
3. support multiple consumer profiles on the same snapshot
4. give `Review Agent` enough context to review changes without rereading the whole repository
5. let `Dev Agent` and `Doc Agent` reuse the same knowledge base with different retrieval behavior

## Current implementation status

### Phase 1: Codebase Ingest + Structured Snapshot ✅ COMPLETE

- Scanner with `.gitignore`-aware skip rules
- Language detection (Python, TypeScript, C#)
- Tree-sitter–based entity extraction (functions, classes, methods, imports)
- Relation builder (imports, calls, contains, depends_on, inherits)
- LLM-powered and heuristic summarization (OpenAI-compatible adapter)
- Snapshot package with JSON storage (files, symbols, relations, summaries)
- Full CLI: `pus ingest`, `pus list`, `pus show`

### Phase 2: Agent Profile + Structured Retrieval ✅ COMPLETE

- Agent profile model with YAML support (entities, relations, ranking, limits)
- 3 default profiles: `review-agent`, `dev-agent`, `doc-agent`
- Retrieval engine with 4 query primitives:
  - `file_context(path, profile)` — file + symbols + related files
  - `symbol_context(name, profile)` — symbol + containing file + siblings
  - `module_context(name, profile)` — module + files + symbols
  - `change_context(files, profile)` — changed files + impact analysis
- Context bundle with relevance scoring and agent-readable output
- CLI: `pus query file|symbol|module|changes`, `pus profiles`

### Phase 3: Semantic Search + Enrichment ✅ COMPLETE

- TF-IDF–based semantic index with cosine similarity (zero-dependency)
- Symbol-level and module-level summaries (heuristic + LLM)
- Convention detection (naming, testing, docstring patterns)
- Risk area detection (large files, deep nesting, God classes, complexity)
- `semantic_context(query, profile)` retrieval primitive
- Pipeline enrichment: conventions, risks, semantic index built during ingest
- CLI: `pus query semantic "natural language query" --repo <id> --top-k N`

## Usage Guide

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/truong0812/ProjectUnderstandingSystem.git
cd ProjectUnderstandingSystem
```

#### Option A: Install with pip (editable mode, recommended)

```bash
pip install -e .
```

This installs the `pus` CLI command and all dependencies from `pyproject.toml`.

#### Option B: Install with requirements.txt only

```bash
pip install -r requirements.txt
```

> **Note:** With Option B, you won't get the `pus` CLI command. You'll need to run the CLI manually:
> ```bash
> python -m project_understanding.cli.main ingest /path/to/repo --no-llm
> ```
> For full CLI support, use Option A.

#### Verify installation

```bash
pus version
```

**Requirements:** Python 3.12+

**No external services needed** — the system works out-of-the-box with:
- TF-IDF semantic search (pure Python, no vector database required)
- Heuristic summarization (no LLM API key required)

### 2. Configuration (Optional)

Create a `.env` file in the project root to enable LLM-powered summaries:

```env
# Optional: Enable LLM summarization (without this, heuristic summaries are used)
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1    # Or any OpenAI-compatible endpoint
OPENAI_MODEL=gpt-4o-mini                       # Model to use for summaries
```

> **Note:** If you don't configure LLM, the system still works fully — it uses heuristic summaries based on code structure (class names, function signatures, docstrings). This is sufficient for most use cases.

### 3. Ingest a Repository

```bash
# Basic ingest (no LLM, heuristic summaries only — works offline)
pus ingest /path/to/your/repo --no-llm

# Ingest with LLM summaries (requires OPENAI_API_KEY in .env)
pus ingest /path/to/your/repo

# Ingest with LLM but skip symbol/module enrichment (faster)
pus ingest /path/to/your/repo --no-enrichment

# Specify custom output directory
pus ingest /path/to/your/repo --no-llm --output-dir ./my-snapshots
```

**What happens during ingest:**
1. Scan repository tree (respects `.gitignore`)
2. Detect languages (Python, TypeScript, C#)
3. Parse files → extract symbols (classes, functions, methods, imports)
4. Build relations (imports, calls, contains, depends_on, inherits)
5. Generate summaries (file-level, symbol-level, module-level)
6. Detect conventions (naming patterns, test files, docstrings)
7. Detect risk areas (large files, deep nesting, God classes)
8. Build semantic index (TF-IDF + cosine similarity)
9. Save snapshot package to disk

**Performance flags:**
- `--no-llm` — Skip all LLM calls, use heuristic summaries only (fastest)
- `--no-enrichment` — Use LLM for file summaries but skip symbol/module enrichment (good balance of speed and quality)

**Output (heuristic):**
```
Snapshot: fb56df2432702a09
  Repository: 509135a5e849199a
  Branch: main @ 4a8233f1
  Files:     47
  Symbols:   257
  Relations: 304
  Summaries: 304
  Time:      0.8s
```

**Output (LLM with --no-enrichment on real C# project):**
```
Snapshot: 4eb2863a64c6b247
  Repository: 1a44a15db1129690
  Branch: main @ 7ede2fdfd0b1
  Files:     131
  Symbols:   254
  Relations: 429
  Summaries: 131
  Time:      269.7s
```

### 4. Manage Snapshots

```bash
# List all snapshots for a repository
pus list <repo_id>

# Show detailed snapshot info
pus show <repo_id>

# Show a specific snapshot
pus show <repo_id> --snapshot-id <snapshot_id>
```

**Tip:** The `repo_id` is shown in the ingest output. It's a hash generated from the repository path.

### 5. Query the Knowledge Base

All query commands require `--repo <repo_id>` to identify which repository's snapshot to use.

#### 5a. File Context — Get everything about a file

```bash
pus query file "src/project_understanding/ingest/pipeline.py" --repo <repo_id>
```

Returns: file info + all symbols in the file + related files (imports/dependents) + summary.

#### 5b. Symbol Context — Get everything about a class/function

```bash
pus query symbol "RetrievalEngine" --repo <repo_id> --profile dev-agent
```

Returns: symbol definition + containing file + sibling symbols + callers/callees.

#### 5c. Module Context — Get everything about a module/directory

```bash
pus query module "ingest" --repo <repo_id> --profile doc-agent
```

Returns: all files in the module + all symbols + inter-module relations + module summary.

#### 5d. Change Impact — Analyze affected code for PR review

```bash
pus query changes --files "src/a.py" "src/b.py" --repo <repo_id> --profile review-agent
```

Returns: changed files + symbols modified in those files + dependent files that may be affected + risk assessment.

#### 5e. Semantic Search — Natural language query

```bash
# Search with natural language
pus query semantic "how does authentication work" --repo <repo_id> --top-k 10

# Search with specific profile
pus query semantic "error handling patterns" --repo <repo_id> --profile review-agent --top-k 5
```

Returns: ranked list of files/symbols matching the query, sorted by relevance score.

**Note:** `--top-k` controls how many results to return (default: 10). Higher = more results but more context.

### 6. Agent Profiles

Profiles control how retrieval works for different agent use cases:

```bash
# List all available profiles
pus profiles
```

**Built-in profiles:**

| Profile | Purpose | Prioritizes | Ranking | Includes Risks |
|---------|---------|-------------|---------|----------------|
| `review-agent` | Code review | Files, Symbols, Relations | Dependency depth | ✅ Yes |
| `dev-agent` | Development assistance | Modules, Symbols, Files | Breadth-first | ❌ No |
| `doc-agent` | Documentation generation | Modules, Files, Symbols | Relevance | ❌ No |

Use `--profile <name>` with any query command:

```bash
pus query file "src/main.py" --repo <repo_id> --profile review-agent
pus query symbol "MyClass" --repo <repo_id> --profile dev-agent
pus query module "ingest" --repo <repo_id> --profile doc-agent
```

### 7. Output Formats

#### Human-readable (default)
```bash
pus query file "src/main.py" --repo <repo_id>
```

#### JSON (for programmatic use by agents)
```bash
pus query file "src/main.py" --repo <repo_id> --json
```

The JSON output is a `ContextBundle` that can be directly consumed by AI agents:

```json
{
  "bundle_id": "abc123",
  "snapshot_id": "fb56df2432702a09",
  "profile_name": "review-agent",
  "query_info": { ... },
  "items": [
    {
      "item_type": "File",
      "name": "main.py",
      "path": "src/main.py",
      "relevance_score": 0.95,
      "summary": "...",
      "metadata": { ... }
    }
  ],
  "total_relations": 12,
  "conventions": [ ... ],
  "risks": [ ... ]
}
```

### 8. Complete Workflow Example

```bash
# Step 1: Install
pip install -e .
# Or: pip install -r requirements.txt  (no CLI, use python -m instead)

# Step 2: Ingest your repository (works fully offline)
pus ingest /path/to/my-project --no-llm
# Output: Repository ID = 509135a5e849199a

# Step 3: Check what was ingested
pus show 509135a5e849199a

# Step 4: Query for different use cases

# Review a PR that changed 2 files
pus query changes --files "src/auth/login.py" "src/auth/session.py" \
  --repo 509135a5e849199a --profile review-agent

# Find how authentication works (semantic)
pus query semantic "authentication and login flow" \
  --repo 509135a5e849199a --top-k 5

# Get context about a specific class
pus query symbol "UserService" \
  --repo 509135a5e849199a --profile dev-agent

# Get full module documentation context
pus query module "auth" \
  --repo 509135a5e849199a --profile doc-agent

# Step 5: Use JSON output to feed into your AI agent
pus query changes --files "src/auth/login.py" \
  --repo 509135a5e849199a --profile review-agent --json > context.json
```

### 9. Programmatic Usage (Python API)

You can also use the system as a Python library:

```python
from project_understanding.ingest.pipeline import ingest_repository
from project_understanding.storage.snapshot_storage import SnapshotStorage
from project_understanding.profiles.registry import ProfileRegistry
from project_understanding.retrieval.engine import RetrievalEngine

# Ingest
package = ingest_repository("/path/to/repo", use_llm=False)

# Or load from disk
storage = SnapshotStorage()
package = storage.read(repo_id="509135a5e849199a")

# Query
registry = ProfileRegistry()
profile = registry.get("review-agent")
engine = RetrievalEngine(package)

# File context
bundle = engine.file_context("src/main.py", profile)
print(bundle.to_agent_context())

# Semantic search
bundle = engine.semantic_context("how does parsing work", profile, top_k=5)
for item in bundle.items:
    print(f"{item.name} ({item.relevance_score:.0%})")

# Get JSON for agent consumption
json_str = bundle.model_dump_json(indent=2)
```

## Project structure

```
src/project_understanding/
├── __init__.py
├── config.py                    # Settings (env vars, paths)
├── cli/
│   └── main.py                  # CLI entry point (pus command)
├── models/
│   ├── entities.py              # File, Module, Symbol models
│   ├── relations.py             # Relation model with types
│   ├── summaries.py             # Summary model
│   ├── conventions.py           # Convention + RiskArea models
│   └── snapshot.py              # SnapshotPackage (top-level container)
├── ingest/
│   ├── scanner.py               # Repository walker with skip rules
│   ├── language_detect.py       # Language detection from extension
│   ├── parser_base.py           # Base tree-sitter parser
│   ├── parsers/                 # Language-specific parsers
│   │   ├── python_parser.py
│   │   ├── typescript_parser.py
│   │   └── csharp_parser.py
│   ├── entity_extractor.py      # Orchestrates parsing per file
│   ├── relation_builder.py      # Builds import/call/depends relations
│   ├── summarizer.py            # LLM + heuristic summarization
│   ├── enrichment.py            # Symbol + module summary enrichment
│   ├── convention_detector.py   # Naming/testing/docstring conventions
│   ├── risk_detector.py         # Large files, complexity, God classes
│   └── pipeline.py              # Full ingest pipeline orchestrator
├── adapters/
│   ├── llm_base.py              # Abstract LLM interface
│   └── llm_openai_compatible.py # OpenAI-compatible adapter
├── storage/
│   └── snapshot_storage.py      # JSON/JSONL read/write
├── profiles/
│   ├── models.py                # AgentProfile + RankingMode
│   └── registry.py              # Profile registry + defaults
└── retrieval/
    ├── context_bundle.py         # ContextBundle + ContextItem
    ├── semantic_index.py         # TF-IDF semantic index
    └── engine.py                 # RetrievalEngine (5 query primitives)
```

## Documentation

- [MVP Specification](docs/MVP.md)
- [Architecture](docs/ARCHITECTURE.md) *(planned)*
- [Agent Profiles](docs/AGENT_PROFILES.md) *(planned)*

## Roadmap after MVP

- incremental ingest based on file hashes
- active snapshot management
- richer dependency graph support
- vector database as a semantic memory layer on top of structured knowledge
- PR-aware retrieval flows
- optional live API or service layer
- multi-branch and multi-repo support
- observability
- policy engine per agent type

## Project statement

> Project Understanding System turns a codebase into a shared, structured, versioned knowledge base so that multiple AI agents can query and use project understanding through their own configuration, instead of rereading the full source code every time.
