"""Pipeline điều phối — parse → chunk → summarize → store.

Đây là module trung tâm, kết nối tất cả các module lại:
1. Parser: Đọc file code từ repo
2. Chunker: Chia code thành chunks
3. Summarizer: Tóm tắt từng chunk bằng LLM (fast) hoặc multi-agent crew (deep)
4. Storage: Lưu kết quả (Markdown, JSON, FAISS)

Modes:
- fast: 1 LLM call/chunk — nhanh, rẻ, đủ dùng
- deep: 3 agents + 1 synthesis/chunk — chậm hơn nhưng phân tích toàn diện
"""

import os
from dataclasses import dataclass

from config.settings import (
    OUTPUT_DIR,
    FAISS_INDEX_PATH,
    SUMMARIES_MD_PATH,
    SUMMARIES_JSON_PATH,
)
from parser.repo_parser import parse_repo, get_repo_stats
from chunker.code_chunker import chunk_all
from summarizer.llm_summarizer import summarize_all, ChunkSummary
from storage.markdown_store import save_summaries_md
from storage.json_store import save_summaries_json
from storage.vector_store import VectorStore


@dataclass
class PipelineResult:
    """Kết quả chạy pipeline."""

    repo_path: str
    total_files: int
    total_chunks: int
    total_summaries: int
    stats: dict
    summaries: list[ChunkSummary]
    output_dir: str
    md_path: str
    json_path: str
    faiss_path: str
    mode: str  # "fast" hoặc "deep"


def run_pipeline(
    repo_path: str,
    output_dir: str | None = None,
    mode: str = "fast",
) -> PipelineResult:
    """Chạy toàn bộ pipeline: parse → chunk → summarize → store.

    Args:
        repo_path: Đường dẫn đến thư mục repo cần phân tích.
        output_dir: Thư mục output (mặc định từ config).
        mode: Chế độ tóm tắt — "fast" (1 LLM/chunk) hoặc "deep" (multi-agent crew).

    Returns:
        PipelineResult với thông tin kết quả.
    """
    if mode not in ("fast", "deep"):
        raise ValueError(f"Mode không hợp lệ: {mode}. Dùng 'fast' hoặc 'deep'.")

    repo_path = os.path.abspath(repo_path)
    out_dir = output_dir or OUTPUT_DIR

    mode_label = "⚡ Fast" if mode == "fast" else "🤖 Deep (Multi-Agent Crew)"

    print("=" * 60)
    print("  🧠 Repo Knowledge System — Pipeline")
    print("=" * 60)
    print(f"  📂 Repo: {repo_path}")
    print(f"  📁 Output: {out_dir}")
    print(f"  🔧 Mode: {mode_label}")
    print()

    # ─── Bước 1: Parse repo ─────────────────────────────────────
    print("📥 Bước 1/5: Parse repo...")
    code_files = parse_repo(repo_path)
    stats = get_repo_stats(code_files)

    print(f"  ✅ Tìm thấy {stats['total_files']} file code ({stats['total_lines']} dòng)")
    lang_list = ", ".join(f"{lang}: {count}" for lang, count in sorted(stats["languages"].items()))
    print(f"  📊 Ngôn ngữ: {lang_list}")
    print()

    if not code_files:
        raise ValueError(f"Không tìm thấy file code nào trong: {repo_path}")

    # ─── Bước 2: Chunk code ─────────────────────────────────────
    print("✂️  Bước 2/5: Chia code thành chunks...")
    chunks = chunk_all(code_files)
    print(f"  ✅ Đã tạo {len(chunks)} chunks")
    print()

    # ─── Bước 3: Tóm tắt ────────────────────────────────────────
    if mode == "deep":
        print("🤖 Bước 3/5: Tóm tắt chunks bằng Multi-Agent Crew...")
        from summarizer.crew_summarizer import crew_summarize_all
        summaries = crew_summarize_all(chunks)
    else:
        print("🤖 Bước 3/5: Tóm tắt chunks bằng LLM (fast mode)...")
        summaries = summarize_all(chunks)
    print()

    # ─── Bước 4: Lưu Markdown & JSON ────────────────────────────
    print("💾 Bước 4/5: Lưu kết quả (Markdown + JSON)...")

    os.makedirs(out_dir, exist_ok=True)

    md_path = os.path.join(out_dir, "summaries.md")
    json_path = os.path.join(out_dir, "summaries.json")
    faiss_path = os.path.join(out_dir, "faiss_index")

    save_summaries_md(summaries, md_path, repo_path)
    print(f"  📄 Markdown: {md_path}")

    save_summaries_json(summaries, json_path, repo_path)
    print(f"  📋 JSON: {json_path}")
    print()

    # ─── Bước 5: Tạo FAISS index ────────────────────────────────
    print("🔍 Bước 5/5: Tạo FAISS vector index...")

    vector_store = VectorStore(index_dir=faiss_path)
    vector_store.build_index(summaries)
    vector_store.save(faiss_path)
    print()

    # ─── Kết quả ────────────────────────────────────────────────
    result = PipelineResult(
        repo_path=repo_path,
        total_files=stats["total_files"],
        total_chunks=len(chunks),
        total_summaries=len(summaries),
        stats=stats,
        summaries=summaries,
        output_dir=out_dir,
        md_path=md_path,
        json_path=json_path,
        faiss_path=faiss_path,
        mode=mode,
    )

    print("=" * 60)
    print("  ✅ Pipeline hoàn tất!")
    print("=" * 60)
    print(f"  📊 {result.total_files} files → {result.total_chunks} chunks → {result.total_summaries} summaries")
    print(f"  📄 Markdown: {md_path}")
    print(f"  📋 JSON:     {json_path}")
    print(f"  🔍 FAISS:    {faiss_path}")
    print()

    return result