from datetime import datetime, timezone

from agents import Runner
from sqlmodel import Session, select

from app.agent.reliability_agent import reliability_agent
from app.core.database import engine
from app.diagnostics.health import service_health
from app.diagnostics.metrics import request_metrics
from app.diagnostics.errors import error_rate
from app.diagnostics.latency import latency
from app.models.incident import Incident
from app.alerts.manager import handle_incident_alert
from app.metrics import update_reliability_metrics
from app.agent.investigation import run_investigation

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

    # 3. Run AI reliability agent (fail safe if the model is unavailable)
    try:
        result = await Runner.run(
            reliability_agent,
            evidence_prompt,
        )
        diagnosis_text = result.final_output
    except Exception as exc:  # noqa: BLE001
        print(f"[SCHEDULER] Reliability agent unavailable: {exc}")
        diagnosis_text = (
            "Deterministic status from diagnostic evidence; "
            "LLM diagnosis unavailable."
        )

    # 4. Determine status and severity
    is_healthy = health.get("healthy", False)
    current_error_rate = errors.get("error_rate") or 0
    current_latency = latency_result.get("value") or 0

    if not is_healthy:
        status = "DOWN"
        severity = "CRITICAL"

    elif current_error_rate > 5:
        status = "DEGRADED"
        severity = "HIGH"

    elif current_latency > 0.100:
        status = "DEGRADED"
        severity = "MEDIUM"

    else:
        status = "HEALTHY"
        severity = "LOW"

    # 5. Get previous incident
    with Session(engine) as session:
        previous_incident = session.exec(
            select(Incident)
            .where(
                Incident.service_name == "simulated-api-service"
            )
            .order_by(Incident.id.desc())
        ).first()

    # 6. Create new incident
    incident = Incident(
        status=status,
        severity=severity,
        reason=diagnosis_text,
        service_name="simulated-api-service",
        request_rate=metrics.get("value"),
        error_rate=errors.get("error_rate"),
        p95_latency_seconds=latency_result.get("value"),
        created_at=datetime.now(timezone.utc),
    )

    # 7. Save incident
    with Session(engine) as session:
        session.add(incident)
        session.commit()
        session.refresh(incident)

    # 8. Update Prometheus metrics
    with Session(engine) as session:
        incidents = session.exec(
            select(Incident)
        ).all()

    update_reliability_metrics(
        total=len(incidents),
        healthy=sum(
            1 for item in incidents
            if item.status == "HEALTHY"
        ),
        degraded=sum(
            1 for item in incidents
            if item.status == "DEGRADED"
        ),
        down=sum(
            1 for item in incidents
            if item.status == "DOWN"
        ),
        low=sum(
            1 for item in incidents
            if item.severity == "LOW"
        ),
        medium=sum(
            1 for item in incidents
            if item.severity == "MEDIUM"
        ),
        high=sum(
            1 for item in incidents
            if item.severity == "HIGH"
        ),
        critical=sum(
            1 for item in incidents
            if item.severity == "CRITICAL"
        ),
        request_rate=metrics.get("value"),
        error_rate=errors.get("error_rate"),
        p95_latency=latency_result.get("value"),
        service_healthy=health.get("healthy", False),
    )
    # 9. Alert only when state changes
    state_changed = (
        previous_incident is None
        or previous_incident.status != incident.status
    )

    if state_changed:
        investigation = None
        if incident.status in {"DEGRADED", "DOWN"}:
            investigation = await run_investigation(
                alert={
                    "alert_id": f"scheduler-{incident.id}",
                    "alert_name": f"scheduler-{incident.status}",
                    "status": incident.status,
                    "severity": incident.severity,
                    "service_name": incident.service_name,
                    "summary": incident.reason,
                    "reason": incident.reason,
                },
                incident_id=incident.id,
            )
        await handle_incident_alert(incident, investigation=investigation)
    else:
        print(
            f"[ALERT] Duplicate state detected: "
            f"{incident.status}. Alert skipped."
        )

    print(
        f"[SCHEDULER] Incident #{incident.id} created: "
        f"{incident.status} / {incident.severity}"
    )

    return incident