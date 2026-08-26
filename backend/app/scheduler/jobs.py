from datetime import datetime, timezone

from agents import Runner
from sqlmodel import Session

from app.agent.reliability_agent import reliability_agent
from app.core.database import engine
from app.diagnostics.health import service_health
from app.diagnostics.metrics import request_metrics
from app.diagnostics.errors import error_rate
from app.diagnostics.latency import latency
from app.models.incident import Incident
from app.alerts.manager import handle_incident_alert

async def run_reliability_check():
    """
    Run one automatic reliability check and save the result
    as an incident.
    """

    # 1. Collect diagnostic evidence
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

    # 2. Build evidence prompt
    evidence_prompt = f"""
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

Do not invent any metrics.
Do not say UNKNOWN when the supplied evidence is sufficient.
"""

    # 3. Run AI reliability agent
    result = await Runner.run(
        reliability_agent,
        evidence_prompt,
    )

    # 4. Determine status and severity
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

    # 5. Save incident
    incident = Incident(
        status=status,
        severity=severity,
        reason=result.final_output,
        service_name="simulated-api-service",
        request_rate=metrics.get("value"),
        error_rate=errors.get("error_rate"),
        p95_latency_seconds=latency_result.get("value"),
        created_at=datetime.now(timezone.utc),
    )

    with Session(engine) as session:
        session.add(incident)
        session.commit()
        session.refresh(incident)
        
        await handle_incident_alert(incident)

        print(
            f"[SCHEDULER] Incident #{incident.id} created: "
            f"{incident.status} / {incident.severity}"
        )

    return incident