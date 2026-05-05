# MVP Specification: Shared Knowledge Base for AI Agents

## 1. Mục tiêu

MVP này nhằm tạo ra một `Project Understanding Agent` có khả năng chuyển một codebase thành một `knowledge base dùng chung` để nhiều AI agent khác nhau có thể sử dụng mà không cần đọc lại toàn bộ source code mỗi lần làm việc.

Knowledge base được thiết kế theo hướng:

- Dùng chung cho nhiều agent
- Có cấu trúc, có thể truy vấn
- Có version theo snapshot của repo
- Có thể materialize thành file để các agent khác đọc như một `shared memory`

Agent đầu tiên dùng để kiểm chứng giá trị là `Review Agent`, nhưng mô hình dữ liệu và retrieval không được phụ thuộc riêng vào agent này.

---

## 2. Vấn đề cần giải quyết

Trong workflow AI hiện tại, mỗi agent thường phải:

- đọc lại nhiều file từ repo
- tự suy luận lại kiến trúc
- thiếu shared context với agent khác
- tiêu tốn token và thời gian lặp lại
- dễ đưa ra kết luận không nhất quán

MVP này giải quyết bằng cách tạo ra một tầng knowledge trung gian:

`Codebase -> Structured Knowledge Base -> AI Agents`

Thay vì mỗi agent đọc source code từ đầu, các agent sẽ đọc knowledge đã được chuẩn hóa và chỉ quay lại source code khi thật sự cần xác minh.

---

## 3. Product Vision

Sản phẩm được định nghĩa là hai lớp:

### 3.1. Knowledge Producer

Một agent hoặc pipeline có nhiệm vụ:

- ingest codebase
- parse cấu trúc code
- trích xuất entity và relation
- tóm tắt file, module, symbol
- phát hiện convention và vùng rủi ro
- build semantic index
- xuất ra shared knowledge package

### 3.2. Knowledge Consumers

Các agent khác như:

- Review Agent
- Dev Agent
- Doc Agent

sử dụng cùng một knowledge base thông qua `agent profile config`, thay vì mỗi agent có một pipeline hiểu repo riêng.

---

## 4. Phạm vi MVP

MVP được chia thành **3 phase** rõ ràng. Mỗi phase đều deliver giá trị độc lập.

### Phase 1: Codebase Ingest + Structured Snapshot

> Mục tiêu: Biến codebase thành structured knowledge file

Bao gồm:

- Scan repo tree, detect ngôn ngữ từng file
- Parse file thành entities bằng tree-sitter
- Build entity model: `Repository`, `Snapshot`, `File`, `Module`, `Symbol`
- Build relation model: `imports`, `calls`, `contains`, `depends_on`
- Generate **file-level summary** bằng LLM
- Xuất ra knowledge snapshot có schema validate được

Output artifacts:

- `snapshot.json`
- `entities.jsonl`
- `relations.jsonl`
- `summaries.jsonl`

### Phase 2: Agent Profile + Structured Retrieval

> Mục tiêu: Để AI agent khác query knowledge qua profile

Bao gồm:

- Agent profile config (YAML)
- 3 profile khởi tạo: `review-agent`, `dev-agent`, `doc-agent`
- Structured retrieval primitives:
  - `file_context(path, profile)`
  - `symbol_context(symbol_ref, profile)`
  - `module_context(module_id, profile)`
  - `change_context(changed_files, profile)`
- Materialize kết quả thành **context bundle** (JSON) để agent khác đọc

### Phase 3: Semantic Search + Enrichment

> Mục tiêu: Semantic retrieval + convention/risk detection

Bao gồm:

- Build vector index cho summaries
- `semantic_context(query, profile)` primitive
- Convention detection (naming, pattern, structure)
- Risk area detection (auth, DB write, external API...)
- Symbol-level + module-level summary

### Ngoài phạm vi MVP

| Feature | Quyết định | Lý do |
|---|---|---|
| Dashboard UI | Sau MVP | Không cần cho validate |
| Auto sync file change | Sau MVP | Ingest thủ công đủ |
| Multi-repo orchestration | Sau MVP | Tập trung 1 repo trước |
| Auth và multi-tenant | Sau MVP | Không cần |
| PR comment automation | Sau MVP | Không critical |
| Live API service bắt buộc | Sau MVP | File-based đủ cho MVP |

