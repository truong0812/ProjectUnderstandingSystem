"""Profile registry — manages agent profiles with built-in defaults."""

from __future__ import annotations

from pathlib import Path

from project_understanding.profiles.models import AgentProfile, RankingMode


def get_default_profiles() -> dict[str, AgentProfile]:
    """Return the 3 built-in default profiles for MVP."""
    return {
        "review-agent": AgentProfile(
            name="review-agent",
            preferred_entities=["File", "Symbol", "Relation"],
            preferred_relations=["imports", "calls", "depends_on"],
            include_conventions=True,
            include_risks=True,
            include_related_files=True,
            max_items=50,
            ranking_mode=RankingMode.DEPENDENCY_DEPTH,
            summary_levels=["file"],
            semantic_search_enabled=False,
        ),
        "dev-agent": AgentProfile(
            name="dev-agent",
            preferred_entities=["Module", "Symbol", "File"],
            preferred_relations=["contains", "imports", "depends_on", "inherits"],
            include_conventions=True,
            include_risks=False,
            include_related_files=True,
            max_items=100,
            ranking_mode=RankingMode.BREADTH_FIRST,
            summary_levels=["file"],
            semantic_search_enabled=False,
        ),
        "doc-agent": AgentProfile(
            name="doc-agent",
            preferred_entities=["Module", "File", "Symbol"],
            preferred_relations=["contains", "imports"],
            include_conventions=True,
            include_risks=False,
            include_related_files=False,
            max_items=80,
            ranking_mode=RankingMode.RELEVANCE,
            summary_levels=["file"],
            semantic_search_enabled=True,
        ),
    }


class ProfileRegistry:
    """Manages agent profiles — loads from disk and provides defaults."""

    def __init__(self, profiles_dir: str | Path | None = None) -> None:
        """Initialize the registry.

        Args:
            profiles_dir: Optional directory to load/save YAML profiles.
        """
        self._profiles_dir = Path(profiles_dir) if profiles_dir else None
        self._cache: dict[str, AgentProfile] = {}

    def get(self, name: str) -> AgentProfile | None:
        """Get a profile by name.

        Lookup order:
        1. Cache
        2. YAML file in profiles_dir
        3. Built-in defaults

        Args:
            name: Profile name.

        Returns:
            AgentProfile or None if not found.
        """
        # Check cache
        if name in self._cache:
            return self._cache[name]

        # Check YAML file
        if self._profiles_dir:
            yaml_path = self._profiles_dir / f"{name}.yaml"
            if yaml_path.exists():
                profile = AgentProfile.from_yaml(yaml_path)
                self._cache[name] = profile
                return profile

        # Check defaults
        defaults = get_default_profiles()
        if name in defaults:
            self._cache[name] = defaults[name]
            return defaults[name]

        return None

    def list_profiles(self) -> list[str]:
        """List all available profile names."""
        names = set(get_default_profiles().keys())

        if self._profiles_dir and self._profiles_dir.is_dir():
            for f in self._profiles_dir.iterdir():
                if f.suffix in (".yaml", ".yml"):
                    names.add(f.stem)

        return sorted(names)

    def save_profile(self, profile: AgentProfile) -> Path:
        """Save a profile to disk.

        Args:
            profile: Profile to save.

        Returns:
            Path to the saved file.
        """
        if not self._profiles_dir:
            raise ValueError("No profiles directory configured")

        path = self._profiles_dir / f"{profile.name}.yaml"
        profile.to_yaml(path)
        self._cache[profile.name] = profile
        return path