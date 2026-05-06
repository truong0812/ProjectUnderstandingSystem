# Improvement Plan — Project Understanding System

> Ngày tạo: 2026-05-06
> Phiên bản: v0.1.0
> Trạng thái: Draft

---

## 1. Tổng quan

Dự án có kiến trúc tốt, module hóa rõ ràng. Sau khi phân tích toàn bộ codebase (33+ source files, 3 test files), đã xác định **23 vấn đề** được phân loại theo 4 mức ưu tiên.

---

## 2. Plan theo Phase

### Phase 1 — Critical Fixes (1-2 ngày)

| # | Vấn đề | File(s) | Hành động | Status |
|---|--------|---------|-----------|--------|
| 1.1 | **Hardcoded business domain (Logistics/Cargo)** | `ingest/business_glossary.py`, `ingest/summarizer.py`, `models/summaries.py` | Tách `business_glossary.py` thành plugin/domain profile. Bỏ `business_context` field khỏi `Summary` model (hoặc làm generic `metadata: dict`). Bỏ sentence logistics tiếng Việt khỏi `SYSTEM_PROMPT`. | ⬜ |
| 1.2 | **Silent exception swallowing** | `pipeline.py`, `storage/snapshot_storage.py` | Thay `except Exception: pass` bằng `logging.warning()` hoặc `logging.error()`. Raise exception ở những chỗ cần fail-fast. | ⬜ |
| 1.3 | **LLM error handling trả string** | `adapters/llm_openai_compatible.py`, `ingest/summarizer.py` | Tạo custom `LLMError` exception. `generate()` raise exception thay vì return error string. Caller dùng try/except thay vì `startswith("[LLM Error:")`. | ⬜ |

### Phase 2 — High Priority (2-3 ngày)

| # | Vấn đề | File(s) | Hành động | Status |
|---|--------|---------|-----------|--------|
| 2.1 | **Test coverage cực thấp (31 tests, 0% cho 10+ modules)** | `tests/` | Viết unit tests cho: `RetrievalEngine`, `SemanticIndex`, `SnapshotStorage`, `RelationBuilder`, `ConventionDetector`, `RiskDetector`, `EntityExtractor`, `Scanner`, `business_glossary`, Parsers. Thêm integration test cho `Pipeline`. Target: 80%+ coverage. | ⬜ |
| 2.2 | **O(n) linear scans trong RetrievalEngine** | `retrieval/engine.py` | Pre-build `file_id → [symbols]`, `file_id → [relations]` index trong `__init__`. Refactor các query methods dùng index. | ⬜ |
| 2.3 | **CLI dùng argparse thay vì Click** | `cli/main.py`, `pyproject.toml` | Chọn 1 approach: (a) migrate sang Click, hoặc (b) bỏ Click khỏi dependencies. Khuyến nghị: migrate sang Click để code ngắn hơn và feature-rich hơn. | ⬜ |
| 2.4 | **Snapshot collision — Cùng ngày ghi đè** | `storage/snapshot_storage.py` | Thêm timestamp vào snapshot directory: `YYYY-MM-DD/HHMMSS` hoặc `YYYY-MM-DD_HHMMSS`. Thêm warning khi snapshot đã tồn tại. | ⬜ |

### Phase 3 — Medium Priority (3-5 ngày)

