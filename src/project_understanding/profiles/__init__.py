"""Agent profiles — configure how agents query the knowledge base."""

from project_understanding.profiles.models import AgentProfile, RankingMode
from project_understanding.profiles.registry import ProfileRegistry, get_default_profiles

__all__ = ["AgentProfile", "RankingMode", "ProfileRegistry", "get_default_profiles"]