---

## 5. Kết quả đầu ra của MVP

Sau mỗi lần ingest, hệ thống phải tạo ra một `knowledge snapshot` gồm các artifact chính:

- `snapshot.json`
- `entities.jsonl`
- `relations.jsonl`
- `summaries.jsonl`
- `conventions.jsonl` (Phase 3)
- `risks.jsonl` (Phase 3)
- `indexes/` (Phase 3)
- `profiles/` (Phase 2)

Các file này đóng vai trò như `shared memory files` để agent khác đọc trực tiếp.

---

## 6. Shared Knowledge Model

Knowledge base của MVP dùng một schema chung cho tất cả agent.

### 6.1. Entity chính

| Entity | Mô tả | Phase |
|---|---|---|
| `Repository` | Thông tin định danh của repo nguồn | 1 |
| `Snapshot` | Trạng thái repo tại một thời điểm ingest | 1 |
| `File` | Mô tả file code: path, language, hash, size | 1 |
| `Module` | Đơn vị logic ở mức nhóm file hoặc namespace | 1 |
| `Symbol` | Function, class, method, interface, type, constant | 1 |
| `Relation` | Quan hệ giữa các entity | 1 |
| `Summary` | Mô tả ngắn gọn cho file, module hoặc symbol | 1 (file-level), 3 (symbol, module) |
| `Convention` | Quy ước hoặc pattern đang được repo áp dụng | 3 |
| `RiskArea` | Vùng nhạy cảm cần lưu ý khi review hoặc phát triển | 3 |

### 6.2. Chi tiết entity

#### Repository

Thông tin định danh của repo nguồn.

Fields tối thiểu:

- `repo_id`
- `url`
- `branch`
- `commit_sha`
- `ingested_at`

#### Snapshot

Đại diện cho trạng thái repo tại một thời điểm ingest.

Fields tối thiểu:

- `snapshot_id`
- `repo_id`
- `branch`
- `commit_sha`
- `created_at`
- `status`

#### File

Mô tả file code.

Fields tối thiểu:

- `file_id`
- `snapshot_id`
- `path`
- `language`
- `hash`
- `size`
- `is_entrypoint`

#### Module

Đơn vị logic ở mức nhóm file hoặc namespace.

Fields tối thiểu:

- `module_id`
- `snapshot_id`
- `name`
- `path_pattern`
- `files`

#### Symbol

Đại diện cho function, class, method, interface, type, constant hoặc entrypoint quan trọng.

Fields tối thiểu:

- `symbol_id`
- `file_id`
- `name`
- `kind` (function, class, method, interface, type, constant)
- `path` (qualified name)
- `line_start`
- `line_end`
- `hash`

#### Relation

Quan hệ giữa các entity.

Fields tối thiểu:

- `source_id`
- `target_id`
- `relation_type`
- `confidence`
- `evidence`

#### Summary

Mô tả ngắn gọn cho file, module hoặc symbol.

Fields tối thiểu:

- `summary_id`
- `target_id` (reference đến entity)
- `target_type` (file, module, symbol)
- `content`
- `level` (file, symbol, module)
- `generated_by` (heuristic, llm)

---

## 7. ID và Versioning

MVP phải tránh dùng line number làm identity chính.

### 7.1. Snapshot identity

`snapshot_id = repo_id + branch + commit_sha`

### 7.2. File identity

`file_id = repo_id + normalized_path + file_hash`

### 7.3. Symbol identity

`symbol_id = repo_id + file_path + symbol_path + symbol_hash`

Nguyên tắc:

- line span chỉ dùng để trace
- hash nội dung dùng để giữ identity ổn định hơn
- mỗi snapshot là immutable

---

## 8. Ingest Flow

Luồng ingest của MVP:

### 8.1. Phase 1 Flow

1. Đọc metadata của repo và commit hiện tại
2. Quét cây thư mục theo rules bỏ qua
3. Detect ngôn ngữ từng file
4. Parse file thành entities (File, Module, Symbol)
5. Xây relations cấu trúc (contains, imports, calls, depends_on)
6. Sinh file-level summary bằng LLM
7. Ghi toàn bộ knowledge snapshot ra thư mục tạm
8. Atomic rename sang snapshot active

