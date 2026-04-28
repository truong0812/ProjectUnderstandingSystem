# 🧠 Repo Knowledge System

Hệ thống tạo knowledge base từ code repository — Parse repo, chia chunk, tóm tắt bằng LLM, lưu trữ vector, và cung cấp API truy vấn cho AI bots khác.

## 🎯 Mục tiêu

Tạo một hệ thống kiến thức tái sử dụng mà các bot AI khác có thể truy vấn để hiểu codebase.

---

## 📁 Cấu trúc dự án

```
project-understanding-system/
├── config/
│   ├── __init__.py
│   └── settings.py              # Cấu hình từ .env
├── parser/
│   ├── __init__.py
│   └── repo_parser.py           # Parse thư mục repo
├── chunker/
│   ├── __init__.py
│   └── code_chunker.py          # Chia code thành chunks (AST + regex)
├── summarizer/
│   ├── __init__.py
│   ├── llm_summarizer.py        # ⚡ Fast: Tóm tắt từng chunk bằng LLM
│   └── crew_summarizer.py       # 🤖 Deep: Multi-agent crew (3 agents + synthesis)
├── storage/
│   ├── __init__.py
│   ├── markdown_store.py        # Xuất Markdown
│   ├── json_store.py            # Xuất JSON
│   └── vector_store.py          # FAISS vector store
├── pipeline/
│   ├── __init__.py
│   └── orchestrator.py          # Pipeline điều phối
├── api/
│   ├── __init__.py
│   └── server.py                # FastAPI server (/context endpoint)
├── output/                      # Kết quả (tự tạo khi chạy)
├── main.py                      # CLI entry point
├── .env.example                 # Template cấu hình
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🔄 Workflow

```
Thư mục repo
     │
     ▼
┌──────────────┐
│   Parser     │  Duyệt cây thư mục, nhận diện file code
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Chunker    │  Chia code thành hàm/class/module (AST + regex)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Summarizer  │  Tóm tắt TỪNG CHUNK bằng LLM (không load toàn bộ repo)
└──────┬───────┘
       │
       ├──────────────────┬──────────────────┐
       ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Markdown    │  │    JSON      │  │   FAISS      │
│  summaries.md│  │ summaries.json│  │ vector index │
└──────────────┘  └──────────────┘  └──────┬───────┘
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │  FastAPI     │
                                    │  /context    │  Bot AI truy vấn
                                    └──────────────┘
```

---

## 📋 Prerequisites

| Yêu cầu | Cách lấy |
|---------|----------|
| **Python 3.10+** | [python.org](https://www.python.org/downloads/) |
| **OpenAI API Key** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

---

## 🚀 Cài đặt

### Bước 1: Tạo virtual environment

```bash
python -m venv .venv

# Windows CMD:
.venv\Scripts\activate.bat

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Linux/macOS:
source .venv/bin/activate
```

### Bước 2: Cài dependencies

```bash
pip install -r requirements.txt
```

### Bước 3: Cấu hình

```bash
cp .env.example .env
```

Sửa file `.env`:

```env
OPENAI_API_KEY=sk-proj-your-actual-key-here
OPENAI_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
```

> **Dùng provider khác** (Groq, OpenRouter, LM Studio): Thay `OPENAI_API_BASE` tương ứng.

---

## ▶️ Sử dụng

### Chạy pipeline phân tích repo

```bash
# ⚡ Fast mode (mặc định) — 1 LLM call/chunk, nhanh, rẻ
python main.py /path/to/your/project

# 🤖 Deep mode — 3 agents + 1 synthesis/chunk, phân tích toàn diện
python main.py /path/to/your/project --mode deep

# Phân tích + khởi động API server
python main.py /path/to/your/project --serve

# Kết hợp deep + serve
python main.py /path/to/your/project --mode deep --serve

# Chỉ định thư mục output
python main.py /path/to/your/project --output ./my_output
```

### So sánh Fast vs Deep

| | ⚡ Fast | 🤖 Deep |
|---|---|---|
| **LLM calls/chunk** | 1 | 4 (3 agents + 1 synthesis) |
| **Thời gian/chunk** | ~2-3s | ~15-20s |
| **Chi phí** | Rẻ | ~4x fast |
| **Chất lượng** | Tóm tắt tốt | Phân tích sâu: structure, docs, dependencies |
| **Phù hợp** | Quick scan, CI/CD | Code review, documentation, kiến trúc analysis |
| **Agents** | — | Code Analyzer, Doc Writer, Dependency Mapper |

### Chỉ khởi động API (dùng index đã có)

```bash
python main.py --serve
```

---

## 🌐 API Endpoints

Sau khi khởi động server (`http://localhost:8000`):

### `GET /context`

Tìm kiếm code summaries liên quan đến câu truy vấn.

```bash
# Ví dụ
curl "http://localhost:8000/context?query=how+does+authentication+work&top_k=5"
```

Response:
```json
{
  "query": "how does authentication work",
  "top_k": 5,
  "total_results": 3,
  "results": [
    {
      "chunk_id": "auth.py::login::15",
      "file_path": "auth.py",
      "name": "login",
      "chunk_type": "function",
      "language": "python",
      "start_line": 15,
      "end_line": 42,
      "summary": "Handles user login with JWT token generation...",
      "purpose": "Authenticate user and return JWT token",
      "parameters": "username: str, password: str",
      "dependencies": "jwt, bcrypt, database",
      "complexity": "medium — JWT token generation with error handling",
      "score": 0.87
    }
  ]
}
```

### `POST /ingest`

Chạy pipeline cho repo mới qua API.

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/project"}'
```

### `GET /health`

Kiểm tra trạng thái API và FAISS index.

```bash
curl http://localhost:8000/health
```

### 📖 Interactive Docs

Truy cập `http://localhost:8000/docs` để xem Swagger UI.

