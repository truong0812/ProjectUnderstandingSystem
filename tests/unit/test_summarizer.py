"""Unit tests for summarizer module."""

from project_understanding.ingest.summarizer import (
    generate_file_summary,
    _generate_heuristic_summary,
)
from project_understanding.models.entities import File, Symbol, SymbolKind


def _make_file(path: str = "src/main.py", language: str = "python") -> File:
    """Helper to create a File entity for testing."""
    return File(
        file_id="fid1",
        snapshot_id="sid1",
        path=path,
        language=language,
        hash="abc123",
        size=100,
    )


def _make_symbol(name: str = "my_func", kind: SymbolKind = SymbolKind.FUNCTION) -> Symbol:
    """Helper to create a Symbol entity for testing."""
    return Symbol(
        symbol_id="sym1",
        file_id="fid1",
        name=name,
        kind=kind,
        path=f"module.{name}",
        line_start=1,
        line_end=10,
        hash="h1",
    )


class TestHeuristicSummary:
    """Tests for heuristic summary generation."""

    def test_empty_file(self):
        """Heuristic summary for empty file."""
        f = _make_file()
        result = _generate_heuristic_summary(f, "", [])
        assert "main.py" in result
        assert "python" in result

    def test_file_with_symbols(self):
        """Heuristic summary includes symbol info."""
        f = _make_file()
        symbols = [
            _make_symbol("foo", SymbolKind.FUNCTION),
            _make_symbol("Bar", SymbolKind.CLASS),
        ]
        result = _generate_heuristic_summary(f, "def foo(): pass\nclass Bar: pass", symbols)
        assert "foo" in result
        assert "Bar" in result

    def test_file_with_many_symbols_truncates(self):
        """Heuristic summary truncates when too many symbols."""
        f = _make_file()
        symbols = [_make_symbol(f"func{i}", SymbolKind.FUNCTION) for i in range(10)]
        result = _generate_heuristic_summary(f, "x = 1\n" * 50, symbols)
        assert "+" in result  # Should show "+N more"

    def test_line_count(self):
        """Heuristic summary includes line count."""
        f = _make_file()
        content = "line1\nline2\nline3"
        result = _generate_heuristic_summary(f, content, [])
        assert "3 lines" in result


class TestGenerateFileSummary:
    """Tests for generate_file_summary (without LLM)."""

    def test_without_llm_uses_heuristic(self):
        """Without LLM, should use heuristic summary."""
        f = _make_file()
        summary = generate_file_summary(f, "def foo(): pass", [])
        assert summary.generated_by.value == "heuristic"
        assert "main.py" in summary.content

    def test_summary_has_correct_file_id(self):
        """Summary should reference the correct file."""
        f = _make_file()
        summary = generate_file_summary(f, "content", [])
        assert summary.target_id == f.file_id
        assert summary.target_type == "file"

    def test_summary_with_empty_content(self):
        """Summary for empty content should still work."""
        f = _make_file()
        summary = generate_file_summary(f, "", [])
        assert summary is not None
        assert summary.content != ""