### 8.2. Parser strategy

MVP theo hướng multi-language generic:

- `tree-sitter` là parser abstraction chính
- mỗi ngôn ngữ được enable theo capability
- file không parse sâu được vẫn phải được lưu ở mức `File` entity

### 8.3. Summary strategy

Phase 1: file-level summary bằng LLM

Phase 3: bổ sung symbol-level và module-level summary

Summary phải được giữ riêng dưới dạng structured record, không chôn toàn bộ vào một markdown blob.

---

## 9. Relation Model

MVP hỗ trợ các relation type theo phase:

### Phase 1 (tối thiểu)

| Relation | Mô tả |
|---|---|
| `contains` | File chứa symbol, module chứa file |
| `imports` | Symbol/file import symbol/file khác |
| `calls` | Symbol gọi symbol khác |
| `depends_on` | Phụ thuộc giữa file/module |

### Phase 3 (bổ sung)

| Relation | Mô tả |
|---|---|
| `inherits` | Class kế thừa class khác |
| `implements` | Class implement interface |
| `entrypoint_to` | File là entrypoint đến module |
| `related_to` | Quan hệ liên quan khác |

Mỗi relation phải có:

- `source_id`
- `target_id`
- `relation_type`
- `confidence`
- `evidence`

---

## 10. Convention và Risk Detection (Phase 3)

### 10.1. Convention

Ví dụ:

- cấu trúc module
- naming pattern
- dependency direction
- service/repository/controller pattern
- cách xử lý error
- cách tổ chức config

### 10.2. RiskArea

Ví dụ:

- authentication
- authorization
- database write
- transaction
- cache
- queue
- file system write
- external API call
- migration
- config/secrets

MVP ưu tiên heuristic deterministic, sau đó bổ sung LLM enrichment.

---

## 11. Retrieval Model

### 11.1. Phase 2: Structured retrieval

Truy vấn theo:

- file path
- symbol
- module
- relation
- changed files

Query primitives:

- `file_context(path, profile)` — lấy context xung quanh một file
- `symbol_context(symbol_ref, profile)` — lấy context xung quanh một symbol
- `module_context(module_id, profile)` — lấy context cho một module
- `change_context(changed_files, profile)` — lấy context cho danh sách file thay đổi

### 11.2. Phase 3: Semantic retrieval

Truy vấn theo ngôn ngữ tự nhiên trên:

- summaries
- explanations
- selected architecture notes

Query primitive bổ sung:

- `semantic_context(query, profile)` — tìm kiếm semantic theo ngôn ngữ tự nhiên

### 11.3. Context Bundle

Mỗi query phải materialize thành một `context bundle` (JSON) để handoff sang AI agent khác.

Context bundle cho `Review Agent`:

- changed file summaries
- direct dependencies
- impacted modules
- matched conventions (Phase 3)
- matched risk areas (Phase 3)
- related files
- confidence/explanation cho từng item

---

## 12. Agent Profiles (Phase 2)

Knowledge base là shared, còn cách đọc knowledge sẽ do `agent profile` quyết định.

Profile được lưu bằng `YAML`.

### 12.1. Trường tối thiểu

```yaml
name: string
preferred_entities: list[string]
preferred_relations: list[string]
include_conventions: bool
include_risks: bool
include_related_files: bool
max_items: int
ranking_mode: string  # "relevance" | "dependency_depth" | "breadth_first"
summary_levels: list[string]  # ["file"] | ["file", "symbol"] | ["file", "symbol", "module"]
semantic_search_enabled: bool
```

### 12.2. Profile khởi tạo trong MVP

#### review-agent

Ưu tiên:

- changed files
- dependencies trực tiếp
- risk areas
- conventions
- related files cần đọc thêm

```yaml
name: review-agent
preferred_entities: [File, Symbol, Relation]
preferred_relations: [imports, calls, depends_on]
include_conventions: true
include_risks: true
include_related_files: true
max_items: 50
ranking_mode: dependency_depth
summary_levels: [file]
semantic_search_enabled: false
```

#### dev-agent

Ưu tiên:

- module responsibility
- extension points
- dependency flow
- architectural patterns

