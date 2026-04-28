"""CrewAI-inspired Multi-Agent Summarizer — Deep mode.

Sử dụng nhiều agents chuyên biệt để phân tích code chunk,
mỗi agent đóng vai trò khác nhau cho phân tích toàn diện hơn.

Agents:
- Code Analyzer: Phân tích cấu trúc, logic, complexity
- Doc Writer: Viết documentation dễ hiểu
- Dependency Mapper: Phát hiện dependencies, relationships
- Architecture Reviewer: Đánh giá kiến trúc, patterns

Thiết kế lấy cảm hứng từ CrewAI nhưng dùng langchain-openai trực tiếp
để tránh dependency conflicts.
"""

import os
import json
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import (
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    LLM_MODEL,
)
from chunker.code_chunker import CodeChunk
from summarizer.llm_summarizer import ChunkSummary


# ─── Agent Definitions ─────────────────────────────────────────────

@dataclass
class AgentConfig:
    """Cấu hình cho một agent."""
    name: str
    role: str
    goal: str
    backstory: str
    system_prompt: str


# Agent 1: Code Analyzer
CODE_ANALYZER = AgentConfig(
    name="Code Analyzer",
    role="Senior Software Engineer",
    goal="Phân tích cấu trúc code, logic flow, và complexity",
    backstory=(
        "Bạn là kỹ sư phần mềm giàu kinh nghiệm, chuyên phân tích code. "
        "Bạn có khả năng hiểu nhanh logic, phát hiện patterns, "
        "và đánh giá complexity của bất kỳ đoạn code nào."
    ),
    system_prompt="""Bạn là Code Analyzer Agent. Nhiệm vụ: phân tích đoạn code sau.

Trả về JSON với format:
{
    "structure": "Mô tả cấu trúc (hàm/class/module, các thành phần chính)",
    "logic_flow": "Mô tả logic flow của code",
    "complexity": "Đánh giá complexity (low/medium/high) và lý do",
    "patterns": "Design patterns phát hiện được (nếu có)",
    "issues": "Potential issues hoặc code smells (nếu có)",
    "summary": "Tóm tắt ngắn gọn trong 2-3 câu"
}

Code để phân tích:
File: {file_path}
Ngôn ngữ: {language}
Tên: {name}
Loại: {chunk_type}
Dòng: {start_line}-{end_line}

```{language}
{code}
```

Chỉ trả về JSON hợp lệ, không thêm text khác.""",
)

# Agent 2: Documentation Writer
DOC_WRITER = AgentConfig(
    name="Documentation Writer",
    role="Technical Writer",
    goal="Viết documentation rõ ràng, dễ hiểu cho developer khác",
    backstory=(
        "Bạn là technical writer chuyên nghiệp, giỏi biến code phức tạp "
        "thành documentation dễ hiểu. Bạn viết cho developer trung bình "
        "có thể hiểu được mục đích và cách sử dụng."
    ),
    system_prompt="""Bạn là Documentation Writer Agent. Nhiệm vụ: viết documentation cho code sau.

Trả về JSON với format:
{{
    "purpose": "Mục đích chính của đoạn code này (1 câu rõ ràng)",
    "description": "Mô tả chi tiết những gì code làm (2-3 câu)",
    "parameters": "Các parameters/inputs (tên: kiểu - mô tả), hoặc N/A",
    "returns": "Giá trị trả về và kiểu",
    "usage_example": "Ví dụ cách sử dụng (ngắn gọn)",
    "notes": "Ghi chú quan trọng cho developer (edge cases, warnings)"
}}

Code:
File: {file_path}
Ngôn ngữ: {language}
Tên: {name}
Loại: {chunk_type}

```{language}
{code}
```

Chỉ trả về JSON hợp lệ, không thêm text khác.""",
)

# Agent 3: Dependency Mapper
DEPENDENCY_MAPPER = AgentConfig(
    name="Dependency Mapper",
    role="System Architect",
    goal="Phát hiện dependencies, imports, và relationships với code khác",
    backstory=(
        "Bạn là system architect có khả năng nhìn thấy bức tranh lớn. "
        "Bạn phân tích cách các thành phần code kết nối với nhau, "
        "phát hiện dependencies và potential coupling issues."
    ),
    system_prompt="""Bạn là Dependency Mapper Agent. Nhiệm vụ: phân tích dependencies của code sau.

Trả về JSON với format:
{{
    "imports": "Các imports/modules sử dụng (liệt kê)",
    "internal_deps": "Dependencies nội bộ (các hàm/class khác trong project gọi đến)",
    "external_deps": "External dependencies (thư viện thứ 3)",
    "used_by": "Dự đoán component nào có thể sử dụng code này",
    "coupling": "Đánh giá coupling level (low/medium/high)",
    "dependencies": "Tóm tắt dependencies quan trọng nhất (1 câu)"
}}

Code:
File: {file_path}
Ngôn ngữ: {language}
Tên: {name}

```{language}
{code}
```

Chỉ trả về JSON hợp lệ, không thêm text khác.""",
)


# ─── Synthesis Prompt ───────────────────────────────────────────────

