"""FastAPI Server — cung cấp API để truy vấn code intelligence.

Endpoints:
- GET  /context?query=...&top_k=5  → Tìm kiếm code summaries liên quan
- POST /ingest                      → Chạy pipeline cho repo mới
- GET  /health                      → Kiểm tra trạng thái
"""

import sys
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from functools import partial
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import (
    FAISS_INDEX_PATH,
    DEFAULT_TOP_K,
    API_HOST,
    API_PORT,
)
from storage.vector_store import VectorStore, SearchResult
from pipeline.orchestrator import run_pipeline


# ─── FastAPI App ────────────────────────────────────────────────────

app = FastAPI(
    title="Repo Knowledge System API",
    description=(
        "API để truy vấn code knowledge base. "
        "Sử dụng FAISS vector search để tìm code summaries liên quan."
    ),
    version="1.0.0",
)

# CORS — cho phép bot khác truy vấn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global State ───────────────────────────────────────────────────

vector_store = VectorStore(index_dir=FAISS_INDEX_PATH)
_thread_pool = ThreadPoolExecutor(max_workers=2)


@app.on_event("startup")
async def startup():
    """Load FAISS index khi khởi động API."""
    loaded = vector_store.load()
    if loaded:
        print(f"✅ FAISS index đã load: {FAISS_INDEX_PATH}")
    else:
        print(f"⚠️  Chưa có FAISS index tại: {FAISS_INDEX_PATH}")
        print("   Chạy pipeline trước: python main.py /path/to/repo")


# ─── Models ─────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Request body cho POST /ingest."""
    repo_path: str
    output_dir: str | None = None
    mode: str = "fast"  # "fast" hoặc "deep"


class IngestResponse(BaseModel):
    """Response cho POST /ingest."""
    status: str
    total_files: int
    total_chunks: int
    total_summaries: int
    output_dir: str
    md_path: str
    json_path: str
    faiss_path: str


class ContextResponse(BaseModel):
    """Response cho GET /context."""
    query: str
    top_k: int
    total_results: int
    results: list[dict]


class HealthResponse(BaseModel):
    """Response cho GET /health."""
    status: str
    index_loaded: bool
    total_vectors: int


# ─── Endpoints ──────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    """Kiểm tra trạng thái API và FAISS index."""
    return HealthResponse(
        status="ok" if vector_store.is_ready else "no_index",
        index_loaded=vector_store.is_ready,
        total_vectors=vector_store.index.ntotal if vector_store.index else 0,
    )


@app.get("/context", response_model=ContextResponse, tags=["Search"])
async def context(
    query: str = Query(..., description="Câu truy vấn về code"),
    top_k: int = Query(DEFAULT_TOP_K, ge=1, le=50, description="Số kết quả trả về"),
):
    """Tìm kiếm code summaries liên quan đến query.

    Sử dụng FAISS vector similarity search để tìm các đoạn code
    có nội dung liên quan nhất đến câu truy vấn.

    **Ví dụ:**
    - `?query=how does authentication work`
    - `?query=database connection&top_k=3`
    """
    if not vector_store.is_ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "FAISS index chưa sẵn sàng. "
                "Chạy pipeline trước: POST /ingest hoặc python main.py /path/to/repo"
            ),
        )

    try:
        results = vector_store.search(query, top_k=top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tìm kiếm: {str(e)}")

    return ContextResponse(
        query=query,
        top_k=top_k,
        total_results=len(results),
        results=[asdict(r) for r in results],
    )


@app.post("/ingest", response_model=IngestResponse, tags=["Pipeline"])
async def ingest(request: IngestRequest):
    """Chạy pipeline cho một thư mục repo.

    Pipeline sẽ: parse repo → chunk code → tóm tắt bằng LLM → lưu FAISS index.

    Sau khi hoàn tất, API tự động load index mới.
    """
    if not os.path.isdir(request.repo_path):
        raise HTTPException(
            status_code=400,
            detail=f"Thư mục không tồn tại: {request.repo_path}",
        )

    # Validate mode
    if request.mode not in ("fast", "deep"):
        raise HTTPException(
            status_code=400,
            detail=f"Mode không hợp lệ: {request.mode}. Dùng 'fast' hoặc 'deep'.",
        )

    # Chạy pipeline trong thread pool để không block event loop
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _thread_pool,
            partial(
                run_pipeline,
                repo_path=request.repo_path,
                output_dir=request.output_dir,
                mode=request.mode,
            ),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi pipeline: {str(e)}")

    # Reload FAISS index
    vector_store.load()

    return IngestResponse(
        status="success",
        total_files=result.total_files,
        total_chunks=result.total_chunks,
        total_summaries=result.total_summaries,
        output_dir=result.output_dir,
        md_path=result.md_path,
        json_path=result.json_path,
        faiss_path=result.faiss_path,
    )


# ─── Chạy trực tiếp ────────────────────────────────────────────────

def start_server():
    """Khởi động FastAPI server với uvicorn."""
    import uvicorn
    uvicorn.run(
        "api.server:app",
        host=API_HOST,
        port=API_PORT,
        reload=False,
    )


if __name__ == "__main__":
    start_server()