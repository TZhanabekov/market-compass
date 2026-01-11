"""Common schemas used across the API."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Structured error detail."""

    code: str
    message: str
    detail: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response format.

    Format: { "error": { "code": str, "message": str, "detail": object } }
    """

    error: ErrorDetail
