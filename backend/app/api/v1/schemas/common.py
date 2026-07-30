"""Response schemas."""
from pydantic import BaseModel
from typing import Any, Optional


class ResponseMessage(BaseModel):
    """Generic response message."""

    success: bool
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response."""

    success: bool = False
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
