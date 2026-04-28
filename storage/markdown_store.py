"""Lưu trữ tóm tắt dạng Markdown — dễ đọc cho con người."""

import os
from datetime import datetime

from summarizer.llm_summarizer import ChunkSummary


def save_summaries_md(
    summaries: list[ChunkSummary],
    output_path: str,
    repo_path: str = "",
) -> str:
    """Lưu danh sách ChunkSummary thành file Markdown.

    Args:
        summaries: Danh sách tóm tắt chunks.
        output_path: Đường dẫn file output (.md).
        repo_path: Đường dẫn repo gốc (hiển thị trong header).

    Returns:
        Đường dẫn file đã lưu.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    lines: list[str] = []

    # Header
    lines.append("# 📋 Code Intelligence Report")
    lines.append("")
    lines.append(f"- **Repository:** `{repo_path}`")
    lines.append(f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **Total chunks:** {len(summaries)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Nhóm theo file
    by_file: dict[str, list[ChunkSummary]] = {}
    for s in summaries:
        by_file.setdefault(s.file_path, []).append(s)

    for file_path, file_summaries in sorted(by_file.items()):
        lines.append(f"## 📄 `{file_path}`")
        lines.append("")

        for s in file_summaries:
            icon = {
                "function": "⚡",
                "class": "🏛️",
                "method": "🔧",
                "module": "📦",
                "interface": "🔗",
            }.get(s.chunk_type, "📝")

            lines.append(f"### {icon} `{s.name}` ({s.chunk_type})")
            lines.append(f"- **Lines:** {s.start_line}–{s.end_line}")
            lines.append(f"- **Language:** {s.language}")
            lines.append("")
            lines.append(f"**Summary:** {s.summary}")
            lines.append("")
            lines.append(f"**Purpose:** {s.purpose}")
            lines.append("")

            if s.parameters and s.parameters != "N/A":
                lines.append(f"**Parameters:** {s.parameters}")
                lines.append("")

            if s.dependencies and s.dependencies != "N/A":
                lines.append(f"**Dependencies:** {s.dependencies}")
                lines.append("")

            if s.complexity and s.complexity != "N/A":
                lines.append(f"**Complexity:** {s.complexity}")
                lines.append("")

            lines.append("---")
            lines.append("")

    content = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path