| # | Vấn đề | File(s) | Hành động | Status |
|---|--------|---------|-----------|--------|
| 3.1 | **Unused import `ParsedFile`** | `ingest/summarizer.py` | Xóa unused import. | ⬜ |
| 3.2 | **Inline `import re` trong function** | `ingest/relation_builder.py` | Move `import re` lên top-level. | ⬜ |
| 3.3 | **Hardcoded version string** | `cli/main.py` | Đọc version từ `importlib.metadata.version("project_understanding")` hoặc `pyproject.toml`. | ⬜ |
| 3.4 | **SemanticIndex save/load không persist TF-IDF** | `retrieval/semantic_index.py` | Persist vectorizer vocabulary + IDF weights trong `save()`. `load()` trả về ready-to-use index. | ⬜ |
| 3.5 | **requirements.txt trùng pyproject.toml** | `requirements.txt`, `pyproject.toml` | Xóa `requirements.txt`, giữ `pyproject.toml` là nguồn duy nhất. Hoặc generate `requirements.txt` từ `pyproject.toml`. | ⬜ |
| 3.6 | **Config: OPENAI_BASE_URL bị ignore** | `config.py` | Đọc `OPENAI_BASE_URL` từ env variable, cho phép user override preset URL. | ⬜ |
| 3.7 | **`models/__init__.py` không export** | `models/__init__.py` | Thêm re-exports cho các model chính: `File`, `Symbol`, `Relation`, `Summary`, `GlossaryTerm`, `Convention`, `RiskArea`, `Snapshot`. | ⬜ |
| 3.8 | **Project structure không sạch** | Root directory | Xóa thư mục `-p/`, empty `profiles/`. Thêm `.gitkeep` cho `tests/fixtures/`. | ⬜ |
| 3.9 | **Không có logging framework** | Toàn project | Thay `print(..., file=sys.stderr)` bằng `logging.getLogger(__name__)`. Configure logging levels. | ⬜ |
| 3.10 | **Thiếu documentation** | `docs/` | Tạo `docs/ARCHITECTURE.md` và `docs/AGENT_PROFILES.md`. | ⬜ |
| 3.11 | **Không có CI/CD pipeline** | `.github/workflows/` | Tạo GitHub Actions workflow: `ruff check`, `pytest`, `mypy`. | ⬜ |

### Phase 4 — Low Priority (1-2 ngày)

| # | Vấn đề | File(s) | Hành động | Status |
|---|--------|---------|-----------|--------|
| 4.1 | **Parser lazy import pattern** | `ingest/pipeline.py` | Tạo `ParserRegistry` class với dict-based factory. | ⬜ |
| 4.2 | **Snapshot metadata thiếu glossary stats** | `storage/snapshot_storage.py` | Thêm convention/risk/glossary counts vào `metadata.json`. | ⬜ |
| 4.3 | **ProfileRegistry không load YAML** | `profiles/registry.py` | Thêm `register_from_yaml()` method. Support custom profiles từ file. | ⬜ |
| 4.4 | **Thiếu pre-commit hooks** | Root | Tạo `.pre-commit-config.yaml` với ruff, black, mypy. | ⬜ |
| 4.5 | **`RelationType.USES` không được filter** | `profiles/models.py` | Thêm "uses" vào default preferred_relations cho các profiles cần. | ⬜ |

---

## 3. Chi tiết kỹ thuật

### 3.1 Tách Business Glossary thành Plugin

**Hiện tại:**
```
summarizer.py → imports business_glossary.detect_business_context()
models/summaries.py → Summary.business_context field
```

**Mục tiêu:**
```
plugins/domain_glossary/
    ├── __init__.py
    ├── base.py          # DomainGlossaryPlugin interface
    └── logistics_vi.py  # Logistics glossary (current code)

summarizer.py → gọi plugin registry (optional)
models/summaries.py → Summary.metadata: dict[str, str] (generic)
```

### 3.2 Error Handling Pattern

**Hiện tại:**
```python
except Exception as e:
    return f"[LLM Error: {e}]"  # String error
```

**Mục tiêu:**
```python
class LLMError(Exception):
    """Error from LLM provider."""
    pass

# In generate():
except Exception as e:
    raise LLMError(f"Failed to generate: {e}") from e

# In caller:
try:
    result = llm.generate(prompt=prompt, system=system)
except LLMError:
    result = _generate_heuristic_summary(file, content, symbols)
```

### 3.3 RetrievalEngine Index

**Hiện tại:** O(n) scan mỗi query
```python
for sym in self._package.symbols:  # Quét ALL symbols
    if sym.file_id == file_id:
        ...
```

**Mục tiêu:** Pre-built index O(1) lookup
```python
def __init__(self, package):
    self._package = package
    self._symbols_by_file: dict[str, list[Symbol]] = defaultdict(list)
    self._relations_by_source: dict[str, list[Relation]] = defaultdict(list)
    self._relations_by_target: dict[str, list[Relation]] = defaultdict(list)
    
    for sym in package.symbols:
        self._symbols_by_file[sym.file_id].append(sym)
    for rel in package.relations:
        self._relations_by_source[rel.source_id].append(rel)
        self._relations_by_target[rel.target_id].append(rel)
```

