"""Language detection for source code files.

Uses file extension mapping and content heuristics to identify programming languages.
"""

from __future__ import annotations

from pathlib import Path

from project_understanding.config import LANGUAGE_MAP, SUPPORTED_LANGUAGES


def detect_language(file_path: str, extension: str = "") -> str:
    """Detect the programming language of a file.

    Args:
        file_path: Relative file path.
        extension: File extension (e.g., '.py'). Computed if empty.

    Returns:
        Language name (e.g., 'python', 'typescript', 'unknown').
    """
    if not extension:
        extension = Path(file_path).suffix.lower()

    language = LANGUAGE_MAP.get(extension, "unknown")
    return language


def is_supported_language(language: str) -> bool:
    """Check if the language has a tree-sitter parser available."""
    return language in SUPPORTED_LANGUAGES


def is_source_file(file_path: str, extension: str = "") -> bool:
    """Check if a file is a source code file (not config/data/markup).

    Args:
        file_path: Relative file path.
        extension: File extension. Computed if empty.

    Returns:
        True if the file is likely a source code file.
    """
    if not extension:
        extension = Path(file_path).suffix.lower()

    # Known source code extensions
    source_extensions = set(LANGUAGE_MAP.keys())
    return extension in source_extensions


def detect_entrypoint(file_path: str, language: str) -> bool:
    """Heuristic to detect if a file is an entry point.

    Args:
        file_path: Relative file path.
        language: Detected programming language.

    Returns:
        True if the file is likely an entry point.
    """
    name = Path(file_path).name.lower()
    parent = Path(file_path).parent.name.lower()

    entrypoint_patterns = {
        "python": {"main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "__main__.py", "run.py", "server.py"},
        "typescript": {"main.ts", "index.ts", "app.ts", "server.ts", "main.tsx", "index.tsx", "app.tsx"},
        "javascript": {"main.js", "index.js", "app.js", "server.js", "main.jsx", "index.jsx", "app.jsx"},
        "c_sharp": {"program.cs", "startup.cs"},
    }

    patterns = entrypoint_patterns.get(language, set())
    return name in patterns


def detect_test_file(file_path: str) -> bool:
    """Heuristic to detect if a file is a test file.

    Args:
        file_path: Relative file path.

    Returns:
        True if the file is likely a test file.
    """
    path_lower = file_path.lower()
    parts = Path(path_lower).parts

    # Check directory parts
    test_dirs = {"tests", "test", "__tests__", "spec", "specs"}
    if any(part in test_dirs for part in parts):
        return True

    # Check file name patterns
    name = Path(path_lower).stem
    test_prefixes = ("test_", "tests_", "spec_", "specs_")
    test_suffixes = ("_test", "_tests", "_spec", "_specs")

    if name.startswith(test_prefixes) or name.endswith(test_suffixes):
        return True

    # C# convention: *Test.cs, *Tests.cs, *Spec.cs
    if name.endswith("test") or name.endswith("tests") or name.endswith("spec"):
        return True

    return False


def detect_config_file(file_path: str) -> bool:
    """Heuristic to detect if a file is a config file.

    Args:
        file_path: Relative file path.

    Returns:
        True if the file is likely a config file.
    """
    name = Path(file_path).name.lower()
    config_patterns = {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "tox.ini",
        "requirements.txt",
        "pip.conf",
        ".env",
        ".env.local",
        "tsconfig.json",
        "package.json",
        ".eslintrc",
        ".prettierrc",
        "web.config",
        "app.config",
        "appsettings.json",
        "nuget.config",
        ".editorconfig",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "makefile",
        "cmakelists.txt",
    }
    return name in config_patterns