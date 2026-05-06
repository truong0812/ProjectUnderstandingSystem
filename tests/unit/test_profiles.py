"""Unit tests for agent profiles."""

from project_understanding.profiles.models import AgentProfile, RankingMode
from project_understanding.profiles.registry import get_default_profiles, ProfileRegistry


class TestAgentProfile:
    """Tests for AgentProfile model."""

    def test_default_profile_creation(self):
        """Profile should be created with correct defaults."""
        p = AgentProfile(
            name="test-agent",
            preferred_entities=["File", "Symbol"],
            preferred_relations=["imports", "calls"],
        )
        assert p.name == "test-agent"
        assert p.include_conventions is False
        assert p.include_risks is False
        assert p.include_related_files is True
        assert p.max_items == 50
        assert p.ranking_mode == RankingMode.RELEVANCE

    def test_ranking_modes(self):
        """Ranking modes should have expected values."""
        assert RankingMode.RELEVANCE.value == "relevance"
        assert RankingMode.DEPENDENCY_DEPTH.value == "dependency_depth"
        assert RankingMode.BREADTH_FIRST.value == "breadth_first"

    def test_profile_serialization(self):
        """Profile should serialize to dict correctly."""
        p = AgentProfile(
            name="test-agent",
            preferred_entities=["File"],
            preferred_relations=["imports"],
        )
        d = p.model_dump()
        assert d["name"] == "test-agent"
        assert "File" in d["preferred_entities"]


class TestProfileRegistry:
    """Tests for profile registry."""

    def test_get_default_profiles(self):
        """Should return 3 default profiles."""
        profiles = get_default_profiles()
        assert len(profiles) >= 3
        names = list(profiles.keys())
        assert "review-agent" in names
        assert "dev-agent" in names
        assert "doc-agent" in names

    def test_get_review_agent(self):
        """Should get review-agent profile."""
        profiles = get_default_profiles()
        p = profiles["review-agent"]
        assert p.name == "review-agent"
        assert "imports" in p.preferred_relations
        assert p.include_risks is True
        assert p.include_conventions is True

    def test_get_dev_agent(self):
        """Should get dev-agent profile."""
        profiles = get_default_profiles()
        p = profiles["dev-agent"]
        assert p.name == "dev-agent"
        assert p.include_risks is False

    def test_get_doc_agent(self):
        """Should get doc-agent profile."""
        profiles = get_default_profiles()
        p = profiles["doc-agent"]
        assert p.name == "doc-agent"
        assert p.semantic_search_enabled is True

    def test_registry_get_nonexistent(self):
        """Should return None for nonexistent profile."""
        registry = ProfileRegistry()
        p = registry.get("nonexistent-agent")
        assert p is None

    def test_registry_list_profiles(self):
        """Should list profile names."""
        registry = ProfileRegistry()
        names = registry.list_profiles()
        assert isinstance(names, list)
