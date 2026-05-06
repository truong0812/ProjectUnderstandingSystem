"""Unit tests for domain glossary plugin system.

Tests cover:
- LogisticsViPlugin: detect_context with various inputs
- DomainPluginRegistry: register, detect_all, detect, unregister
- Deprecated business_glossary backward compatibility
- Summary model metadata field
"""

from __future__ import annotations

import warnings

import pytest

from project_understanding.ingest.domain_plugins.base import DomainGlossaryPlugin
from project_understanding.ingest.domain_plugins.logistics_vi import LogisticsViPlugin
from project_understanding.ingest.domain_plugins import (
    DomainPluginRegistry,
    registry,
)
from project_understanding.models.summaries import Summary, SummaryLevel, SummarySource


# ---------------------------------------------------------------------------
# LogisticsViPlugin
# ---------------------------------------------------------------------------

class TestLogisticsViPlugin:
    """Tests for the LogisticsViPlugin."""

    def setup_method(self):
        self.plugin = LogisticsViPlugin()

    def test_name(self):
        assert self.plugin.name == "logistics_vi"

    def test_description_is_non_empty(self):
        assert len(self.plugin.description) > 0

    def test_detect_cargo_terms(self):
        code = "# Process cargo manifest for shipment"
        result = self.plugin.detect_context(code, max_terms=5)
        assert isinstance(result, dict)
        assert len(result) > 0
        # Should detect "cargo" and "manifest"
        values = "; ".join(result.values())
        assert "hàng hóa" in values.lower() or "Hàng hóa" in values

    def test_detect_multiple_terms(self):
        code = """
        def process_inbound_shipment(awb_number):
            # Process inbound cargo shipment
            manifest = load_manifest(flight_id)
            warehouse.store(cargo)
        """
        result = self.plugin.detect_context(code, max_terms=5)
        assert len(result) > 0

    def test_max_terms_respected(self):
        code = "cargo shipment manifest inbound outbound warehouse ramp"
        for limit in [2, 3, 5]:
            result = self.plugin.detect_context(code, max_terms=limit)
            assert len(result) <= limit, f"Expected <= {limit} terms, got {len(result)}"

    def test_no_terms_found(self):
        code = "def hello_world(): print('hello')"
        result = self.plugin.detect_context(code, max_terms=5)
        assert result == {}

    def test_empty_code(self):
        result = self.plugin.detect_context("", max_terms=5)
        assert result == {}

    def test_case_insensitive_matching(self):
        result_upper = self.plugin.detect_context("CARGO", max_terms=1)
        result_lower = self.plugin.detect_context("cargo", max_terms=1)
        assert len(result_upper) > 0
        assert len(result_lower) > 0

    def test_returns_dict_not_string(self):
        """Plugin returns dict, not a formatted string."""
        code = "cargo shipment"
        result = self.plugin.detect_context(code, max_terms=5)
        assert isinstance(result, dict)
        for key, val in result.items():
            assert isinstance(key, str)
            assert isinstance(val, str)


# ---------------------------------------------------------------------------
# DomainPluginRegistry
# ---------------------------------------------------------------------------

class TestDomainPluginRegistry:
    """Tests for the DomainPluginRegistry."""

    def setup_method(self):
        self.reg = DomainPluginRegistry()
        self.reg.register(LogisticsViPlugin())

    def test_register_and_get(self):
        plugin = self.reg.get("logistics_vi")
        assert plugin is not None
        assert isinstance(plugin, LogisticsViPlugin)

    def test_get_nonexistent(self):
        assert self.reg.get("nonexistent") is None

    def test_unregister(self):
        self.reg.unregister("logistics_vi")
        assert self.reg.get("logistics_vi") is None

    def test_unregister_nonexistent_no_error(self):
        self.reg.unregister("nonexistent")  # Should not raise

    def test_plugins_property(self):
        plugins = self.reg.plugins
        assert "logistics_vi" in plugins
        # Verify it's a copy
        plugins.clear()
        assert "logistics_vi" in self.reg.plugins

    def test_detect_all(self):
        code = "# Handle cargo shipment in warehouse"
        result = self.reg.detect_all(code, max_terms=3)
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_detect_all_no_plugins(self):
        empty_reg = DomainPluginRegistry()
        result = empty_reg.detect_all("cargo", max_terms=5)
        assert result == {}

    def test_detect_specific_plugin(self):
        code = "cargo shipment"
        result = self.reg.detect(code, plugin_name="logistics_vi", max_terms=5)
        assert len(result) > 0

    def test_detect_nonexistent_plugin_raises(self):
        with pytest.raises(KeyError, match="not registered"):
            self.reg.detect("code", plugin_name="nonexistent")

    def test_detect_all_respects_max_terms(self):
        code = "cargo shipment manifest inbound outbound warehouse ramp flight"
        result = self.reg.detect_all(code, max_terms=2)
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

