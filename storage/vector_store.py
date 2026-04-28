"""FAISS Vector Store — embed chunks và tìm kiếm tương đồng.

Sử dụng OpenAI embeddings để vector hóa tóm tắt code,
lưu vào FAISS index để tìm kiếm nhanh.
"""

import os
import pickle
from dataclasses import dataclass

import numpy as np

try:
    import faiss
except ImportError:
    raise ImportError(
        "faiss-cpu chưa được cài. Chạy: pip install faiss-cpu"
    )

from langchain_openai import OpenAIEmbeddings

from config.settings import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    EMBEDDING_MODEL,
    DEFAULT_TOP_K,
)
from summarizer.llm_summarizer import ChunkSummary


@dataclass
class SearchResult:
    """Kết quả tìm kiếm vector."""

    chunk_id: str
    file_path: str
    name: str
    chunk_type: str
    language: str
    start_line: int
    end_line: int
    summary: str
    purpose: str
    parameters: str
    dependencies: str
    complexity: str
    score: float  # Similarity score (cao = tốt hơn)


class VectorStore:
    """Quản lý FAISS index cho code summaries."""

    def __init__(self, index_dir: str | None = None):
        """Khởi tạo VectorStore.

        Args:
            index_dir: Thư mục chứa FAISS index files.
        """
        self.index_dir = index_dir
        self.index: faiss.IndexFlatIP | None = None
        self.summaries: list[ChunkSummary] = []
        self.embeddings_model = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
        )
        self._embeddings_matrix: np.ndarray | None = None

    def _build_text_for_embedding(self, summary: ChunkSummary) -> str:
        """Tạo text để embed từ ChunkSummary."""
        parts = [
            f"File: {summary.file_path}",
            f"Name: {summary.name}",
            f"Type: {summary.chunk_type}",
            f"Language: {summary.language}",
            f"Summary: {summary.summary}",
            f"Purpose: {summary.purpose}",
        ]
        if summary.parameters and summary.parameters != "N/A":
            parts.append(f"Parameters: {summary.parameters}")
        if summary.dependencies and summary.dependencies != "N/A":
            parts.append(f"Dependencies: {summary.dependencies}")
        return "\n".join(parts)

    def build_index(self, summaries: list[ChunkSummary]) -> None:
        """Tạo FAISS index từ danh sách ChunkSummary.

        Args:
            summaries: Danh sách tóm tắt đã được embed.
        """
        if not summaries:
            print("  ⚠️  Không có summaries để tạo index.")
            return

        print(f"  📊 Embedding {len(summaries)} summaries...")

        self.summaries = summaries
        texts = [self._build_text_for_embedding(s) for s in summaries]

        # Embed tất cả (batch)
        embeddings_list = self.embeddings_model.embed_documents(texts)
        self._embeddings_matrix = np.array(embeddings_list, dtype=np.float32)

        # Normalize để dùng Inner Product như cosine similarity
        faiss.normalize_L2(self._embeddings_matrix)

        # Tạo FAISS index (IndexFlatIP = Inner Product ≈ Cosine similarity khi đã normalize)
        dimension = self._embeddings_matrix.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(self._embeddings_matrix)

        print(f"  ✅ FAISS index đã tạo: {self.index.ntotal} vectors, {dimension} dimensions.")

    def search(self, query: str, top_k: int = 0) -> list[SearchResult]:
        """Tìm kiếm summaries tương đồng với query.

        Args:
            query: Câu truy vấn.
            top_k: Số kết quả trả về (mặc định từ config).

        Returns:
            Danh sách SearchResult sắp xếp theo similarity score.
        """
        if self.index is None or not self.summaries:
            raise RuntimeError(
                "FAISS index chưa được tạo. Chạy pipeline trước."
            )

        if top_k <= 0:
            top_k = DEFAULT_TOP_K

        top_k = min(top_k, len(self.summaries))

        # Embed query
        query_vector = np.array(
            [self.embeddings_model.embed_query(query)],
            dtype=np.float32,
        )
        faiss.normalize_L2(query_vector)

        # Tìm kiếm
        scores, indices = self.index.search(query_vector, top_k)

        results: list[SearchResult] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.summaries):
                continue

            s = self.summaries[idx]
            results.append(SearchResult(
                chunk_id=s.chunk_id,
                file_path=s.file_path,
                name=s.name,
                chunk_type=s.chunk_type,
                language=s.language,
                start_line=s.start_line,
                end_line=s.end_line,
                summary=s.summary,
                purpose=s.purpose,
                parameters=s.parameters,
                dependencies=s.dependencies,
                complexity=s.complexity,
                score=float(score),
            ))

        return results

    def save(self, index_dir: str | None = None) -> str:
        """Lưu FAISS index và metadata xuống đĩa.

        Args:
            index_dir: Thư mục lưu (mặc định dùng self.index_dir).

        Returns:
            Đường dẫn thư mục đã lưu.
        """
        save_dir = index_dir or self.index_dir
        if not save_dir:
            raise ValueError("Chưa chỉ định thư mục lưu index.")

        if self.index is None:
            raise RuntimeError("Chưa có index để lưu.")

        os.makedirs(save_dir, exist_ok=True)

        # Lưu FAISS index
        faiss_path = os.path.join(save_dir, "index.faiss")
        faiss.write_index(self.index, faiss_path)

        # Lưu metadata (summaries + embeddings)
        meta_path = os.path.join(save_dir, "metadata.pkl")
        with open(meta_path, "wb") as f:
            pickle.dump({
                "summaries": self.summaries,
                "embeddings_matrix": self._embeddings_matrix,
            }, f)

        print(f"  💾 FAISS index đã lưu: {save_dir}")
        return save_dir

    def load(self, index_dir: str | None = None) -> bool:
        """Load FAISS index từ đĩa.

        Args:
            index_dir: Thư mục chứa index (mặc định dùng self.index_dir).

        Returns:
            True nếu load thành công, False nếu không tìm thấy.
        """
        load_dir = index_dir or self.index_dir
        if not load_dir:
            raise ValueError("Chưa chỉ định thư mục load index.")

        faiss_path = os.path.join(load_dir, "index.faiss")
        meta_path = os.path.join(load_dir, "metadata.pkl")

        if not os.path.exists(faiss_path) or not os.path.exists(meta_path):
            return False

        # Load FAISS index
        self.index = faiss.read_index(faiss_path)

        # Load metadata
        with open(meta_path, "rb") as f:
            meta = pickle.load(f)

        self.summaries = meta["summaries"]
        self._embeddings_matrix = meta.get("embeddings_matrix")

        print(f"  📂 FAISS index đã load: {self.index.ntotal} vectors từ {load_dir}")
        return True

    @property
    def is_ready(self) -> bool:
        """Kiểm tra index đã sẵn sàng để tìm kiếm."""
        return self.index is not None and len(self.summaries) > 0