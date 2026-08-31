from __future__ import annotations

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
async def analyze(request: AgentRequest) -> AgentResponse:
    """
    Unified manual analysis endpoint.

    IMPORTANT:
    This endpoint delegates diagnosis to the canonical investigation
    pipeline instead of maintaining a second diagnostic implementation.

    No recovery action is executed here.
    Actions requiring approval remain blocked.
    """

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
    # 2. Run canonical investigation
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
    # 3. Safely extract evidence
    # ---------------------------------------------------------

    evidence = ReliabilityEvidence(
        health=None,
        request_rate=None,
        error_rate=None,
        p95_latency_seconds=None,
    )

    # Investigation may expose collected signals.
    # Keep this defensive so older investigation objects remain
    # compatible.

    signals = getattr(
        investigation,
        "signals",
        None,
    )

    if not isinstance(signals, dict):
        signals = {}

    # Support both current and compatibility signal names.

    health_value = signals.get(
        "health_ok",
        signals.get("service_health"),
    )

    request_rate_value = signals.get(
        "request_rate",
        signals.get("request_rate_per_second"),
    )

    error_rate_value = signals.get(
        "error_rate",
        signals.get("error_rate_percent"),
    )

    p95_value = signals.get(
        "p95",
        signals.get("p95_latency_seconds"),
    )

    evidence = ReliabilityEvidence(
        health=(
            bool(health_value)
            if health_value is not None
            else None
        ),
        request_rate=(
            float(request_rate_value)
            if request_rate_value is not None
            else None
        ),
        error_rate=(
            float(error_rate_value)
            if error_rate_value is not None
            else None
        ),
        p95_latency_seconds=(
            float(p95_value)
            if p95_value is not None
            else None
        ),
    )

    # ---------------------------------------------------------
    # 4. Recommended action
    # ---------------------------------------------------------

    recommended_action = (
        getattr(
            investigation,
            "recommended_action",
            None,
        )
        or "Continue normal monitoring."
    )

    approval_required = bool(
        getattr(
            investigation,
            "approval_required",
            False,
        )
    )

    if approval_required:
        recommended_action = (
            f"{recommended_action} "
            "BLOCKED until explicit human approval."
        )

    # ---------------------------------------------------------
    # 5. Status
    # ---------------------------------------------------------

    investigation_status = (
        getattr(
            investigation,
            "status",
            None,
        )
        or "RECOMMENDED"
    )

    status = (
        "AWAITING_APPROVAL"
        if approval_required
        else investigation_status
    )

    # ---------------------------------------------------------
    # 6. Severity
    # ---------------------------------------------------------

    severity = (
        getattr(
            investigation,
            "severity",
            None,
        )
        or "MEDIUM"
    )

    # Keep response compatible with existing API contract.
    severity = str(severity).upper()

    # ---------------------------------------------------------
    # 7. Final unified response
    # ---------------------------------------------------------

    return AgentResponse(
        status=status,
        severity=severity,
        evidence=evidence,
        diagnosis=(
            getattr(
                investigation,
                "diagnosis",
                None,
            )
            or getattr(
                investigation,
                "likely_cause",
                None,
            )
            or ""
        ),
        recommended_action=recommended_action,
        investigation_id=getattr(
            investigation,
            "id",
            None,
        ),
        likely_cause=getattr(
            investigation,
            "likely_cause",
            None,
        ),
        confidence=getattr(
            investigation,
            "confidence",
            None,
        ),
        approval_required=(
            getattr(
                investigation,
                "approval_required",
                None,
            )
        ),
        approval_status=(
            getattr(
                investigation,
                "approval_status",
                None,
            )
        ),
    )
