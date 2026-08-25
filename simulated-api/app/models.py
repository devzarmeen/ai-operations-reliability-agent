from datetime import datetime

from pydantic import BaseModel


class OperationEvent(BaseModel):
    event_id: str
    timestamp: datetime
    service: str
    operation: str
    status: str
    latency_ms: float
    error_message: str | None = None