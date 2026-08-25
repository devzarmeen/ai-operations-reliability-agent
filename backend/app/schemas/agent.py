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