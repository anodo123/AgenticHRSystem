"""FastAPI API dependencies."""

from app.db.session import get_db
from app.core.config import get_settings

__all__ = ["get_db", "get_settings"]
