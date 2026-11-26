from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standardized API response envelope."""
    success: bool
    message: str
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """Standardized error response envelope."""
    success: bool = False
    message: str
    data: Optional[Any] = None
