"""HR system adapter contracts and implementations."""
from app.adapters.base import AdapterResult, BaseHRAdapter
from app.adapters.factory import AdapterFactory

__all__ = ["AdapterFactory", "AdapterResult", "BaseHRAdapter"]
