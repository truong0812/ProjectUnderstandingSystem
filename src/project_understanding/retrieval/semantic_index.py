"""Semantic index for knowledge base search.

Provides embedding-based semantic search over summaries using
TF-IDF + cosine similarity as the default backend. Can be swapped
to use real embeddings (OpenAI, etc.) when available.

The index is built from summaries and supports natural language queries.
"""

from __future__ import annotations

import math
import re
import json
from collections import Counter, defaultdict
from pathlib import Path

from project_understanding.models.entities import File, Symbol
from project_understanding.models.summaries import Summary
from project_understanding.models.conventions import Convention, RiskArea


# ─── Tokenizer ────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    text = text.lower()
    # Split camelCase and snake_case
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[_\-./\\]", " ", text)
    tokens = re.findall(r"[a-z0-9]{2,}", text)
    return tokens


# ─── TF-IDF Index ─────────────────────────────────────────────────────

class SemanticIndex:
    """Lightweight TF-IDF based semantic index.

    Indexes summaries for natural language search.
    Designed to be swappable with an embedding-based backend later.
    """

    def __init__(self) -> None:
        self._docs: dict[str, list[str]] = {}  # id -> tokens
        self._metadata: dict[str, dict] = {}    # id -> metadata
        self._idf: dict[str, float] = {}        # term -> idf score
        self._tf: dict[str, Counter] = {}       # id -> term frequencies
        self._norms: dict[str, float] = {}      # id -> vector norm
        self._built = False

    def add_document(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """Add a document to the index."""
        tokens = _tokenize(text)
        self._docs[doc_id] = tokens
        self._metadata[doc_id] = metadata or {}
        self._built = False

    def add_summary(self, summary: Summary, extra_context: str = "") -> None:
        """Add a summary to the index with optional extra context."""
        parts = [summary.content]
        if extra_context:
            parts.append(extra_context)
        text = " ".join(parts)
        self.add_document(
            doc_id=summary.summary_id,
            text=text,
            metadata={
                "target_id": summary.target_id,
                "target_type": summary.target_type,
                "level": summary.level.value,
                "generated_by": summary.generated_by.value,
            },
        )

    def build(self) -> None:
        """Build the TF-IDF index from added documents."""
        if not self._docs:
            self._built = True
            return

        n_docs = len(self._docs)
        # Document frequency
        df: dict[str, int] = defaultdict(int)
        for doc_id, tokens in self._docs.items():
            self._tf[doc_id] = Counter(tokens)
            unique_terms = set(tokens)
            for term in unique_terms:
                df[term] += 1

        # IDF with smoothing
        self._idf = {
            term: math.log((n_docs + 1) / (freq + 1)) + 1
            for term, freq in df.items()
        }

        # Compute norms
        self._norms = {}
        for doc_id, tf in self._tf.items():
            norm_sq = 0.0
            for term, count in tf.items():
                tfidf = count * self._idf.get(term, 1.0)
                norm_sq += tfidf * tfidf
            self._norms[doc_id] = math.sqrt(norm_sq) if norm_sq > 0 else 0.0

        self._built = True

    def search(
        self,
        query: str,
        top_k: int = 10,
        filter_type: str | None = None,
    ) -> list[tuple[str, float, dict]]:
        """Search the index for relevant documents.

        Args:
            query: Natural language query string.
            top_k: Maximum number of results.
            filter_type: Optional filter by target_type (file, symbol, module).

        Returns:
            List of (doc_id, score, metadata) tuples, sorted by relevance.
        """
        if not self._built:
            self.build()

        if not self._docs:
            return []

        # Vectorize query
        query_tokens = _tokenize(query)
        query_tf = Counter(query_tokens)

        # Compute query TF-IDF
        query_vec: dict[str, float] = {}
        for term, count in query_tf.items():
            if term in self._idf:
                query_vec[term] = count * self._idf[term]

        if not query_vec:
            return []

        query_norm = math.sqrt(sum(v * v for v in query_vec.values()))
        if query_norm == 0:
            return []

        # Compute cosine similarity with all docs
        scores: list[tuple[str, float]] = []
        for doc_id, tf in self._tf.items():
            meta = self._metadata.get(doc_id, {})
            if filter_type and meta.get("target_type") != filter_type:
                continue

            doc_norm = self._norms.get(doc_id, 0.0)
            if doc_norm == 0:
                continue

            # Dot product
            dot = 0.0
            for term, q_weight in query_vec.items():
                if term in tf:
                    d_weight = tf[term] * self._idf.get(term, 1.0)
                    dot += q_weight * d_weight

            similarity = dot / (query_norm * doc_norm)
            if similarity > 0:
                scores.append((doc_id, similarity))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return [
            (doc_id, score, self._metadata.get(doc_id, {}))
            for doc_id, score in scores[:top_k]
        ]

    def save(self, path: Path) -> None:
        """Save index to disk."""
        data = {
            "docs": {k: v for k, v in self._docs.items()},
            "metadata": self._metadata,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SemanticIndex:
        """Load index from disk."""
        if not path.exists():
            return cls()

        data = json.loads(path.read_text(encoding="utf-8"))
        index = cls()
        index._docs = {k: v for k, v in data.get("docs", {}).items()}
        index._metadata = data.get("metadata", {})
        index.build()
        return index

    @property
    def document_count(self) -> int:
        """Number of documents in the index."""
        return len(self._docs)


# ─── Index Builder ────────────────────────────────────────────────────

def build_semantic_index(
    summaries: list[Summary],
    files: list[File] | None = None,
    symbols: list[Symbol] | None = None,
) -> SemanticIndex:
    """Build a semantic index from summaries with enriched context.

    Args:
        summaries: All summaries to index.
        files: Optional files for extra context.
        symbols: Optional symbols for extra context.

    Returns:
        Built SemanticIndex ready for search.
    """
    file_map = {f.file_id: f for f in (files or [])}
    symbol_map = {s.symbol_id: s for s in (symbols or [])}

    index = SemanticIndex()

    for summary in summaries:
        # Add extra context based on target type
        extra = ""
        if summary.target_type == "file":
            f = file_map.get(summary.target_id)
            if f:
                extra = f"file:{f.path} lang:{f.language}"
        elif summary.target_type == "symbol":
            s = symbol_map.get(summary.target_id)
            if s:
                extra = f"symbol:{s.name} kind:{s.kind.value}"

        index.add_summary(summary, extra_context=extra)

    index.build()
    return index