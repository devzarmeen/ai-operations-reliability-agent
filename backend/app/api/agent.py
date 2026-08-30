from fastapi import APIRouter
from sqlmodel import Session

from app.agent.investigation import run_investigation
from app.core.database import engine
from app.models.incident import Incident
from app.schemas.agent import (
    AgentRequest,
    AgentResponse,
    ReliabilityEvidence,
)


router = APIRouter(
    prefix="/api/agent",
    tags=["Reliability Agent"],
)


@router.post(
    "/analyze",
    response_model=AgentResponse,
)
async def analyze(request: AgentRequest):

    # ---------------------------------------------------------
    # 1. Create incident
    # ---------------------------------------------------------

    incident = Incident(
        status="INVESTIGATING",
        severity="MEDIUM",
        reason=request.query,
        service_name="simulated-api-service",
    )

    with Session(engine) as session:
        session.add(incident)
        session.commit()
        session.refresh(incident)

        incident_id = incident.id

    # ---------------------------------------------------------
    # 2. Start investigation
    # ---------------------------------------------------------

    investigation = await run_investigation(
        alert={
            "alert_id": f"agent-analyze-{incident_id}",
            "alert_name": "manual-analyze",
            "status": "firing",
            "severity": "medium",
            "service_name": "simulated-api-service",
            "summary": request.query,
            "reason": request.query,
        },
        incident_id=incident_id,
    )

    # ---------------------------------------------------------
    # 3. Build evidence response from investigation events
    # ---------------------------------------------------------

    evidence = ReliabilityEvidence(
        health=None,
        request_rate=None,
        error_rate=None,
        p95_latency_seconds=None,
    )

    recommended_action = (
        investigation.recommended_action
        or "Continue normal monitoring."
    )

    if investigation.approval_required:
        recommended_action = (
            f"{recommended_action} "
            "BLOCKED until explicit human approval."
        )

    # ---------------------------------------------------------
    # 4. Return unified agent response
    # ---------------------------------------------------------

    return AgentResponse(
        status=(
            "AWAITING_APPROVAL"
            if investigation.approval_required
            else investigation.status
        ),
        severity="MEDIUM",
        evidence=evidence,
        diagnosis=(
            investigation.diagnosis
            or investigation.likely_cause
            or ""
        ),
        recommended_action=recommended_action,
        investigation_id=investigation.id,
        likely_cause=investigation.likely_cause,
        confidence=investigation.confidence,
        approval_required=investigation.approval_required,
        approval_status=investigation.approval_status,
    )