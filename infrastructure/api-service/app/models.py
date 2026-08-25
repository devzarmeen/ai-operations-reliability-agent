from pydantic import BaseModel
from datetime import datetime


class OperationEvent(BaseModel):
    event_id: str
    timestamp: datetime
    service: str
    operation: str
    status: str
    latency_ms: float
    error_message: str | None = None