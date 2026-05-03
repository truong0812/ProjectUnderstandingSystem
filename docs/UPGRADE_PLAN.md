# 🚀 Kế Hoạch Nâng Cấp: Quality Output & PR Ingest

> **Mục tiêu:** Nâng hệ thống từ "repo summarizer chạy được" lên "knowledge service có thể cập nhật theo PR với đầu ra đủ dùng cho bot/downstream API".

---

## Tổng quan

Trọng tâm gồm 2 nhánh đồng thời:
1. **Chuẩn hóa và đo chất lượng** summary/index/output
2. **Bổ sung API ingest theo PR** — nhận diff của PR làm đầu vào, chỉ cập nhật các file bị ảnh hưởng

Pipeline theo hướng **best effort**: không dừng toàn bộ job vì lỗi cục bộ, nhưng phải gắn cờ chất lượng rõ ràng để downstream biết dữ liệu nào đáng tin.

---

## Giai đoạn 1: Chuẩn hóa ChunkSummary + Quality Validator

### Mở rộng `ChunkSummary` schema

```python
@dataclass
class ChunkSummary:
    # === Existing fields ===
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

    # === NEW: Quality metadata ===
    status: str = "ok"                    # ok | partial | failed
    quality_flags: list[str] = field(default_factory=list)  # Danh sách cờ chất lượng
    source_kind: str = "full_repo"        # full_repo | pr_update
    source_ref: str = ""                  # commit/PR identifier
    updated_at: str = ""                  # ISO timestamp
```

### Quality flags
| Flag | Ý nghĩa |
|------|----------|
| `llm_error` | LLM call thất bại |
| `parse_fallback` | JSON parse lỗi, dùng fallback |
| `truncated_input` | Code bị cắt do quá dài |
| `invalid_json_recovered` | JSON malformed nhưng recover được |

### Tạo `pipeline/quality_validator.py`

```python
def validate_summary(summary: ChunkSummary, chunk: CodeChunk) -> ChunkSummary:
    """Validate và gắn quality flags cho summary."""
    # 1. Kiểm tra summary/purpose không rỗng
    # 2. Kiểm tra line range hợp lệ
    # 3. Kiểm tra kiểu dữ liệu đúng schema
    # 4. Gắn status: ok / partial / failed
```

### Files cần sửa
- `summarizer/llm_summarizer.py` — Mở rộng `ChunkSummary` dataclass
- (MỚI) `pipeline/quality_validator.py` — Module validation

---

## Giai đoạn 2: Sửa Pipeline Foundation

### 2.1 Retry logic cho LLM calls
```python
def summarize_chunk_with_retry(chunk, llm, max_retries=3):
    """Retry với exponential backoff."""
    for attempt in range(max_retries):
        try:
            return summarize_chunk(chunk, llm)
        except Exception as e:
            if attempt == max_retries - 1:
                return failed_summary(chunk, e)
            time.sleep(2 ** attempt)
```

### 2.2 Cải thiện JSON parser
- Thay `string.index()` bằng `string.find()` — tránh crash "substring not found"
- Thêm recovery: regex extract JSON, fix common malformed patterns

### 2.3 Sửa `crew_summarizer.py`
- Dùng đúng `chunk.content` thay vì `chunk.code`
- Dùng đúng `chunk.unique_id` thay vì `chunk.chunk_id`

### 2.4 Pipeline step rõ ràng
```
chunk → summarize → validate → persist → index
```
- Không index chunks có `status=failed`
- Chunks `partial` được index nhưng có metadata để filter

### 2.5 Nâng cấp model
- `.env`: `LLM_MODEL=meta/llama-3.1-70b-instruct`
- `max_tokens`: 500 → 800
- `content limit`: 3000 → 5000

### Files cần sửa
- `summarizer/llm_summarizer.py` — Retry, JSON parser, params
- `summarizer/crew_summarizer.py` — Fix field names
- `pipeline/orchestrator.py` — Thêm validation step
- `.env` — Model upgrade

---

## Giai đoạn 3: Storage Layer Hỗ Trợ Partial Update

### 3.1 Thêm file→chunk mapping
```python
# Trong metadata.pkl
{
    "summaries": [...],
    "embeddings_matrix": [...],
    "file_chunk_map": {         # MỚI
        "src/api/auth.ts": ["auth.ts::LoginRequest::13", "auth.ts::AuthUser::21"],
        "src/api/client.ts": ["client.ts::request::46"],
    },
    "repo_manifest": {          # MỚI
        "repo_path": "...",
        "last_build": "2026-05-03T10:02:08",
        "snapshot_id": "...",
        "total_ok": 100,
        "total_partial": 4,
        "total_failed": 4,
    }
}
```

### 3.2 VectorStore methods mới
```python
def remove_by_file_path(self, file_path: str) -> int:
    """Xóa tất cả chunks thuộc một file."""

def replace_file_chunks(self, file_path: str, new_summaries: list[ChunkSummary]) -> None:
    """Thay thế tất cả chunks của một file."""

def rebuild_from_summaries(self) -> None:
    """Rebuild FAISS từ metadata hiện tại."""
```

