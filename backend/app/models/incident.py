from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    status: str
    severity: str
    reason: str

    service_name: str = "simulated-api-service"

    request_rate: float | None = None
    error_rate: float | None = None
    p95_latency_seconds: float | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )