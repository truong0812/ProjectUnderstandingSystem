"""Convention and RiskArea models for the shared knowledge schema.

Conventions describe patterns and practices found in the codebase.
RiskAreas identify sensitive regions requiring extra attention.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConventionType(str, Enum):
    """Types of detected conventions."""

    NAMING_PATTERN = "naming_pattern"
    MODULE_STRUCTURE = "module_structure"
    DEPENDENCY_DIRECTION = "dependency_direction"
    SERVICE_REPOSITORY_PATTERN = "service_repository_pattern"
    ERROR_HANDLING = "error_handling"
    CONFIG_ORGANIZATION = "config_organization"
    ENTRYPOINT_PATTERN = "entrypoint_pattern"
    LAYERED_ARCHITECTURE = "layered_architecture"


class RiskCategory(str, Enum):
    """Categories of risk areas."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE_WRITE = "database_write"
    TRANSACTION = "transaction"
    CACHE = "cache"
    QUEUE = "queue"
    FILE_SYSTEM_WRITE = "file_system_write"
    EXTERNAL_API = "external_api"
    MIGRATION = "migration"
    CONFIG_SECRETS = "config_secrets"
    SECURITY_SENSITIVE = "security_sensitive"


class Convention(BaseModel):
    """A detected convention or pattern in the codebase.

    Conventions describe structural or behavioral patterns that
    the codebase follows, helping agents understand project norms.
    """

    convention_id: str = Field(description="Unique convention identifier")
    convention_type: ConventionType = Field(description="Type of convention")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Description of the convention")
    evidence: list[str] = Field(
        default_factory=list,
        description="File paths or symbols that follow this convention",
    )
    confidence: float = Field(
        default=1.0,
        description="Detection confidence 0-1",
    )
    affected_files: list[str] = Field(
        default_factory=list,
        description="File paths affected by this convention",
    )
    affected_symbols: list[str] = Field(
        default_factory=list,
        description="Symbol IDs affected by this convention",
    )


class RiskArea(BaseModel):
    """A detected risk area in the codebase.

    Risk areas identify sensitive regions that require extra
    attention during code review or development.
    """

    risk_id: str = Field(description="Unique risk identifier")
    category: RiskCategory = Field(description="Risk category")
    name: str = Field(description="Human-readable name")
    description: str = Field(description="Why this area is risky")
    file_path: str = Field(description="File path of the risk area")
    symbol_name: str | None = Field(
        default=None,
        description="Symbol name if applicable",
    )
    line_range: tuple[int, int] | None = Field(
        default=None,
        description="Line range if applicable",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting this risk classification",
    )
    confidence: float = Field(
        default=1.0,
        description="Detection confidence 0-1",
    )
    severity: str = Field(
        default="medium",
        description="Severity: low, medium, high",
    )