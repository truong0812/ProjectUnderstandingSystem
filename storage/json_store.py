"""Lưu trữ tóm tắt dạng JSON — dễ đọc cho máy."""

import os
import json
from datetime import datetime
from dataclasses import asdict

from summarizer.llm_summarizer import ChunkSummary


def save_summaries_json(
    summaries: list[ChunkSummary],
    output_path: str,
    repo_path: str = "",
) -> str:
    """Lưu danh sách ChunkSummary thành file JSON.

    Args:
        summaries: Danh sách tóm tắt chunks.
        output_path: Đường dẫn file output (.json).
        repo_path: Đường dẫn repo gốc.

    Returns:
        Đường dẫn file đã lưu.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    data = {
        "metadata": {
            "repository": repo_path,
            "generated_at": datetime.now().isoformat(),
            "total_chunks": len(summaries),
        },
        "summaries": [asdict(s) for s in summaries],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return output_path


def load_summaries_json(input_path: str) -> list[ChunkSummary]:
    """Đọc danh sách ChunkSummary từ file JSON.

    Args:
        input_path: Đường dẫn file JSON.

    Returns:
        Danh sách ChunkSummary.
    """
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summaries = []
    for item in data.get("summaries", []):
        summaries.append(ChunkSummary(**item))

    return summaries