```yaml
name: dev-agent
preferred_entities: [Module, Symbol, File]
preferred_relations: [contains, imports, depends_on, inherits]
include_conventions: true
include_risks: false
include_related_files: true
max_items: 100
ranking_mode: breadth_first
summary_levels: [file]
semantic_search_enabled: false
```

#### doc-agent

Ưu tiên:

- purpose
- behavior summary
- domain terms
- public-facing flows

```yaml
name: doc-agent
preferred_entities: [Module, File, Symbol]
preferred_relations: [contains, imports]
include_conventions: true
include_risks: false
include_related_files: false
max_items: 80
ranking_mode: relevance
summary_levels: [file]
semantic_search_enabled: true
```

---

## 13. Tech Stack for MVP

- `Python 3.12`
- `Pydantic v2`
- `tree-sitter`
- local structured file storage: `JSON/JSONL`
- local vector index với abstraction nội bộ (Phase 3)
- provider-agnostic adapter cho embeddings và LLM
- `pytest`
- `ruff`
- `black`
- `mypy`

Lý do chọn:

- triển khai nhanh cho MVP
- đủ mạnh cho parsing và AI workflows
- dễ materialize shared memory thành file
- tránh phụ thuộc sớm vào service phức tạp

---

## 14. Tiêu chí hoàn thành theo Phase

### Phase 1 hoàn thành khi:

1. Có thể ingest một repo và tạo snapshot thành công
2. Snapshot có schema rõ ràng, validate được bằng Pydantic
3. Entities (File, Module, Symbol) được extract đúng
4. Relations cơ bản (contains, imports, calls, depends_on) được build
5. File-level summary được generate cho mỗi file

### Phase 2 hoàn thành khi:

1. Có thể chạy query bằng profile khác nhau
2. `Review Agent` lấy được context đủ để review thay đổi mà không cần đọc lại toàn repo
3. `Dev Agent` và `Doc Agent` có thể dùng cùng snapshot với profile riêng
4. Context bundle được materialize thành JSON hợp lệ

### Phase 3 hoàn thành khi:

1. Semantic search hoạt động trên summaries
2. Convention detection cho ít nhất 3 pattern phổ biến
3. Risk area detection cho ít nhất 3 vùng rủi ro phổ biến
4. Symbol-level và module-level summary được generate

---

## 15. Rủi ro cần kiểm soát

- parser coverage giữa nhiều ngôn ngữ không đồng đều → bắt đầu với Python, TypeScript
- summary quá phụ thuộc LLM sẽ làm output thiếu ổn định → dùng structured prompt + fallback heuristic
- semantic retrieval không đủ nếu thiếu structured relations → structured retrieval là core, semantic là bổ sung
- knowledge stale nếu ingest không được chạy lại sau thay đổi → ghi rõ snapshot timestamp
- file-based shared memory cần atomic write để tránh snapshot lỗi một phần → write vào temp rồi rename

---

## 16. Hướng phát triển sau MVP

- incremental ingest theo file hash
- active snapshot management
- live API/service layer
- multi-branch và multi-repo
- richer dependency graph
- PR-aware retrieval
- dashboard và observability
- policy engine cho từng loại agent

---

## 17. Tuyên bố MVP

> MVP của dự án là một hệ thống chuyển codebase thành shared, structured, versioned knowledge base ở dạng file-based shared memory, để nhiều AI agents có thể truy vấn và sử dụng thông qua profile cấu hình riêng, thay vì phải đọc lại toàn bộ source code mỗi lần làm việc.
>
> MVP được triển khai qua 3 phase: (1) Ingest + Structured Snapshot, (2) Agent Profile + Structured Retrieval, (3) Semantic Search + Enrichment. Mỗi phase đều deliver giá trị độc lập.

---

## 18. Implementation Status (Updated: 2026-05-05)

### ✅ Phase 1: Codebase Ingest + Structured Snapshot — COMPLETE

**Thực hiện:**
- Scanner với `.gitignore`-aware skip rules
- Language detection: Python, TypeScript, C#
- Tree-sitter–based entity extraction (functions, classes, methods, imports)
- Relation builder: imports, calls, contains, depends_on, inherits
- LLM-powered summarization (OpenAI-compatible adapter) + heuristic fallback
- Concurrent LLM summarization với ThreadPoolExecutor (10 workers)
- `--no-enrichment` flag để skip symbol/module enrichment (tối ưu thời gian)
- Snapshot package: JSON storage (files, symbols, relations, summaries)
- CLI: `pus ingest`, `pus list`, `pus show`

