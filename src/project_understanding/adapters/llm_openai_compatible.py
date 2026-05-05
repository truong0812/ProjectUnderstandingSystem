"""Unified OpenAI-compatible LLM adapter.

Works with OpenAI, NVIDIA NIM, and Groq since they all share
the OpenAI API format.
"""

from __future__ import annotations

import os

from openai import OpenAI

from project_understanding.config import PROVIDER_PRESETS, get_settings


class OpenAICompatibleLLM:
    """LLM provider using OpenAI-compatible API.

    Supports OpenAI, NVIDIA NIM, and Groq by changing base_url.
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the LLM adapter.

        Args:
            provider: Provider name (openai, nvidia, groq). Uses config default if None.
            model: Model name. Uses config default if None.
            api_key: API key override. Uses env/config if None.
        """
        settings = get_settings()
        self._provider = provider or settings.llm_provider
        self._model = model or settings.llm_model

        if self._provider not in PROVIDER_PRESETS:
            raise ValueError(
                f"Unknown provider: {self._provider}. "
                f"Supported: {list(PROVIDER_PRESETS.keys())}"
            )

        base_url, api_key_env = PROVIDER_PRESETS[self._provider]

        if api_key:
            self._api_key = api_key
        else:
            self._api_key = os.environ.get(api_key_env, getattr(settings, api_key_env.lower(), ""))

        self._base_url = base_url
        self._client = OpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
        )

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from a prompt.

        Args:
            prompt: User prompt.
            system: Optional system prompt.

        Returns:
            Generated text.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
                max_tokens=1024,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[LLM Error: {e}]"

    @property
    def provider(self) -> str:
        """Current provider name."""
        return self._provider

    @property
    def model(self) -> str:
        """Current model name."""
        return self._model