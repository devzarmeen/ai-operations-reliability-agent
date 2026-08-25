from fastapi import APIRouter
from sqlmodel import Session

from agents import Runner

from app.agent.reliability_agent import reliability_agent
from app.core.database import engine

from app.diagnostics.health import service_health
from app.diagnostics.metrics import request_metrics
from app.diagnostics.errors import error_rate
from app.diagnostics.latency import latency

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


@router.post("/analyze", response_model=AgentResponse)
async def analyze(request: AgentRequest):

    # -----------------------------------------
    # 1. Collect diagnostic evidence
    # -----------------------------------------

    health = await service_health(
        service_name="simulated-api-service"
    )

    metrics = await request_metrics(
        metric_name="api_request_rate"
    )

    errors = await error_rate(
        metric_name="5xx_error_rate"
    )

    latency_result = await latency(
        metric_name="p95_request_latency"
    )

    # -----------------------------------------
    # 2. Build evidence for AI agent
    # -----------------------------------------

    evidence_prompt = f"""
User request:
{request.query}

Current production reliability evidence:

Service Health:
{health}

Request Rate:
{metrics}

5xx Error Rate:
{errors}

P95 Latency:
{latency_result}

Analyze the service using ONLY the diagnostic evidence above.

Determine whether the service is:
- HEALTHY
- DEGRADED
- DOWN

Do not say UNKNOWN when the supplied evidence is sufficient.
Do not invent any metrics.
"""

    # -----------------------------------------
    # 3. Run AI Reliability Agent
    # -----------------------------------------

    result = await Runner.run(
        reliability_agent,
        evidence_prompt,
    )

    # -----------------------------------------
    # 4. Determine API status
    # -----------------------------------------

    is_healthy = health.get("healthy", False)

    if not is_healthy:
        status = "DOWN"
        severity = "CRITICAL"

    elif errors.get("error_rate", 0) > 5:
        status = "DEGRADED"
        severity = "HIGH"

    elif latency_result.get("value", 0) > 0.100:
        status = "DEGRADED"
        severity = "MEDIUM"

    else:
        status = "HEALTHY"
        severity = "LOW"

    # -----------------------------------------
    # 5. Recommended action
    # -----------------------------------------

    if status == "HEALTHY":
        recommended_action = "Continue normal monitoring."

    elif status == "DEGRADED":
        recommended_action = (
            "Investigate elevated reliability metrics "
            "and continue monitoring."
        )

    else:
        recommended_action = (
            "Investigate the production service immediately."
        )

    # -----------------------------------------
    # 6. Save incident
    # -----------------------------------------

    incident = Incident(
        status=status,
        severity=severity,
        reason=result.final_output,
        service_name="simulated-api-service",
        request_rate=metrics.get("value"),
        error_rate=errors.get("error_rate"),
        p95_latency_seconds=latency_result.get("value"),
    )

    with Session(engine) as session:
        session.add(incident)
        session.commit()
        session.refresh(incident)

    # -----------------------------------------
    # 7. Return API response
    # -----------------------------------------

    return AgentResponse(
        status=status,
        severity=severity,

        evidence=ReliabilityEvidence(
            health=is_healthy,
            request_rate=metrics.get("value"),
            error_rate=errors.get("error_rate"),
            p95_latency_seconds=latency_result.get("value"),
        ),

        diagnosis=result.final_output,

        recommended_action=recommended_action,
    )