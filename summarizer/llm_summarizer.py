"""Bộ tóm tắt code bằng LLM — xử lý từng chunk một.

Quan trọng: KHÔNG tải toàn bộ repo vào LLM.
Mỗi chunk được gửi riêng biệt để tóm tắt.
"""

import time
import json
from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from config.settings import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    LLM_MODEL,
)
from chunker.code_chunker import CodeChunk


@dataclass
class ChunkSummary:
    """Kết quả tóm tắt một chunk."""

    chunk_id: str          # unique_id từ CodeChunk
    file_path: str         # Đường dẫn file
    name: str              # Tên hàm/class
    chunk_type: str        # function/class/method/module
    language: str          # Ngôn ngữ lập trình
    start_line: int        # Dòng bắt đầu
    end_line: int          # Dòng kết thúc
    summary: str           # Tóm tắt bằng LLM
    purpose: str           # Mục đích chính
    parameters: str        # Tham số (nếu có)
    dependencies: str      # Dependencies / imports
    complexity: str        # Đánh giá độ phức tạp


# ─── Prompt template ────────────────────────────────────────────────

SUMMARY_PROMPT = """Bạn là một kỹ sư phần mềm giỏi. Hãy phân tích đoạn code sau và trả về JSON hợp lệ.

## Thông tin
- File: {file_path}
- Tên: {name}
- Loại: {chunk_type}
- Ngôn ngữ: {language}
- Dòng: {start_line}-{end_line}

## Code
```{language}
{content}
```

## Yêu cầu
Trả về JSON với các trường sau (bằng tiếng Anh):
{{
    "summary": "Tóm tắt ngắn gọn những gì đoạn code này làm (2-3 câu)",
    "purpose": "Mục đích chính của hàm/class này",
    "parameters": "Các tham số đầu vào và kiểu dữ liệu (nếu có)",
    "dependencies": "Các module/thư viện/hàm bên ngoài được sử dụng",
    "complexity": "Đánh giá độ phức tạp: low/medium/high kèm lý do ngắn"
}}

Chỉ trả về JSON, không thêm text khác."""


def _create_llm() -> ChatOpenAI:
    """Tạo LLM instance từ config."""
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
        temperature=0.1,
        max_tokens=500,
    )


def _parse_llm_response(response_text: str) -> dict:
    """Parse JSON từ response của LLM."""
    text = response_text.strip()

    # Thử tìm JSON trong code block
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: trả về summary thô
        return {
            "summary": text[:300],
            "purpose": "N/A",
            "parameters": "N/A",
            "dependencies": "N/A",
            "complexity": "N/A",
        }


def summarize_chunk(chunk: CodeChunk, llm: ChatOpenAI | None = None) -> ChunkSummary:
    """Tóm tắt một chunk bằng LLM.

    Args:
        chunk: CodeChunk cần tóm tắt.
        llm: ChatOpenAI instance (tạo mới nếu None).

    Returns:
        ChunkSummary với thông tin tóm tắt.
    """
    if llm is None:
        llm = _create_llm()

    prompt = SUMMARY_PROMPT.format(
        file_path=chunk.file_path,
        name=chunk.name,
        chunk_type=chunk.chunk_type,
        language=chunk.language,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        content=chunk.content[:3000],  # Giới hạn nội dung
    )

    try:
        response = llm.invoke(prompt)
        parsed = _parse_llm_response(response.content)
    except Exception as e:
        print(f"    ⚠️  Lỗi tóm tắt chunk {chunk.name}: {e}")
        parsed = {
            "summary": f"(Lỗi tóm tắt: {str(e)[:100]})",
            "purpose": "N/A",
            "parameters": "N/A",
            "dependencies": "N/A",
            "complexity": "N/A",
        }

    return ChunkSummary(
        chunk_id=chunk.unique_id,
        file_path=chunk.file_path,
        name=chunk.name,
        chunk_type=chunk.chunk_type,
        language=chunk.language,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
        summary=parsed.get("summary", "N/A"),
        purpose=parsed.get("purpose", "N/A"),
        parameters=parsed.get("parameters", "N/A"),
        dependencies=parsed.get("dependencies", "N/A"),
        complexity=parsed.get("complexity", "N/A"),
    )


def summarize_all(
    chunks: list[CodeChunk],
    delay: float = 0.5,
    progress_callback=None,
) -> list[ChunkSummary]:
    """Tóm tắt tất cả chunks tuần tự.

    Args:
        chunks: Danh sách CodeChunk cần tóm tắt.
        delay: Thời gian chờ giữa các lần gọi LLM (giây).
        progress_callback: Hàm callback(progress, total, chunk_name).

    Returns:
        Danh sách ChunkSummary.
    """
    llm = _create_llm()
    summaries: list[ChunkSummary] = []
    total = len(chunks)

    print(f"  📝 Bắt đầu tóm tắt {total} chunks...")

    for i, chunk in enumerate(chunks, 1):
        if progress_callback:
            progress_callback(i, total, chunk.name)
        else:
            print(f"    [{i}/{total}] {chunk.name} ({chunk.chunk_type})")

        summary = summarize_chunk(chunk, llm)
        summaries.append(summary)

        # Rate limiting
        if i < total and delay > 0:
            time.sleep(delay)

    print(f"  ✅ Đã tóm tắt {len(summaries)} chunks.")
    return summaries