**Kiểm chứng thực tế (self-ingest — heuristic):**
```
Snapshot: fb56df2432702a09
  Files: 47 | Symbols: 257 | Relations: 304 | Summaries: 304
  Time: 0.8s
```

### ✅ Phase 2: Agent Profile + Structured Retrieval — COMPLETE

**Thực hiện:**
- Agent profile model (entities, relations, ranking, limits)
- 3 default profiles: `review-agent`, `dev-agent`, `doc-agent`
- Retrieval engine với 4 query primitives:
  - `file_context(path, profile)` — file + symbols + related files
  - `symbol_context(name, profile)` — symbol + containing file + siblings
  - `module_context(name, profile)` — module + files + symbols
  - `change_context(files, profile)` — changed files + impact analysis
- Context bundle với relevance scoring và agent-readable output
- CLI: `pus query file|symbol|module|changes`, `pus profiles`

### ✅ Phase 3: Semantic Search + Enrichment — COMPLETE

**Thực hiện:**
- TF-IDF–based semantic index với cosine similarity (zero-dependency, pure Python)
- Symbol-level + module-level summaries (heuristic + LLM enrichment)
- Convention detection: naming patterns, test file patterns, docstring patterns
- Risk area detection: large files, deep nesting, God classes, high complexity
- `semantic_context(query, profile)` retrieval primitive
- Pipeline enrichment: conventions, risks, semantic index built during ingest
- CLI: `pus query semantic "query" --repo <id> --top-k N`


### CLI Reference

```bash
# Ingest
pus ingest <repo_path> [--no-llm] [--no-enrichment] [--output-dir DIR]

# Query
pus query file <path> --repo <repo_id> [--profile <name>] [--json]
pus query symbol <name> --repo <repo_id> [--profile <name>] [--json]
pus query module <name> --repo <repo_id> [--profile <name>] [--json]
pus query changes --files <f1> <f2> --repo <repo_id> [--profile <name>] [--json]
pus query semantic "<query>" --repo <repo_id> [--profile <name>] [--top-k N] [--json]

# Management
pus list <repo_id>
pus show <repo_id> [--snapshot-id <id>]
pus profiles
pus version
```

### Completed Criteria Checklist

| # | Tiêu chí | Status |
|---|----------|--------|
| Phase 1.1 | Ingest repo và tạo snapshot thành công | ✅ |
| Phase 1.2 | Snapshot có schema rõ ràng, validate bằng Pydantic | ✅ |
| Phase 1.3 | Entities (File, Module, Symbol) được extract đúng | ✅ |
| Phase 1.4 | Relations cơ bản (contains, imports, calls, depends_on) được build | ✅ |
| Phase 1.5 | File-level summary được generate cho mỗi file | ✅ |
| Phase 2.1 | Chạy query bằng profile khác nhau | ✅ |
| Phase 2.2 | Review Agent lấy context đủ để review thay đổi | ✅ |
| Phase 2.3 | Dev Agent và Doc Agent dùng cùng snapshot với profile riêng | ✅ |
| Phase 2.4 | Context bundle materialize thành JSON hợp lệ | ✅ |
| Phase 3.1 | Semantic search hoạt động trên summaries | ✅ |
| Phase 3.2 | Convention detection cho ≥3 pattern phổ biến | ✅ |
| Phase 3.3 | Risk area detection cho ≥3 vùng rủi ro | ✅ |
| Phase 3.4 | Symbol-level và module-level summary được generate | ✅ |

### Lessons Learned

1. **LLM timeout issue:** Concurrent LLM enrichment (254 symbols) có thể mất >10 phút. Giải pháp: `--no-enrichment` flag để skip, chỉ dùng file-level LLM summaries.
2. **Worker count:** Tăng từ 5 → 10 workers giúp giảm thời gian summarization ~50%.
3. **C# parser:** Tree-sitter C# grammar hoạt động tốt với Xamarin/MAUI projects.
4. **File-based storage:** Snapshot JSON (~458KB cho 131 files) đủ nhỏ để load nhanh vào memory.
</task_progress>
</write_to_file>