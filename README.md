# Project Understanding System

Project Understanding System is an experiment in building shared, AI-readable
project memory for software engineering agents.

The goal is to transform a source repository into structured knowledge that
Review, Dev, Doc, and Test agents can reuse without rereading the whole codebase
from scratch each time.

## Status

The current codebase is a V1 prototype. It proved the core idea:

- scan a repository
- parse files and symbols
- build relations
- generate summaries
- store snapshots on disk
- query context through agent profiles

However, the next version should not continue the flat "summarize all files"
approach. The project is moving toward a V2 rebuild based on layered project
understanding.

See the full rebuild plan:

- [Layered Rebuild Plan](docs/LAYERED_REBUILD_PLAN.md)

## Why This Exists

In AI-assisted engineering workflows, every agent often has to rediscover the
same facts:

- repository structure
- architectural boundaries
- module responsibilities
- important classes and components
- function-level behavior
- dependency and impact paths
- conventions and risk areas

That repeated discovery is slow, expensive, and inconsistent.

Project Understanding System aims to create a shared knowledge base that agents
can query according to their job.

```text
Codebase -> Structured Project Memory -> Specialized AI Agents
```

## V2 Direction: Layered Understanding

V2 will read a project the way an engineer usually understands it: from the
highest-level shape down to the exact code involved in a task.

```text
Architecture
  -> Modules / Bounded Contexts
    -> Classes / Components
      -> Functions / Methods
        -> Evidence / Relations / Code snippets
```

Instead of generating a flat summary for every file, V2 will build a layered
map:

- architecture map
- module map
- class/component map
- function/method map
- relation graph
- review context bundles

This makes the output more useful for downstream agents because context can be
selected by level of abstraction and by actual relevance.

## Primary Consumer

The first V2 consumer is the Review Agent.

The system should help a Review Agent answer:

- What changed?
- Which function, class, and module owns the change?
- Which callers, users, or dependencies may be affected?
- Which architectural layer does this change touch?
- Are there risky areas such as authentication, persistence, external APIs, or
  filesystem writes?
- What evidence should the reviewer inspect?

## Output Goal

For a changed file or symbol, V2 should produce a review-oriented context object
containing:

- changed files and changed symbols
- containing class or component
- owning module
- architectural layer
- direct callers and callees
- reverse dependencies and usages
- risk markers
- relevant conventions
- concise review checklist
- evidence with file paths and line ranges

The target flow is:

```text
changed function
-> containing class/component
-> owning module
-> architectural layer
-> impacted callers/users/dependencies
-> risks + review checklist
```

## Documentation

- [Layered Rebuild Plan](docs/LAYERED_REBUILD_PLAN.md)
- [MVP Specification](docs/MVP.md)
- [Previous Improvement Plan](docs/IMPROVEMENT_PLAN.md)

## Legacy Prototype

The current implementation under `src/project_understanding/` is retained as a
reference prototype only. It may still be useful for:

- parser and scanner ideas
- entity and relation extraction patterns
- snapshot storage experiments
- profile-based retrieval experiments

V2 should be treated as a clean rebuild with a new layered model, not a small
incremental patch on the current flat snapshot design.

## Project Statement

Project Understanding System turns a codebase into shared, structured,
versioned project memory so multiple AI agents can reuse project understanding
through their own context needs instead of rereading the full source code every
time.
