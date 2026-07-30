"""Data freshness validation and refresh coordination."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from app.adapters.base import AdapterResult
from app.core.config import get_settings


@dataclass(frozen=True)
class FreshnessResult:
    fresh: bool
    age_seconds: float
    refreshed: bool
    result: AdapterResult


class FreshnessGate:
    @staticmethod
    def evaluate(result: AdapterResult, max_age_minutes: int | None = None) -> FreshnessResult:
        max_age_minutes = max_age_minutes or get_settings().data_freshness_max_age_minutes
        age = max(0.0, (datetime.utcnow() - result.fetched_at).total_seconds())
        return FreshnessResult(
            fresh=result.success and age <= timedelta(minutes=max_age_minutes).total_seconds(),
            age_seconds=age,
            refreshed=False,
            result=result,
        )

    @classmethod
    def ensure(
        cls,
        result: AdapterResult,
        refresher: Callable[[], AdapterResult],
        max_age_minutes: int | None = None,
    ) -> FreshnessResult:
        evaluation = cls.evaluate(result, max_age_minutes)
        if evaluation.fresh:
            return evaluation
        refreshed = refresher()
        checked = cls.evaluate(refreshed, max_age_minutes)
        return FreshnessResult(checked.fresh, checked.age_seconds, True, refreshed)
