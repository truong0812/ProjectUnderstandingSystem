"""Unit tests for entity models."""

import pytest

from project_understanding.models.entities import File, Module, Symbol, SymbolKind
from project_understanding.models.relations import Relation, RelationType
from project_understanding.models.summaries import Summary, SummaryLevel, SummarySource
from project_understanding.models.conventions import Convention, RiskArea, ConventionType, RiskCategory


class TestFile:
    """Tests for File entity."""

    def test_make_file_id_deterministic(self):
        """File ID should be deterministic for same inputs."""
        id1 = File.make_file_id("repo1", "src/main.py", "abc123")
        id2 = File.make_file_id("repo1", "src/main.py", "abc123")
        assert id1 == id2

    def test_make_file_id_different_for_different_paths(self):
        """File ID should differ for different paths."""
        id1 = File.make_file_id("repo1", "src/main.py", "abc123")
        id2 = File.make_file_id("repo1", "src/utils.py", "abc123")
        assert id1 != id2

    def test_file_creation(self):
        """File entity should be created with correct fields."""
        f = File(
            file_id="fid1",
            snapshot_id="sid1",
            path="src/main.py",
            language="python",
            hash="abc123",
            size=100,
        )
        assert f.path == "src/main.py"
        assert f.language == "python"
        assert f.is_entrypoint is False
        assert f.is_test is False
        assert f.is_config is False


class TestSymbol:
    """Tests for Symbol entity."""

    def test_make_symbol_id_deterministic(self):
        """Symbol ID should be deterministic."""
        id1 = Symbol.make_symbol_id("repo1", "src/main.py", "MyClass.my_method", "h1")
        id2 = Symbol.make_symbol_id("repo1", "src/main.py", "MyClass.my_method", "h1")
        assert id1 == id2

    def test_symbol_kinds(self):
        """Symbol kinds should have expected values."""
        assert SymbolKind.FUNCTION.value == "function"
        assert SymbolKind.CLASS.value == "class"
        assert SymbolKind.METHOD.value == "method"
        assert SymbolKind.INTERFACE.value == "interface"
        assert SymbolKind.TYPE.value == "type"
        assert SymbolKind.CONSTANT.value == "constant"


class TestRelation:
    """Tests for Relation entity."""

    def test_relation_types(self):
        """Relation types should have expected values."""
        assert RelationType.CONTAINS.value == "contains"
        assert RelationType.IMPORTS.value == "imports"
        assert RelationType.CALLS.value == "calls"
        assert RelationType.DEPENDS_ON.value == "depends_on"
        assert RelationType.INHERITS.value == "inherits"
        assert RelationType.IMPLEMENTS.value == "implements"

    def test_relation_creation(self):
        """Relation should be created with correct fields."""
        r = Relation(
            source_id="sid1",
            target_id="tid1",
            relation_type=RelationType.IMPORTS,
            confidence=0.9,
            evidence="import tid1",
        )
        assert r.source_id == "sid1"
        assert r.target_id == "tid1"
        assert r.relation_type == RelationType.IMPORTS
        assert r.confidence == 0.9


class TestSummary:
    """Tests for Summary entity."""

    def test_make_summary_id(self):
        """Summary ID should be deterministic."""
        id1 = Summary.make_summary_id("target1", SummaryLevel.FILE)
        id2 = Summary.make_summary_id("target1", SummaryLevel.FILE)
        assert id1 == id2

    def test_summary_levels(self):
        """Summary levels should have expected values."""
        assert SummaryLevel.FILE.value == "file"
        assert SummaryLevel.SYMBOL.value == "symbol"
        assert SummaryLevel.MODULE.value == "module"

    def test_summary_sources(self):
        """Summary sources should have expected values."""
        assert SummarySource.LLM.value == "llm"
        assert SummarySource.HEURISTIC.value == "heuristic"

    def test_summary_creation(self):
        """Summary should be created with correct fields."""
        s = Summary(
            summary_id="sum1",
            target_id="tid1",
            target_type="file",
            content="A test file",
            level=SummaryLevel.FILE,
            generated_by=SummarySource.HEURISTIC,
            language="python",
        )
        assert s.content == "A test file"
        assert s.generated_by == SummarySource.HEURISTIC


class TestConvention:
    """Tests for Convention entity."""

    def test_convention_types(self):
        """Convention types should have expected values."""
        assert ConventionType.NAMING_PATTERN.value == "naming_pattern"
        assert ConventionType.MODULE_STRUCTURE.value == "module_structure"

    def test_convention_creation(self):
        """Convention should be created with correct fields."""
        c = Convention(
            convention_id="conv1",
            convention_type=ConventionType.NAMING_PATTERN,
            name="CamelCase classes",
            description="Classes use CamelCase naming",
            evidence=["class MyHelper"],
            file_paths=["src/main.py"],
            confidence=0.9,
        )
        assert c.name == "CamelCase classes"
        assert c.confidence == 0.9


class TestRiskArea:
    """Tests for RiskArea entity."""

    def test_risk_categories(self):
        """Risk categories should have expected values."""
        assert RiskCategory.AUTHENTICATION.value == "authentication"
        assert RiskCategory.DATABASE_WRITE.value == "database_write"
        assert RiskCategory.EXTERNAL_API.value == "external_api"

    def test_risk_creation(self):
        """RiskArea should be created with correct fields."""
        r = RiskArea(
            risk_id="risk1",
            category=RiskCategory.AUTHENTICATION,
            name="Login auth",
            description="Authentication logic",
            file_path="src/auth.py",
            evidence=["def login()"],
            confidence=0.9,
            severity="high",
        )
        assert r.category == RiskCategory.AUTHENTICATION
        assert r.severity == "high"