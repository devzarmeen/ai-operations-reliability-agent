from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class AlertRecord(SQLModel, table=True):
    __tablename__ = "alert_records"

    id: int | None = Field(default=None, primary_key=True)
    fingerprint: str = Field(index=True)
    alert_name: str
    service_name: str
    status: str
    severity: str
    payload_summary: str | None = None
    investigation_id: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
