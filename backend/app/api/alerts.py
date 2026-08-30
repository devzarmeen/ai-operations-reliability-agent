from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.agent.investigation import run_investigation
from app.core.database import engine
from app.models.alert import AlertRecord
from app.models.incident import Incident


router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


class GrafanaAlert(BaseModel):
    status: str | None = None
    labels: dict = Field(default_factory=dict)
    annotations: dict = Field(default_factory=dict)
    fingerprint: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None


class GrafanaWebhook(BaseModel):
    status: str | None = None
    alerts: list[GrafanaAlert] = Field(default_factory=list)
    title: str | None = None
    message: str | None = None


def _fingerprint(alert: GrafanaAlert) -> str:
    if alert.fingerprint:
        return alert.fingerprint
    labels = alert.labels or {}
    return "|".join(
        [
            str(labels.get("alertname") or labels.get("alert_name") or "unknown"),
            str(labels.get("service") or labels.get("service_name") or "simulated-api-service"),
            str(alert.status or "unknown"),
        ]
    )


@router.post("/webhook")
async def ingest_grafana_webhook(payload: GrafanaWebhook):
    """Ingest Grafana Unified Alerting webhooks without replacing scheduler alerts."""
    ingested = []
    skipped = []

    alerts = payload.alerts or [
        GrafanaAlert(
            status=payload.status,
            labels={"alertname": payload.title or "grafana-alert"},
            annotations={"summary": payload.message or ""},
        )
    ]

    for alert in alerts:
        labels = alert.labels or {}
        annotations = alert.annotations or {}
        fingerprint = _fingerprint(alert)
        status = (alert.status or payload.status or "firing").lower()
        service = str(
            labels.get("service")
            or labels.get("service_name")
            or "simulated-api-service"
        )
        alert_name = str(labels.get("alertname") or labels.get("alert_name") or "grafana-alert")
        severity = str(labels.get("severity") or "HIGH").upper()
        summary = str(
            annotations.get("summary")
            or annotations.get("description")
            or payload.message
            or alert_name
        )

        with Session(engine) as session:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
            duplicate = session.exec(
                select(AlertRecord)
                .where(AlertRecord.fingerprint == fingerprint)
                .where(AlertRecord.status == status)
                .where(AlertRecord.created_at >= cutoff)
            ).first()
            if duplicate:
                skipped.append({"fingerprint": fingerprint, "reason": "duplicate"})
                continue

            incident_status = "DOWN" if status in {"firing", "alerting"} else "HEALTHY"
            if "latency" in alert_name.lower() or "error" in alert_name.lower():
                if incident_status != "HEALTHY":
                    incident_status = "DEGRADED" if "down" not in alert_name.lower() else "DOWN"

            incident = Incident(
                status=incident_status if status != "resolved" else "HEALTHY",
                severity="LOW" if status == "resolved" else severity,
                reason=summary,
                service_name=service,
            )
            session.add(incident)
            session.commit()
            session.refresh(incident)

        investigation = None
        if status != "resolved":
            investigation = await run_investigation(
                alert={
                    "alert_id": fingerprint,
                    "alert_name": alert_name,
                    "status": status,
                    "severity": severity,
                    "service_name": service,
                    "summary": summary,
                },
                incident_id=incident.id,
            )

        with Session(engine) as session:
            record = AlertRecord(
                fingerprint=fingerprint,
                alert_name=alert_name,
                service_name=service,
                status=status,
                severity=severity,
                payload_summary=summary,
                investigation_id=investigation.id if investigation else None,
            )
            session.add(record)
            session.commit()
            session.refresh(record)

        ingested.append(
            {
                "alert_id": record.id,
                "incident_id": incident.id,
                "investigation_id": investigation.id if investigation else None,
                "status": status,
                "duplicate": False,
            }
        )

    return {"ingested": ingested, "skipped": skipped}
