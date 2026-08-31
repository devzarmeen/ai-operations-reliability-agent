from __future__ import annotations

from pydantic import BaseModel


class AgentRequest(BaseModel):
    query: str


class ReliabilityEvidence(BaseModel):
    health: bool | None = None
    request_rate: float | None = None
    error_rate: float | None = None
    p95_latency_seconds: float | None = None


class AgentResponse(BaseModel):
    status: str
    severity: str
    evidence: ReliabilityEvidence

    diagnosis: str
    recommended_action: str

    investigation_id: int | None = None
    likely_cause: str | None = None
    confidence: float | None = None

    approval_required: bool | None = None
    approval_status: str | None = None
