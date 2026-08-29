"""Common finding schema shared by all scanner parsers (SRS FR-12, S5.2)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Category(str, Enum):
    SECRET = "secret"
    CODE = "code"
    CONTAINER = "container"


@dataclass(frozen=True)
class Finding:
    tool: str
    category: Category
    severity: Severity
    location: str
    description: str