### 3.3 Filter trong search
```python
def search(self, query, top_k=5, include_failed=False, include_partial=True):
    """Mặc định bỏ qua failed chunks."""
```

### Files cần sửa
- `storage/vector_store.py` — File mapping, partial update, filter
- `storage/json_store.py` — Quality metadata trong JSON output
- `storage/markdown_store.py` — Quality info trong Markdown

---

## Giai đoạn 4: PR Ingest API

### 4.1 Diff Parser (MỚI: `pipeline/diff_parser.py`)

```python
@dataclass
class DiffFileChange:
    file_path: str
    change_type: str  # added | modified | deleted | renamed
    old_path: str | None = None  # Cho renamed
    hunks: list[tuple[int, int]] = field(default_factory=list)  # (start, length)

def parse_unified_diff(diff_text: str) -> list[DiffFileChange]:
    """Parse unified diff/patch text."""
```

### 4.2 PR Ingestor (MỚI: `pipeline/pr_ingestor.py`)

```python
def ingest_pr(
    repo_path: str,
    diff: str,
    pr_id: str,
    mode: str = "fast",
    output_dir: str | None = None,
) -> PRIngestResult:
    """
    1. Parse diff → danh sách file changed
    2. Load existing metadata
    3. Với mỗi file:
       - added/modified: parse → chunk → summarize → validate
       - deleted: xóa khỏi metadata
       - renamed: cập nhật đường dẫn
    4. Rebuild FAISS index
    5. Lưu metadata mới
    """
```

### 4.3 API Endpoint (sửa: `api/server.py`)

```
POST /ingest/pr
```

**Request body:**
```json
{
    "repo_path": "D:\\Projects\\MyApp",
    "pr_id": "42",
    "diff": "diff --git a/src/auth.ts b/src/auth.ts\n...",
    "mode": "fast",
    "output_dir": null
}
```

**Response:**
```json
{
    "status": "success",
    "pr_id": "42",
    "changed_files": 3,
    "processed_files": 2,
    "deleted_files": 1,
    "chunks_added": 5,
    "chunks_updated": 8,
    "chunks_deleted": 3,
    "ok_chunks": 12,
    "partial_chunks": 1,
    "failed_chunks": 0,
    "errors": [],
    "index_reloaded": true
}
```

### 4.4 Điều chỉnh `GET /context`
- Mặc định lọc bỏ `status=failed` chunks
- Query params: `include_partial=true`, `include_failed=false`

### Files cần tạo
- (MỚI) `pipeline/diff_parser.py`
- (MỚI) `pipeline/pr_ingestor.py`

### Files cần sửa
- `api/server.py` — Thêm `POST /ingest/pr`, điều chỉnh `GET /context`

---

## API Reference (Sau nâng cấp)

### Existing endpoints (giữ nguyên)
| Method | Path | Mô tả |
|--------|------|--------|
| `GET` | `/health` | Kiểm tra trạng thái |
| `GET` | `/context` | Tìm kiếm code summaries |
| `POST` | `/ingest` | Chạy pipeline cho repo |

### New endpoints
| Method | Path | Mô tả |
|--------|------|--------|
| `POST` | `/ingest/pr` | Cập nhật knowledge theo PR diff |

---

## Thứ tự implement

```
1. Giai đoạn 1 → ChunkSummary schema + Quality Validator (nền tảng)
2. Giai đoạn 2 → Sửa pipeline: retry, JSON parser, crew fix, model upgrade
3. Giai đoạn 3 → Storage layer: file mapping, partial update, search filter
4. Giai đoạn 4 → PR Ingest: diff parser, ingestor, API endpoint
```

---

## Test Plan

### Unit Tests
- [ ] Diff parser: modified/added/deleted/renamed/multi-hunk
- [ ] Quality validator: valid chunk, invalid JSON, LLM error, wrong field type
- [ ] PR ingestor: chỉ file đổi bị reprocess, deleted bị gỡ, chunk lỗi không fail request
- [ ] JSON recovery parser: malformed JSON, code blocks, partial JSON

### API Tests
- [ ] `POST /ingest/pr` với diff hợp lệ
- [ ] Diff không parse được
- [ ] File trong diff không tồn tại
- [ ] `GET /context` không trả failed chunks

### Smoke Tests E2E
- [ ] Full ingest repo mẫu
- [ ] PR ingest: 1 file sửa + 1 file xóa
- [ ] Search phản ánh bản mới sau PR update

---

## Assumptions

- Client gửi raw unified diff/patch vào API, server không gọi GitHub/GitLab.
- Vòng này cập nhật theo file, chưa tối ưu đến mức hunk.
- Best effort: không fail toàn job vì lỗi cục bộ, dữ liệu degraded phải có cờ.
- Chưa thêm auth, queue, hay background job system.