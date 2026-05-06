"""LLM-based business domain detection.

Analyzes code samples to automatically identify the business domain
of a project using LLM. Returns a dictionary of domain terms and
their descriptions — works with ANY domain, no predefined catalog needed.

This is called ONCE per ingestion pipeline run (1 LLM call total),
and the result is shared across all file summaries.
"""

from __future__ import annotations

import json
import logging
import re

from project_understanding.adapters.llm_base import LLMProvider

logger = logging.getLogger(__name__)

_DOMAIN_DETECTION_SYSTEM_PROMPT = """You are a business domain analyst. \
Analyze the provided code samples and identify the BUSINESS domain of this project.

Return ONLY a valid JSON object mapping key domain-specific terms to brief descriptions.
Rules:
- Include ONLY business/domain-specific terms, NOT programming concepts
- Use 5-15 terms maximum
- Write descriptions in the SAME LANGUAGE as the code comments and identifiers
- Focus on terms that help a developer understand the business context
- Example output: {"shipment": "Lô hàng vận chuyển", "warehouse": "Kho hàng chứa hàng hóa"}

If the code is generic (no clear business domain), return an empty JSON object: {}"""

_MAX_CHARS_PER_SAMPLE = 500
_MAX_SAMPLES = 10
_MAX_TERMS_DEFAULT = 15


def detect_domain_llm(
    code_samples: list[str],
    llm: LLMProvider,
    max_terms: int = _MAX_TERMS_DEFAULT,
) -> dict[str, str]:
    """Detect business domain from code samples using LLM.

    Makes exactly 1 LLM call to identify the business domain.
    Falls back gracefully to empty dict on any error.

    Args:
        code_samples: List of file contents to analyze.
        llm: LLM provider instance.
        max_terms: Maximum number of domain terms to extract.

    Returns:
        Dictionary mapping domain terms to their descriptions.
        Empty dict if detection fails or domain is generic.
    """
    if not code_samples:
        return {}

    # Prepare condensed code samples
    condensed = _condense_samples(code_samples)
    if not condensed.strip():
        return {}

    prompt = f"""Analyze these code samples from a project and identify the business domain:

```
{condensed}
```

Return a JSON object of key domain terms (max {max_terms} terms)."""

    try:
        response = llm.generate(prompt=prompt, system=_DOMAIN_DETECTION_SYSTEM_PROMPT)
        return _parse_domain_response(response, max_terms)
    except Exception as e:
        logger.warning("Domain detection failed: %s", e)
        return {}


def _condense_samples(samples: list[str]) -> str:
    """Condense code samples into a manageable size for LLM input.

    Takes first N samples, truncates each to max chars,
    and joins them with separators.
    """
    parts: list[str] = []
    for sample in samples[:_MAX_SAMPLES]:
        trimmed = sample.strip()
        if not trimmed:
            continue
        if len(trimmed) > _MAX_CHARS_PER_SAMPLE:
            trimmed = trimmed[:_MAX_CHARS_PER_SAMPLE] + "\n... (truncated)"
        parts.append(trimmed)

    return "\n\n---\n\n".join(parts)


def _parse_domain_response(response: str, max_terms: int) -> dict[str, str]:
    """Parse LLM response into domain term dictionary.

    Handles various response formats:
    - Pure JSON object
    - JSON wrapped in markdown code block
    - JSON with extra text before/after
    """
    if not response or not response.strip():
        return {}

    # Try to extract JSON from markdown code block
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find JSON object directly
        brace_match = re.search(r"\{.*\}", response, re.DOTALL)
        if brace_match:
            json_str = brace_match.group(0)
        else:
            json_str = response.strip()

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        logger.warning("Failed to parse domain detection response as JSON")
        return {}

    # Validate and clean
    if not isinstance(parsed, dict):
        return {}

    result: dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(key, str) and isinstance(value, str) and key.strip():
            result[key.strip()] = value.strip()
            if len(result) >= max_terms:
                break

    return result