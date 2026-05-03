"""Cấu hình cho Project Understanding System.

Đọc tất cả config từ file .env bằng python-dotenv.
Không phụ thuộc project nào khác.
"""

import os
from dotenv import load_dotenv

# Load environment variables từ file .env
load_dotenv()

# ─── LLM Configuration ────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "sk-your-api-key-here")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ─── Embedding Configuration ──────────────────────────────────────
HF_EMBEDDING_MODEL = os.getenv("HF_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ─── Paths ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(BASE_DIR, "output"))
FAISS_INDEX_PATH = os.path.join(OUTPUT_DIR, "faiss_index")
SUMMARIES_MD_PATH = os.path.join(OUTPUT_DIR, "summaries.md")
SUMMARIES_JSON_PATH = os.path.join(OUTPUT_DIR, "summaries.json")

# ─── Chunking Configuration ───────────────────────────────────────
CHUNK_MAX_LINES = int(os.getenv("CHUNK_MAX_LINES", "500"))

# ─── API Configuration ────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ─── Search Configuration ─────────────────────────────────────────
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K", "5"))

# ─── File extensions được hỗ trợ ──────────────────────────────────
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".r": "r",
    ".R": "r",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
    ".ps1": "powershell",
}

# ─── Thư mục cần bỏ qua ───────────────────────────────────────────
SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".svn", ".hg",
    "venv", ".venv", "env", ".env",
    "dist", "build", "egg-info", ".tox", ".mypy_cache",
    ".pytest_cache", ".idea", ".vscode",
    "vendor", "Pods", ".gradle", ".mvn",
}