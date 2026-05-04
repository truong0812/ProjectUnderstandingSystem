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

## Documentation

Current project documents:

- [MVP Specification](docs/MVP.md)

Planned next documents:

- `docs/ARCHITECTURE.md`
- `docs/SCHEMA.md`
- `docs/AGENT_PROFILES.md`
- `docs/INGEST_FLOW.md`

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
