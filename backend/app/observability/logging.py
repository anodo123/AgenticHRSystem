"""Structured JSON logging with request correlation context."""
from contextvars import ContextVar
from datetime import datetime
import json
import logging
import sys


correlation_id_context: ContextVar[str] = ContextVar(
    "correlation_id", default="no-correlation-id"
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_context.get(),
        }
        for key in ("event_type", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]


def set_correlation_id(value: str):
    return correlation_id_context.set(value)


def reset_correlation_id(token) -> None:
    correlation_id_context.reset(token)
