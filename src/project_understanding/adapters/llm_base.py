"""Abstract LLM provider interface."""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """Interface for LLM providers."""

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from a prompt.

        Args:
            prompt: User prompt.
            system: Optional system prompt.

        Returns:
            Generated text.
        """
        ...