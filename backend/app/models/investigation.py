from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Investigation(SQLModel, table=True):
    __tablename__ = "investigations"

    id: int | None = Field(default=None, primary_key=True)
    incident_id: int | None = Field(default=None, index=True)
    alert_id: str | None = None
    service_name: str = "simulated-api-service"
    stage: str = "INVESTIGATING"
    status: str = "INVESTIGATING"
    likely_cause: str | None = None
    confidence: float | None = None
    recommended_action: str | None = None
    recommended_action_type: str | None = None
    approval_required: bool = False
    approval_status: str = "not_required"
    diagnosis: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InvestigationEvent(SQLModel, table=True):
    __tablename__ = "investigation_events"

    id: int | None = Field(default=None, primary_key=True)
    investigation_id: int = Field(index=True)
    incident_id: int | None = Field(default=None, index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    tool_name: str | None = None
    tool_input: str | None = None
    tool_result_summary: str | None = None
    hypothesis: str | None = None
    hypothesis_status: str | None = None
    evidence: str | None = None
    decision: str | None = None
    confidence: float | None = None
    details: str | None = None


class ApprovalRequest(SQLModel, table=True):
    __tablename__ = "approval_requests"

    id: int | None = Field(default=None, primary_key=True)
    investigation_id: int = Field(index=True)
    incident_id: int | None = Field(default=None, index=True)
    action_type: str
    reason: str
    evidence_summary: str
    expected_impact: str
    status: str = "pending"
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None
    execution_status: str = "blocked"
    execution_result: str | None = None


class RecoveryVerification(SQLModel, table=True):
    __tablename__ = "recovery_verifications"

    id: int | None = Field(default=None, primary_key=True)
    investigation_id: int = Field(index=True)
    incident_id: int | None = Field(default=None, index=True)
    approval_id: int | None = None
    recovered: bool = False
    status: str = "UNKNOWN"
    details: str | None = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