---

## 📦 Kết quả đầu ra

Sau khi chạy pipeline, thư mục `output/` chứa:

| File | Mô tả |
|------|-------|
| `summaries.md` | Báo cáo tóm tắt dễ đọc cho người |
| `summaries.json` | Dữ liệu có cấu trúc cho máy |
| `faiss_index/index.faiss` | FAISS vector index |
| `faiss_index/metadata.pkl` | Metadata (summaries + embeddings) |

---

## ⚙️ Cấu hình

Tất cả cấu hình qua file `.env`:

| Biến | Mô tả | Mặc định |
|------|-------|----------|
| `OPENAI_API_KEY` | API key cho LLM | — |
| `OPENAI_API_BASE` | API base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model tóm tắt | `gpt-4o-mini` |
| `EMBEDDING_MODEL` | Model embedding | `text-embedding-3-small` |
| `OUTPUT_DIR` | Thư mục output | `./output` |
| `CHUNK_MAX_LINES` | Số dòng tối đa/chunk | `500` |
| `API_HOST` | API host | `0.0.0.0` |
| `API_PORT` | API port | `8000` |
| `DEFAULT_TOP_K` | Số kết quả tìm kiếm mặc định | `5` |

---

## 🔑 Nguyên tắc thiết kế

1. ✅ **Không tải toàn bộ repo vào LLM** — xử lý từng chunk một
2. ✅ **Chunking trước** — code được chia nhỏ trước khi gọi LLM
3. ✅ **Modular** — mỗi module một trách nhiệm duy nhất
4. ✅ **API để bot khác truy vấn** — FastAPI `/context` endpoint
5. ✅ **Triple storage** — Markdown, JSON, FAISS vector database

---

## 🧰 Tech Stack

| Thành phần | Công nghệ | Mục đích |
|-----------|-----------|----------|
| **Language** | Python 3.10+ | Ngôn ngữ chính |
| **Web Framework** | FastAPI | API server hiệu năng cao, auto-docs |
| **ASGI Server** | Uvicorn | Chạy FastAPI |
| **LLM** | OpenAI GPT-4o-mini (via LangChain) | Tóm tắt code chunks |
| **Embeddings** | OpenAI `text-embedding-3-small` | Vector hóa summaries |
| **Vector DB** | FAISS (faiss-cpu) | Lưu trữ & tìm kiếm vector similarity |
| **LLM Framework** | LangChain (langchain-openai, langchain-community) | Quản lý LLM calls, embeddings |
| **Data** | NumPy, Pickle | Xử lý ma trận embeddings, serialize metadata |
| **HTTP Client** | httpx | API client |
| **Config** | python-dotenv | Load cấu hình từ `.env` |

### Kiến trúc dữ liệu

```
Code File → Parser → Chunker → LLM Summarizer → Storage
                                                    ├── Markdown (.md)      ← Human-readable
                                                    ├── JSON (.json)        ← Machine-readable
                                                    └── FAISS (index.faiss) ← Vector search
```

---

## 🔮 Hướng phát triển tương lai

### Giai đoạn 1 — Cải thiện core
- [ ] **AST parsing mở rộng**: Hỗ trợ Java, Go, Rust bằng tree-sitter thay vì regex
- [ ] **Incremental indexing**: Chỉ re-index file thay đổi, không rebuild toàn bộ
- [ ] **Streaming summaries**: Hiển thị tóm tắt real-time qua WebSocket khi đang xử lý
- [ ] **Cache LLM responses**: Tránh gọi LLM lại cho code không thay đổi

### Giai đoạn 2 — Tăng cường AI
- [ ] **Multi-repo support**: Phân tích nhiều repo, tạo knowledge graph liên project
- [ ] **Code relationship mapping**: Phát hiện dependency giữa các chunk/module
- [ ] **Architecture diagram generation**: Tự động vẽ sơ đồ kiến trúc từ summaries
- [ ] **RAG-enhanced Q&A**: Kết hợp vector search với LLM để trả lời câu hỏi về code
- [ ] **Local LLM support**: Tích hợp Ollama/llama.cpp cho môi trường không có internet

### Giai đoạn 3 — Nền tảng
- [ ] **Authentication & API keys**: Bảo vệ endpoint bằng JWT/API key
- [ ] **Multi-tenant**: Nhiều user/project riêng biệt
- [ ] **Web Dashboard**: UI trực quan để xem summaries, tìm kiếm, quản lý repos
- [ ] **Plugin system**: Cho phép mở rộng parser/chunker cho ngôn ngữ/framework mới
- [ ] **CI/CD integration**: GitHub Action tự động re-index khi push code
- [ ] **Database persistence**: Lưu metadata vào PostgreSQL/SQLite thay vì pickle files
- [ ] **Docker deployment**: Dockerfile + docker-compose cho deployment dễ dàng

### Giai đoạn 4 — Ecosystem
- [ ] **MCP Server**: Biến hệ thống thành MCP tool cho Claude/Cursor/VS Code
- [ ] **CLI enhancement**: Interactive mode, search trực tiếp từ terminal
- [ ] **IDE extensions**: VS Code extension để query context ngay trong editor
- [ ] **Team knowledge base**: Chia sẻ knowledge giữa team members
- [ ] **Code review assistant**: Tự động review PR dựa trên project knowledge

---

## 🛠️ Ngôn ngữ được hỗ trợ

Python, JavaScript, TypeScript, Java, Go, Rust, C, C++, C#, Ruby, PHP, Swift, Kotlin, Scala, Shell, SQL, và hơn nữa.

---

## 📄 License

MIT