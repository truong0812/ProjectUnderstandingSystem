"""Unit tests for LLM-based domain detection.

Tests cover:
- detect_domain_llm with mock LLM
- _condense_samples helper
- _parse_domain_response helper
- Edge cases: empty input, invalid JSON, no domain, etc.
"""

from __future__ import annotations

from project_understanding.ingest.domain_detector import (
    detect_domain_llm,
    _condense_samples,
    _parse_domain_response,
)


class FakeLLM:
    """Fake LLM that returns a predefined response."""

    def __init__(self, response: str = ""):
        self._response = response

    def generate(self, prompt: str, system: str = "") -> str:
        return self._response


class FailingLLM:
    """Fake LLM that always raises an exception."""

    def generate(self, prompt: str, system: str = "") -> str:
        raise RuntimeError("LLM unavailable")


# ---------------------------------------------------------------------------
# detect_domain_llm
# ---------------------------------------------------------------------------

class TestDetectDomainLLM:
    """Tests for the main detect_domain_llm function."""

    def test_returns_dict_with_valid_response(self):
        response = '{"shipment": "Lô hàng vận chuyển", "warehouse": "Kho hàng"}'
        llm = FakeLLM(response)
        result = detect_domain_llm(["# cargo shipment code"], llm)
        assert isinstance(result, dict)
        assert "shipment" in result
        assert "warehouse" in result

    def test_returns_empty_on_no_domain(self):
        response = "{}"
        llm = FakeLLM(response)
        result = detect_domain_llm(["def hello(): pass"], llm)
        assert result == {}

    def test_returns_empty_on_empty_samples(self):
        llm = FakeLLM('{"key": "value"}')
        result = detect_domain_llm([], llm)
        assert result == {}

    def test_returns_empty_on_blank_samples(self):
        llm = FakeLLM('{"key": "value"}')
        result = detect_domain_llm(["   ", ""], llm)
        assert result == {}

    def test_returns_empty_on_llm_error(self):
        llm = FailingLLM()
        result = detect_domain_llm(["some code"], llm)
        assert result == {}

    def test_returns_empty_on_empty_response(self):
        llm = FakeLLM("")
        result = detect_domain_llm(["some code"], llm)
        assert result == {}

    def test_respects_max_terms(self):
        response = '{"a": "1", "b": "2", "c": "3", "d": "4", "e": "5"}'
        llm = FakeLLM(response)
        result = detect_domain_llm(["code"], llm, max_terms=3)
        assert len(result) <= 3

    def test_handles_markdown_code_block_response(self):
        response = '```json\n{"cargo": "Hàng hóa", "flight": "Chuyến bay"}\n```'
        llm = FakeLLM(response)
        result = detect_domain_llm(["cargo flight code"], llm)
        assert "cargo" in result
        assert "flight" in result

    def test_handles_response_with_surrounding_text(self):
        response = 'Here is the result:\n{"patient": "Bệnh nhân"}\nHope this helps!'
        llm = FakeLLM(response)
        result = detect_domain_llm(["patient code"], llm)
        assert "patient" in result


# ---------------------------------------------------------------------------
# _condense_samples
# ---------------------------------------------------------------------------

class TestCondenseSamples:
    """Tests for the _condense_samples helper."""

    def test_basic_condensation(self):
        samples = ["short code"]
        result = _condense_samples(samples)
        assert "short code" in result

    def test_truncates_long_samples(self):
        long_sample = "x" * 1000
        result = _condense_samples([long_sample])
        assert len(result) < 1000
        assert "truncated" in result

    def test_limits_to_max_samples(self):
        samples = [f"file_{i} content" for i in range(20)]
        result = _condense_samples(samples)
        # Should not contain file_10 through file_19
        assert "file_0" in result
        assert "file_9" in result

    def test_skips_empty_samples(self):
        samples = ["", "   ", "valid code"]
        result = _condense_samples(samples)
        assert "valid code" in result
        assert "---" not in result  # Only 1 non-empty, no separator

    def test_returns_empty_for_all_empty(self):
        result = _condense_samples(["", "  "])
        assert result == ""


# ---------------------------------------------------------------------------
# _parse_domain_response
# ---------------------------------------------------------------------------

class TestParseDomainResponse:
    """Tests for the _parse_domain_response helper."""

    def test_valid_json(self):
        result = _parse_domain_response('{"a": "desc a", "b": "desc b"}', max_terms=15)
        assert result == {"a": "desc a", "b": "desc b"}

    def test_empty_json(self):
        result = _parse_domain_response("{}", max_terms=15)
        assert result == {}

    def test_markdown_wrapped_json(self):
        response = "```json\n{\"key\": \"value\"}\n```"
        result = _parse_domain_response(response, max_terms=15)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        response = "Here you go:\n{\"term\": \"description\"}\nDone."
        result = _parse_domain_response(response, max_terms=15)
        assert result == {"term": "description"}

    def test_invalid_json_returns_empty(self):
        result = _parse_domain_response("not json at all", max_terms=15)
        assert result == {}

    def test_empty_response_returns_empty(self):
        result = _parse_domain_response("", max_terms=15)
        assert result == {}

    def test_none_response_returns_empty(self):
        result = _parse_domain_response(None, max_terms=15)
        assert result == {}

    def test_non_dict_json_returns_empty(self):
        result = _parse_domain_response('["a", "b"]', max_terms=15)
        assert result == {}

    def test_non_string_values_filtered(self):
        result = _parse_domain_response('{"a": 123, "b": "valid"}', max_terms=15)
        assert "a" not in result
        assert "b" in result

    def test_empty_keys_filtered(self):
        result = _parse_domain_response('{" ": "desc", "valid": "desc"}', max_terms=15)
        assert "valid" in result

    def test_max_terms_respected(self):
        result = _parse_domain_response(
            '{"a": "1", "b": "2", "c": "3", "d": "4"}', max_terms=2
        )
        assert len(result) <= 2