### 3.4 Snapshot Directory Structure

**Hiện tại:** `snapshots/YYYY-MM-DD/snapshot.jsonl`
**Mục tiêu:** `snapshots/YYYY-MM-DD/HHMMSS/snapshot.jsonl`

Hoặc: `snapshots/YYYY-MM-DD_HHMMSS/snapshot.jsonl`

---

## 4. Test Coverage Plan

### Unit Tests cần tạo:

| File | Priority | Key Test Cases |
|------|----------|----------------|
| `tests/unit/test_retrieval_engine.py` | 🔴 | 5 query primitives, empty package, large package |
| `tests/unit/test_semantic_index.py` | 🔴 | build, search, save/load, empty index |
| `tests/unit/test_snapshot_storage.py` | 🔴 | write, read, list, delete, corrupt file |
| `tests/unit/test_relation_builder.py` | 🟠 | 5 relation types, cross-file, no symbols |
| `tests/unit/test_convention_detector.py` | 🟠 | naming, docstring, type hints detection |
| `tests/unit/test_risk_detector.py` | 🟠 | all risk categories, severity levels |
| `tests/unit/test_entity_extractor.py` | 🟠 | extract from parsed files |
| `tests/unit/test_scanner.py` | 🟠 | scan directory, filter extensions |
| `tests/unit/test_business_glossary.py` | 🟡 | detect terms, max_terms, empty content |
| `tests/unit/test_parsers.py` | 🟠 | Python/TypeScript/C# parsing |

### Integration Tests cần tạo:

| File | Priority | Key Test Cases |
|------|----------|----------------|
| `tests/integration/test_pipeline.py` | 🔴 | Full ingest flow, incremental update |
| `tests/integration/test_cli.py` | 🟠 | CLI commands end-to-end |

---

## 5. Thứ tự thực hiện

```
Week 1:
  Day 1-2: Phase 1 (Critical fixes)
    ├── 1.1 Tách business glossary
    ├── 1.2 Fix silent errors  
    └── 1.3 Fix LLM error handling

  Day 3-5: Phase 2 (High priority)
    ├── 2.1 Viết tests (part 1)
    ├── 2.2 Fix RetrievalEngine index
    ├── 2.3 Resolve CLI framework
    └── 2.4 Fix snapshot collision

Week 2:
  Day 1-3: Phase 2 continued
    └── 2.1 Viết tests (part 2) — target 80%+ coverage

  Day 3-5: Phase 3 (Medium priority)
    ├── 3.1-3.3 Cleanup (imports, version, etc.)
    ├── 3.4 SemanticIndex persistence
    ├── 3.5-3.6 Config cleanup
    ├── 3.7-3.8 Structure cleanup
    ├── 3.9 Logging framework
    ├── 3.10-3.11 Docs + CI/CD

Week 3:
  Day 1-2: Phase 4 (Low priority)
    ├── 4.1-4.5 Small improvements

  Day 3-5: Final review + regression testing
```

---

## 6. Metrics mục tiêu

| Metric | Hiện tại | Mục tiêu |
|--------|----------|----------|
| Test coverage | ~15% (3 files) | 80%+ |
| Unit tests | 31 | 150+ |
| Integration tests | 0 | 10+ |
| Silent exceptions | 5+ | 0 |
| Domain-specific hardcoded | 85+ terms | 0 (moved to plugin) |
| O(n) queries | 4 methods | 0 (all indexed) |
| CI/CD pipelines | 0 | 1 (GitHub Actions) |

---

## 7. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tách business_glossary có thể break existing summaries | Medium | Migration script cho old snapshots |
| Thay error handling có thể break callers | Low | Tìm tất cả callers qua search |
| Thêm index tăng memory usage | Low | Index size ~2x package size, acceptable |
| Migrate CLI sang Click | Medium | Giữ argparse fallback trong transition |