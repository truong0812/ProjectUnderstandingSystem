"""Global configuration for Project Understanding System."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class LLMProviderConfig(BaseSettings):
    """LLM provider configuration loaded from environment variables."""

    # Provider selection: openai, nvidia, groq
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

    # API keys
    openai_api_key: str = ""
    nvidia_api_key: str = ""
    groq_api_key: str = ""

    # Embedding config
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    # Qdrant config
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Project config
    snapshot_output_dir: str = "./output"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Provider presets: name -> (base_url, api_key_env_var)
PROVIDER_PRESETS: dict[str, tuple[str, str]] = {
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}


def get_settings() -> LLMProviderConfig:
    """Load and return settings from .env file."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        return LLMProviderConfig(_env_file=str(env_path))  # type: ignore[call-arg]
    return LLMProviderConfig()


def get_llm_config(provider: str | None = None) -> tuple[str, str, str]:
    """Get LLM connection details: (base_url, api_key, model).

    Args:
        provider: Override provider name. If None, uses config default.

    Returns:
        Tuple of (base_url, api_key, model).
    """
    settings = get_settings()
    provider = provider or settings.llm_provider
    model = settings.llm_model

    if provider not in PROVIDER_PRESETS:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Supported: {list(PROVIDER_PRESETS.keys())}"
        )

    base_url, api_key_env = PROVIDER_PRESETS[provider]
    api_key = os.environ.get(api_key_env, getattr(settings, api_key_env.lower(), ""))

    return base_url, api_key, model


# Default skip patterns for repository scanning
DEFAULT_SKIP_PATTERNS: list[str] = [
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "eggs",
    "*.egg-info",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    "*.min.js",
    "*.min.css",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    ".DS_Store",
    "Thumbs.db",
]

# Language detection mapping: extension -> language name
LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".cs": "c_sharp",
    ".csx": "c_sharp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
}

# Languages supported by tree-sitter parsers in this project
SUPPORTED_LANGUAGES: set[str] = {"python", "typescript", "c_sharp"}