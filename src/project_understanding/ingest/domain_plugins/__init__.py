"""Domain glossary plugin registry.

Provides a registry for domain-specific glossary plugins.
Plugins are registered at startup and can be looked up by name.
"""

from __future__ import annotations

from project_understanding.ingest.domain_plugins.base import DomainGlossaryPlugin
from project_understanding.ingest.domain_plugins.logistics_vi import LogisticsViPlugin

__all__ = ["DomainGlossaryPlugin", "DomainPluginRegistry", "registry"]

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class DomainPluginRegistry:
    """Registry for domain glossary plugins.

    Usage:
        # Get the default global registry
        reg = registry

        # Register a plugin
        reg.register(LogisticsViPlugin())

        # Detect context using all registered plugins
        metadata = reg.detect_all(code, max_terms=5)

        # Detect context using a specific plugin
        metadata = reg.detect(code, plugin_name="logistics_vi")
    """

    def __init__(self) -> None:
        self._plugins: dict[str, DomainGlossaryPlugin] = {}

    def register(self, plugin: DomainGlossaryPlugin) -> None:
        """Register a domain glossary plugin."""
        self._plugins[plugin.name] = plugin

    def unregister(self, name: str) -> None:
        """Remove a registered plugin by name."""
        self._plugins.pop(name, None)

    def get(self, name: str) -> DomainGlossaryPlugin | None:
        """Get a plugin by name, or None if not registered."""
        return self._plugins.get(name)

    @property
    def plugins(self) -> dict[str, DomainGlossaryPlugin]:
        """Return a copy of the registered plugins mapping."""
        return dict(self._plugins)

    def detect_all(self, code: str, max_terms: int = 5) -> dict[str, str]:
        """Run detection across all registered plugins and merge results.

        Args:
            code: Source code or file content to analyze.
            max_terms: Maximum total terms across all plugins.

        Returns:
            Merged dict of term → description from all plugins.
        """
        merged: dict[str, str] = {}
        for plugin in self._plugins.values():
            result = plugin.detect_context(code, max_terms=max_terms)
            merged.update(result)
            if len(merged) >= max_terms:
                break
        # Trim to max_terms
        if len(merged) > max_terms:
            merged = dict(list(merged.items())[:max_terms])
        return merged

    def detect(self, code: str, *, plugin_name: str, max_terms: int = 5) -> dict[str, str]:
        """Run detection using a specific plugin.

        Args:
            code: Source code or file content to analyze.
            plugin_name: Name of the plugin to use.
            max_terms: Maximum number of terms.

        Returns:
            Dict of term → description from the specified plugin.

        Raises:
            KeyError: If the plugin is not registered.
        """
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            raise KeyError(f"Plugin '{plugin_name}' not registered. Available: {list(self._plugins)}")
        return plugin.detect_context(code, max_terms=max_terms)


# ---------------------------------------------------------------------------
# Global registry — starts empty, plugins registered on-demand
# ---------------------------------------------------------------------------

registry = DomainPluginRegistry()

# Catalog of built-in plugins available for manual registration
BUILTIN_PLUGINS: dict[str, type[DomainGlossaryPlugin]] = {
    "logistics_vi": LogisticsViPlugin,
}
