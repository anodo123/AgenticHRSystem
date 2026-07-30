"""Adapter serialization utilities."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


def serialize(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def model_dict(model, fields: tuple[str, ...]) -> dict:
    return {field: serialize(getattr(model, field)) for field in fields}
