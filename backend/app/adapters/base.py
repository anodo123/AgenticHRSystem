"""Shared HR adapter interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AdapterResult:
    system: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    error: str | None = None
    dry_run: bool = False


class BaseHRAdapter(ABC):
    system: str

    @abstractmethod
    def read(self, db: Session, employee_id: int, **filters) -> AdapterResult:
        """Read employee-scoped data."""

    @abstractmethod
    def write(self, db: Session, employee_id: int, payload: dict[str, Any]) -> AdapterResult:
        """Apply a controlled employee-scoped mutation."""

    @abstractmethod
    def dry_run(self, db: Session, employee_id: int, payload: dict[str, Any]) -> AdapterResult:
        """Validate and preview a mutation without applying it."""

    def health_check(self) -> AdapterResult:
        return AdapterResult(self.system, True, {"status": "healthy", "mode": "mock"})
