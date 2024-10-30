from typing import Literal, Optional
from pydantic import BaseModel, Field

class BaseEvent(BaseModel):
    event : str
    origin : Optional[str] = None

class BaseError(BaseEvent):
    event : Literal["error"] = "error"

    error_type : str
    error_message : Optional[str] = Field(default=None)

__all__ = [
    BaseEvent,
    BaseError
]