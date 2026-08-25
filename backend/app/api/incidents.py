from fastapi import APIRouter, Query
from sqlmodel import Session, select

from app.core.database import engine
from app.models.incident import Incident


router = APIRouter(
    prefix="/api/incidents",
    tags=["Incidents"],
)


@router.get("/")
def get_incidents(
    status: str | None = Query(
        default=None,
        description="Filter by status: HEALTHY, DEGRADED, or DOWN",
    ),
    severity: str | None = Query(
        default=None,
        description="Filter by severity: LOW, MEDIUM, HIGH, or CRITICAL",
    ),
):
    statement = select(Incident)

    if status:
        statement = statement.where(
            Incident.status == status.upper()
        )

    if severity:
        statement = statement.where(
            Incident.severity == severity.upper()
        )

    statement = statement.order_by(
        Incident.created_at.desc()
    )

    with Session(engine) as session:
        incidents = session.exec(statement).all()

        return incidents


@router.get("/summary")
def get_incident_summary():
    with Session(engine) as session:
        incidents = session.exec(
            select(Incident)
        ).all()

    return {
        "total": len(incidents),

        "healthy": sum(
            1 for incident in incidents
            if incident.status == "HEALTHY"
        ),

        "degraded": sum(
            1 for incident in incidents
            if incident.status == "DEGRADED"
        ),

        "down": sum(
            1 for incident in incidents
            if incident.status == "DOWN"
        ),

        "low": sum(
            1 for incident in incidents
            if incident.severity == "LOW"
        ),

        "medium": sum(
            1 for incident in incidents
            if incident.severity == "MEDIUM"
        ),

        "high": sum(
            1 for incident in incidents
            if incident.severity == "HIGH"
        ),

        "critical": sum(
            1 for incident in incidents
            if incident.severity == "CRITICAL"
        ),
    }