SYNTHESIS_PROMPT = """Bạn là Lead Engineer. Tổng hợp phân tích từ các agents thành một bản tóm tắt cuối cùng.

=== PHÂN TÍCH TỪ CODE ANALYZER ===
{analysis}

=== DOCUMENTATION ===
{documentation}

=== DEPENDENCY ANALYSIS ===
{dependencies}

=== THÔNG TIN CHUNK ===
File: {file_path}
Tên: {name}
Loại: {chunk_type}
Ngôn ngữ: {language}
Dòng: {start_line}-{end_line}

Tổng hợp thành JSON:
{{
    "chunk_id": "{chunk_id}",
    "file_path": "{file_path}",
    "name": "{name}",
    "chunk_type": "{chunk_type}",
    "language": "{language}",
    "start_line": {start_line},
    "end_line": {end_line},
    "summary": "Tóm tắt tổng hợp (2-3 câu, đầy đủ nhất)",
    "purpose": "Mục đích chính (1 câu)",
    "parameters": "Parameters hoặc N/A",
    "dependencies": "Dependencies quan trọng nhất",
    "complexity": "Complexity assessment (low/medium/high — lý do)"
}}

Chỉ trả về JSON hợp lệ."""


# ─── Crew Summarizer ────────────────────────────────────────────────

class CrewSummarizer:
    """Multi-agent summarizer lấy cảm hứng từ CrewAI."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            temperature=0.1,
            max_tokens=1000,
        )
        self.agents = [CODE_ANALYZER, DOC_WRITER, DEPENDENCY_MAPPER]

    def _run_agent(self, agent: AgentConfig, chunk: CodeChunk) -> dict:
        """Chạy một agent trên một chunk."""
        prompt = agent.system_prompt.format(
            file_path=chunk.file_path,
            language=chunk.language,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            code=chunk.code,
        )

        messages = [
            SystemMessage(content=f"Role: {agent.role}\nGoal: {agent.goal}\nBackstory: {agent.backstory}"),
            HumanMessage(content=prompt),
        ]

        try:
            response = self.llm.invoke(messages)
            return self._parse_json_response(response.content)
        except Exception as e:
            print(f"    ⚠️  Agent {agent.name} lỗi: {e}")
            return {"error": str(e)}

    def _synthesize(
        self,
        chunk: CodeChunk,
        analysis: dict,
        documentation: dict,
        dependencies: dict,
    ) -> ChunkSummary:
        """Tổng hợp kết quả từ tất cả agents."""
        prompt = SYNTHESIS_PROMPT.format(
            analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
            documentation=json.dumps(documentation, indent=2, ensure_ascii=False),
            dependencies=json.dumps(dependencies, indent=2, ensure_ascii=False),
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = self._parse_json_response(response.content)
        except Exception as e:
            print(f"    ⚠️  Synthesis lỗi: {e}")
            result = {}

        return ChunkSummary(
            chunk_id=chunk.chunk_id,
            file_path=chunk.file_path,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            summary=result.get("summary", analysis.get("summary", "N/A")),
            purpose=result.get("purpose", documentation.get("purpose", "N/A")),
            parameters=result.get("parameters", documentation.get("parameters", "N/A")),
            dependencies=result.get("dependencies", dependencies.get("dependencies", "N/A")),
            complexity=result.get("complexity", analysis.get("complexity", "N/A")),
        )

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Parse JSON từ LLM response, xử lý markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return json.loads(text)

    def summarize_chunk(self, chunk: CodeChunk) -> ChunkSummary:
        """Chạy tất cả agents trên một chunk, sau đó tổng hợp."""
        # Chạy từng agent
        analysis = self._run_agent(CODE_ANALYZER, chunk)
        documentation = self._run_agent(DOC_WRITER, chunk)
        dependencies = self._run_agent(DEPENDENCY_MAPPER, chunk)

        # Tổng hợp
        return self._synthesize(chunk, analysis, documentation, dependencies)


def crew_summarize_all(chunks: list[CodeChunk]) -> list[ChunkSummary]:
    """Tóm tắt tất cả chunks bằng multi-agent crew.

    Args:
        chunks: Danh sách CodeChunk cần tóm tắt.

    Returns:
        Danh sách ChunkSummary.
    """
    crew = CrewSummarizer()
    summaries: list[ChunkSummary] = []

    total = len(chunks)
    print(f"  🤖 Crew: {len(crew.agents)} agents × {total} chunks = ~{len(crew.agents) * total + total} LLM calls")
    print(f"  ⏱️  Ước tính: ~{total * 20 // 60}m {total * 20 % 60}s")
    print()

    for i, chunk in enumerate(chunks, 1):
        short_name = f"{chunk.file_path}::{chunk.name}"
        print(f"  🔄 [{i}/{total}] Crew analyzing: {short_name}")

        try:
            summary = crew.summarize_chunk(chunk)
            summaries.append(summary)
            print(f"  ✅ [{i}/{total}] Done: {short_name}")
        except Exception as e:
            print(f"  ❌ [{i}/{total}] Lỗi {short_name}: {e}")

    print()
    print(f"  📊 Crew hoàn tất: {len(summaries)}/{total} chunks analyzed")
    return summaries