class TestGlobalRegistry:
    """Tests for the global registry instance — starts empty by default."""

    def setup_method(self):
        """Save and clear global registry state for each test."""
        self._saved = dict(registry.plugins)
        for name in list(registry.plugins.keys()):
            registry.unregister(name)

    def teardown_method(self):
        """Restore global registry state after each test."""
        for name in list(registry.plugins.keys()):
            registry.unregister(name)
        for name, plugin in self._saved.items():
            if registry.get(name) is None:
                registry.register(plugin)

    def test_global_registry_starts_empty(self):
        """Global registry should start with no plugins registered."""
        assert len(registry.plugins) == 0

    def test_global_registry_detect_returns_empty(self):
        """With no plugins, detect_all should return empty dict."""
        result = registry.detect_all("cargo", max_terms=3)
        assert result == {}

    def test_can_register_logistics_plugin(self):
        """LogisticsViPlugin can be registered on-demand."""
        from project_understanding.ingest.domain_plugins import BUILTIN_PLUGINS
        plugin_cls = BUILTIN_PLUGINS.get("logistics_vi")
        assert plugin_cls is not None
        registry.register(plugin_cls())
        assert registry.get("logistics_vi") is not None
        result = registry.detect_all("cargo shipment", max_terms=3)
        assert len(result) > 0

    def test_builtin_plugins_catalog_has_logistics(self):
        """BUILTIN_PLUGINS catalog should contain logistics_vi."""
        from project_understanding.ingest.domain_plugins import BUILTIN_PLUGINS
        assert "logistics_vi" in BUILTIN_PLUGINS


# ---------------------------------------------------------------------------
# Custom plugin for extensibility
# ---------------------------------------------------------------------------

class FakeHealthcarePlugin(DomainGlossaryPlugin):
    """Example custom plugin for testing extensibility."""

    @property
    def name(self) -> str:
        return "healthcare_en"

    @property
    def description(self) -> str:
        return "Healthcare domain (English)"

    def detect_context(self, code: str, max_terms: int = 5) -> dict[str, str]:
        terms = {
            "patient": "Patient record",
            "diagnosis": "Medical diagnosis",
            "prescription": "Prescription medication",
        }
        found = {}
        for term, desc in terms.items():
            if term in code.lower():
                found[term] = desc
                if len(found) >= max_terms:
                    break
        return found


class TestCustomPlugin:
    """Tests to verify the plugin system is extensible."""

    def test_register_custom_plugin(self):
        reg = DomainPluginRegistry()
        reg.register(FakeHealthcarePlugin())
        assert reg.get("healthcare_en") is not None

    def test_detect_with_custom_plugin(self):
        reg = DomainPluginRegistry()
        reg.register(FakeHealthcarePlugin())
        result = reg.detect_all("patient diagnosis code", max_terms=5)
        assert "patient" in result
        assert "diagnosis" in result

    def test_multiple_plugins(self):
        reg = DomainPluginRegistry()
        reg.register(LogisticsViPlugin())
        reg.register(FakeHealthcarePlugin())
        # Both plugins should be available
        assert len(reg.plugins) == 2
        # Cargo term detected
        cargo_result = reg.detect_all("cargo shipment", max_terms=3)
        assert len(cargo_result) > 0
        # Healthcare term detected
        health_result = reg.detect("patient diagnosis", plugin_name="healthcare_en", max_terms=3)
        assert len(health_result) > 0


# ---------------------------------------------------------------------------
# Deprecated business_glossary backward compatibility
# ---------------------------------------------------------------------------

class TestDeprecatedBusinessGlossary:
    """Test the backward-compatible shim."""

    def test_detect_business_context_emits_deprecation_warning(self):
        from project_understanding.ingest.business_glossary import detect_business_context
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = detect_business_context("cargo shipment", max_terms=3)
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()

    def test_detect_business_context_returns_string(self):
        from project_understanding.ingest.business_glossary import detect_business_context
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = detect_business_context("cargo shipment", max_terms=3)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_detect_business_context_empty(self):
        from project_understanding.ingest.business_glossary import detect_business_context
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = detect_business_context("hello world", max_terms=3)
            assert result == ""


# ---------------------------------------------------------------------------
# Summary model with metadata
# ---------------------------------------------------------------------------

class TestSummaryMetadata:
    """Tests for the updated Summary model with metadata field."""

    def test_metadata_default_empty_dict(self):
        s = Summary(
            summary_id="abc",
            target_id="file:1",
            target_type="file",
            content="Test",
            level=SummaryLevel.FILE,
        )
        assert s.metadata == {}

    def test_metadata_with_domain_context(self):
        s = Summary(
            summary_id="abc",
            target_id="file:1",
            target_type="file",
            content="Test",
            level=SummaryLevel.FILE,
            metadata={"cargo": "Hàng hóa vận chuyển", "shipment": "Lô hàng"},
        )
        assert "cargo" in s.metadata
        assert s.metadata["cargo"] == "Hàng hóa vận chuyển"

    def test_no_business_context_field(self):
        """Verify business_context field is removed."""
        s = Summary(
            summary_id="abc",
            target_id="file:1",
            target_type="file",
            content="Test",
            level=SummaryLevel.FILE,
        )
        assert not hasattr(s, "business_context")

    def test_serialization_roundtrip(self):
        s = Summary(
            summary_id="abc",
            target_id="file:1",
            target_type="file",
            content="Test summary",
            level=SummaryLevel.FILE,
            generated_by=SummarySource.HEURISTIC,
            language="python",
            metadata={"key1": "val1"},
        )
        data = s.model_dump()
        s2 = Summary.model_validate(data)
        assert s2.metadata == {"key1": "val1"}
        assert s2.summary_id == "abc"