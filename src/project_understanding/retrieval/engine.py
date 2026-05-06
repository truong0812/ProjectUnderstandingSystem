"""Retrieval engine — structured knowledge retrieval for AI agents.

Implements the 4 Phase 2 query primitives:
- file_context(path, profile)
- symbol_context(symbol_ref, profile)
- module_context(module_id, profile)
- change_context(changed_files, profile)

Each returns a ContextBundle filtered and ranked by the agent's profile.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from project_understanding.models.entities import File, Module, Symbol
from project_understanding.models.relations import Relation, RelationType
from project_understanding.models.snapshot import SnapshotPackage
from project_understanding.models.summaries import Summary
from project_understanding.models.conventions import Convention, RiskArea
from project_understanding.profiles.models import AgentProfile, RankingMode
from project_understanding.retrieval.context_bundle import ContextBundle, ContextItem
from project_understanding.retrieval.semantic_index import SemanticIndex, build_semantic_index


class RetrievalEngine:
    """Structured knowledge retrieval engine.

    Queries a snapshot package using agent profiles to produce
    context bundles tailored for each agent's needs.
    """

    def __init__(self, package: SnapshotPackage) -> None:
        """Initialize with a loaded snapshot.

        Args:
            package: The snapshot to query against.
        """
        self._package = package
        self._file_by_path: dict[str, File] = {f.path: f for f in package.files}
        self._file_by_id: dict[str, File] = {f.file_id: f for f in package.files}
        self._symbol_by_name: dict[str, list[Symbol]] = {}
        self._symbol_by_id: dict[str, Symbol] = {s.symbol_id: s for s in package.symbols}
        self._module_by_id: dict[str, Module] = {m.module_id: m for m in package.modules}
        self._module_by_name: dict[str, Module] = {m.name: m for m in package.modules}
        self._summary_by_target: dict[str, Summary] = {s.target_id: s for s in package.summaries}

        for sym in package.symbols:
            if sym.name not in self._symbol_by_name:
                self._symbol_by_name[sym.name] = []
            self._symbol_by_name[sym.name].append(sym)

    def file_context(self, path: str, profile: AgentProfile) -> ContextBundle:
        """Get context around a specific file.

        Returns the file, its symbols, related files (imports/depends_on),
        and associated summaries.

        Args:
            path: File path relative to repo root.
            profile: Agent profile controlling retrieval.

        Returns:
            ContextBundle with relevant context.
        """
        items: list[ContextItem] = []
        relations: list[dict] = []

        # 1. Find the primary file
        target_file = self._file_by_path.get(path)
        if not target_file:
            return self._empty_bundle("file_context", {"path": path}, profile)

        # 2. Add the file itself
        summary = self._get_summary(target_file.file_id)
        items.append(ContextItem(
            entity_type="File",
            entity_id=target_file.file_id,
            data=target_file.model_dump(mode="json"),
            summary=summary,
            relevance_score=1.0,
            reason="Primary target file",
        ))

        # 3. Add symbols in this file
        if "Symbol" in profile.preferred_entities:
            for sym in self._package.symbols:
                if sym.file_id == target_file.file_id:
                    items.append(ContextItem(
                        entity_type="Symbol",
                        entity_id=sym.symbol_id,
                        data=sym.model_dump(mode="json"),
                        summary=self._get_summary(sym.symbol_id),
                        relevance_score=0.95,
                        reason=f"Defined in {path}",
                    ))

        # 4. Add related files (imports, depends_on)
        if profile.include_related_files:
            related = self._get_related_files(target_file.file_id, profile)
            items.extend(related)

        # 5. Collect relevant relations
        relations = self._get_relations_for(target_file.file_id, profile)

        return self._build_bundle(
            "file_context", {"path": path}, profile, items, relations,
        )

    def symbol_context(self, symbol_ref: str, profile: AgentProfile) -> ContextBundle:
        """Get context around a specific symbol.

        Args:
            symbol_ref: Symbol name or qualified path.
            profile: Agent profile controlling retrieval.

        Returns:
            ContextBundle with symbol context.
        """
        items: list[ContextItem] = []
        relations: list[dict] = []

        # Find symbol by name or path
        symbols = self._symbol_by_name.get(symbol_ref, [])
        target_sym = None

        if symbols:
            target_sym = symbols[0]
        else:
            # Try by ID
            target_sym = self._symbol_by_id.get(symbol_ref)

        if not target_sym:
            return self._empty_bundle("symbol_context", {"symbol_ref": symbol_ref}, profile)

        # Add the symbol
        items.append(ContextItem(
            entity_type="Symbol",
            entity_id=target_sym.symbol_id,
            data=target_sym.model_dump(mode="json"),
            summary=self._get_summary(target_sym.symbol_id),
            relevance_score=1.0,
            reason="Primary target symbol",
        ))

        # Add the containing file
        containing_file = self._file_by_id.get(target_sym.file_id)
        if containing_file:
            items.append(ContextItem(
                entity_type="File",
                entity_id=containing_file.file_id,
                data=containing_file.model_dump(mode="json"),
                summary=self._get_summary(containing_file.file_id),
                relevance_score=0.9,
                reason=f"Contains symbol '{target_sym.name}'",
            ))

        # Add sibling symbols
        if "Symbol" in profile.preferred_entities:
            for sym in self._package.symbols:
                if sym.file_id == target_sym.file_id and sym.symbol_id != target_sym.symbol_id:
                    items.append(ContextItem(
                        entity_type="Symbol",
                        entity_id=sym.symbol_id,
                        data=sym.model_dump(mode="json"),
                        relevance_score=0.6,
                        reason=f"Sibling symbol in same file",
                    ))

        # Call relations
        relations = self._get_relations_for(target_sym.symbol_id, profile)

        return self._build_bundle(
            "symbol_context", {"symbol_ref": symbol_ref}, profile, items, relations,
        )

    def module_context(self, module_name: str, profile: AgentProfile) -> ContextBundle:
        """Get context for a module.

        Args:
            module_name: Module name or ID.
            profile: Agent profile controlling retrieval.

        Returns:
            ContextBundle with module context.
        """
        items: list[ContextItem] = []
        relations: list[dict] = []

        target_module = self._module_by_name.get(module_name)
        if not target_module:
            target_module = self._module_by_id.get(module_name)

        if not target_module:
            return self._empty_bundle("module_context", {"module_name": module_name}, profile)

        # Add the module
        items.append(ContextItem(
            entity_type="Module",
            entity_id=target_module.module_id,
            data=target_module.model_dump(mode="json"),
            relevance_score=1.0,
            reason="Primary target module",
        ))

        # Add files in this module
        for file_id in target_module.files:
            f = self._file_by_id.get(file_id)
            if f:
                items.append(ContextItem(
                    entity_type="File",
                    entity_id=f.file_id,
                    data=f.model_dump(mode="json"),
                    summary=self._get_summary(f.file_id),
                    relevance_score=0.9,
                    reason=f"Part of module '{module_name}'",
                ))

                # Add symbols in each file
                if "Symbol" in profile.preferred_entities:
                    for sym in self._package.symbols:
                        if sym.file_id == f.file_id:
                            items.append(ContextItem(
                                entity_type="Symbol",
                                entity_id=sym.symbol_id,
                                data=sym.model_dump(mode="json"),
                                relevance_score=0.7,
                                reason=f"Symbol in module '{module_name}'",
                            ))

        relations = self._get_relations_for(target_module.module_id, profile)

        return self._build_bundle(
            "module_context", {"module_name": module_name}, profile, items, relations,
        )

    def change_context(
        self, changed_files: list[str], profile: AgentProfile
    ) -> ContextBundle:
        """Get context for a set of changed files (e.g., PR review).

        This is the primary query for the review-agent profile.

        Args:
            changed_files: List of changed file paths.
            profile: Agent profile controlling retrieval.

        Returns:
            ContextBundle with change impact context.
        """
        items: list[ContextItem] = []
        relations: list[dict] = []
        seen_ids: set[str] = set()

        for path in changed_files:
            f = self._file_by_path.get(path)
            if not f:
                continue

            # Add changed file
            if f.file_id not in seen_ids:
                seen_ids.add(f.file_id)
                items.append(ContextItem(
                    entity_type="File",
                    entity_id=f.file_id,
                    data=f.model_dump(mode="json"),
                    summary=self._get_summary(f.file_id),
                    relevance_score=1.0,
                    reason="Changed file",
                ))

            # Add symbols in changed file
            if "Symbol" in profile.preferred_entities:
                for sym in self._package.symbols:
                    if sym.file_id == f.file_id and sym.symbol_id not in seen_ids:
                        seen_ids.add(sym.symbol_id)
                        items.append(ContextItem(
                            entity_type="Symbol",
                            entity_id=sym.symbol_id,
                            data=sym.model_dump(mode="json"),
                            relevance_score=0.9,
                            reason=f"Symbol in changed file '{path}'",
                        ))

            # Add related files
            if profile.include_related_files:
                related = self._get_related_files(f.file_id, profile)
                for item in related:
                    if item.entity_id not in seen_ids:
                        seen_ids.add(item.entity_id)
                        item.relevance_score *= 0.7  # Lower relevance for indirect
                        items.append(item)

            # Collect relations
            rels = self._get_relations_for(f.file_id, profile)
            relations.extend(rels)

        # Deduplicate relations
        seen_rels: set[str] = set()
        unique_rels: list[dict] = []
        for r in relations:
            key = f"{r.get('source_id')}:{r.get('relation_type')}:{r.get('target_id')}"
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(r)

        return self._build_bundle(
            "change_context",
            {"changed_files": changed_files},
            profile,
            items,
            unique_rels,
        )

    def semantic_context(
        self,
        query: str,
        profile: AgentProfile,
        top_k: int = 10,
        semantic_index: SemanticIndex | None = None,
    ) -> ContextBundle:
        """Semantic search over summaries using natural language query.

        Phase 3 query primitive. Finds relevant files, symbols, and modules
        by searching their summaries with TF-IDF / embedding similarity.

        Args:
            query: Natural language query string.
            profile: Agent profile controlling retrieval.
            top_k: Maximum semantic results.
            semantic_index: Pre-built index (built from package if not provided).

        Returns:
            ContextBundle with semantically relevant context.
        """
        items: list[ContextItem] = []
        relations: list[dict] = []

        # Build or use provided index
        index = semantic_index
        if index is None:
            index = build_semantic_index(
                self._package.summaries,
                self._package.files,
                self._package.symbols,
            )

        # Search
        results = index.search(query, top_k=top_k)

        for doc_id, score, metadata in results:
            target_id = metadata.get("target_id", "")
            target_type = metadata.get("target_type", "")

            if target_type == "file":
                f = self._file_by_id.get(target_id)
                if f:
                    items.append(ContextItem(
                        entity_type="File",
                        entity_id=f.file_id,
                        data=f.model_dump(mode="json"),
                        summary=self._get_summary(f.file_id),
                        relevance_score=score,
                        reason=f"Semantic match for '{query}'",
                    ))
            elif target_type == "symbol":
                sym = self._symbol_by_id.get(target_id)
                if sym:
                    items.append(ContextItem(
                        entity_type="Symbol",
                        entity_id=sym.symbol_id,
                        data=sym.model_dump(mode="json"),
                        summary=self._get_summary(sym.symbol_id),
                        relevance_score=score,
                        reason=f"Semantic match for '{query}'",
                    ))
            elif target_type == "module":
                mod = self._module_by_id.get(target_id)
                if mod:
                    items.append(ContextItem(
                        entity_type="Module",
                        entity_id=mod.module_id,
                        data=mod.model_dump(mode="json"),
                        relevance_score=score,
                        reason=f"Semantic match for '{query}'",
                    ))

        # Add conventions if profile wants them
        if profile.include_conventions:
            for conv in self._package.conventions:
                items.append(ContextItem(
                    entity_type="Convention",
                    entity_id=conv.convention_id,
                    data=conv.model_dump(mode="json"),
                    summary=conv.description,
                    relevance_score=0.5,
                    reason="Detected convention",
                ))

        # Add risks if profile wants them
        if profile.include_risks:
            for risk in self._package.risks:
                items.append(ContextItem(
                    entity_type="RiskArea",
                    entity_id=risk.risk_id,
                    data=risk.model_dump(mode="json"),
                    summary=risk.description,
                    relevance_score=0.6 if risk.severity == "high" else 0.3,
                    reason=f"Risk area: {risk.category.value}",
                ))

        return self._build_bundle(
            "semantic_context",
            {"query": query},
            profile,
            items,
            relations,
        )

    # --- Internal helpers ---

    def _get_summary(self, target_id: str) -> str | None:
        """Get summary text for a target entity."""
        s = self._summary_by_target.get(target_id)
        return s.content if s else None

    def _get_related_files(
        self, file_id: str, profile: AgentProfile
    ) -> list[ContextItem]:
        """Find files related to the given file via relations."""
        items: list[ContextItem] = []

        for rel in self._package.relations:
            if rel.relation_type.value not in profile.preferred_relations:
                continue

            related_file_id = None
            reason = ""

            if rel.source_id == file_id:
                related_file_id = rel.target_id
                reason = f"{rel.relation_type.value} → target"
            elif rel.target_id == file_id:
                related_file_id = rel.source_id
                reason = f"{rel.relation_type.value} ← source"

            if related_file_id and related_file_id not in {item.entity_id for item in items}:
                f = self._file_by_id.get(related_file_id)
                if f:
                    items.append(ContextItem(
                        entity_type="File",
                        entity_id=f.file_id,
                        data=f.model_dump(mode="json"),
                        summary=self._get_summary(f.file_id),
                        relevance_score=0.7,
                        reason=reason,
                    ))

        return items

    def _get_relations_for(
        self, entity_id: str, profile: AgentProfile
    ) -> list[dict]:
        """Get relations involving an entity, filtered by profile."""
        relations: list[dict] = []

        for rel in self._package.relations:
            if rel.relation_type.value not in profile.preferred_relations:
                continue
            if rel.source_id == entity_id or rel.target_id == entity_id:
                relations.append(rel.model_dump(mode="json"))

        return relations

    def _build_bundle(
        self,
        query_type: str,
        query_params: dict,
        profile: AgentProfile,
        items: list[ContextItem],
        relations: list[dict],
    ) -> ContextBundle:
        """Build and rank a context bundle."""
        # Rank items
        items = self._rank_items(items, profile)

        # Truncate to max_items
        items = items[:profile.max_items]

        # Count totals
        file_count = sum(1 for i in items if i.entity_type == "File")
        sym_count = sum(1 for i in items if i.entity_type == "Symbol")
        mod_count = sum(1 for i in items if i.entity_type == "Module")

        bundle_id = hashlib.sha256(
            f"{query_type}:{query_params}:{profile.name}:{self._package.snapshot.snapshot_id}".encode()
        ).hexdigest()[:16]

        # Include glossary if available and profile wants it
        glossary_context = ""
        if getattr(profile, "include_glossary", True):
            glossary_context = self._package.glossary.to_agent_context()

        return ContextBundle(
            bundle_id=bundle_id,
            query_type=query_type,
            query_params=query_params,
            profile_name=profile.name,
            snapshot_id=self._package.snapshot.snapshot_id,
            repo_id=self._package.repository.repo_id,
            items=items,
            relations=relations[:profile.max_items],
            glossary_context=glossary_context,
            total_files=file_count,
            total_symbols=sym_count,
            total_modules=mod_count,
            total_relations=len(relations),
        )

    def _rank_items(
        self, items: list[ContextItem], profile: AgentProfile
    ) -> list[ContextItem]:
        """Rank context items based on the profile's ranking mode."""
        if profile.ranking_mode == RankingMode.DEPENDENCY_DEPTH:
            # Sort by relevance_score descending, direct matches first
            items.sort(key=lambda x: x.relevance_score, reverse=True)
        elif profile.ranking_mode == RankingMode.BREADTH_FIRST:
            # Group by entity type per profile preference, then by score
            entity_order = {e: i for i, e in enumerate(profile.preferred_entities)}
            items.sort(key=lambda x: (entity_order.get(x.entity_type, 99), -x.relevance_score))
        else:  # RELEVANCE
            items.sort(key=lambda x: x.relevance_score, reverse=True)

        return items

    def _empty_bundle(
        self,
        query_type: str,
        query_params: dict,
        profile: AgentProfile,
    ) -> ContextBundle:
        """Return an empty bundle when target is not found."""
        bundle_id = hashlib.sha256(
            f"{query_type}:{query_params}:{profile.name}".encode()
        ).hexdigest()[:16]
        return ContextBundle(
            bundle_id=bundle_id,
            query_type=query_type,
            query_params=query_params,
            profile_name=profile.name,
            snapshot_id=self._package.snapshot.snapshot_id,
            repo_id=self._package.repository.repo_id,
        )