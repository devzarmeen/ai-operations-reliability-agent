from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.agent.investigation import run_investigation
from app.core.database import engine
from app.metrics import (
    APPROVAL_DECISIONS,
    INVESTIGATIONS_COMPLETED,
    RECOVERY_RESULTS,
)
from app.models.incident import Incident
from app.models.investigation import (
    ApprovalRequest,
    Investigation,
    InvestigationEvent,
    RecoveryVerification,
)
from app.safety.enforcement import requires_approval
from app.services.diagnostics import (
    collect_full_diagnostics,
)
from app.tools.actions import (
    execute_controlled_action,
)


router = APIRouter(
    prefix="/api",
    tags=["Investigations"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    """Return current UTC time."""

    return datetime.now(timezone.utc)


def _service_recovered(
    snapshot: dict | None,
    execution: dict,
) -> bool:
    """
    Verify recovery using live simulated-service health.

    Primary source:
        /health

    Prometheus is treated as supporting evidence because
    Prometheus can lag immediately after a recovery action.
    """

    if not snapshot:
        return False

    # ---------------------------------------------------------------
    # Live service health
    # ---------------------------------------------------------------

    health_wrapper = (
        snapshot.get("service_health") or {}
    )

    health_result = (
        health_wrapper.get("result") or {}
    )

    health_data = (
        health_result.get("data") or {}
    )

    live_healthy = (
        health_result.get("available") is True
        and health_data.get("status") == "healthy"
    )

    if not live_healthy:
        return False

    # ---------------------------------------------------------------
    # Determine current scenario
    # ---------------------------------------------------------------

    execution_result = (
        execution.get("result") or {}
    )

    execution_state = (
        execution_result.get("state") or {}
    )

    scenario = (
        health_data.get("scenario")
        or execution_state.get("scenario")
    )

    # A normal state is obviously recovered.
    #
    # recovery_after_failure is accepted because the
    # simulated API may explicitly report this transitional
    # state after a successful recovery action.
    acceptable_scenarios = {
        None,
        "normal",
        "recovery_after_failure",
    }

    if scenario in acceptable_scenarios:
        return True

    # ---------------------------------------------------------------
    # Prometheus supporting evidence
    # ---------------------------------------------------------------

    prometheus_status = (
        snapshot.get("overall_status")
    )

    prometheus_healthy = (
        prometheus_status == "HEALTHY"
    )

    return prometheus_healthy


def _investigation_payload(
    session: Session,
    investigation: Investigation,
) -> dict:

    events = session.exec(
        select(InvestigationEvent)
        .where(
            InvestigationEvent.investigation_id
            == investigation.id
        )
        .order_by(
            InvestigationEvent.id.asc()
        )
    ).all()

    approvals = session.exec(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.investigation_id
            == investigation.id
        )
        .order_by(
            ApprovalRequest.id.desc()
        )
    ).all()

    recoveries = session.exec(
        select(RecoveryVerification)
        .where(
            RecoveryVerification.investigation_id
            == investigation.id
        )
        .order_by(
            RecoveryVerification.id.desc()
        )
    ).all()

    return {
        "investigation": investigation,
        "events": events,
        "approvals": approvals,
        "recoveries": recoveries,
    }


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class DecisionBody(BaseModel):
    operator: str = "operator"
    note: str | None = None


# ---------------------------------------------------------------------------
# Investigation routes
# ---------------------------------------------------------------------------

@router.get("/investigations")
def list_investigations():

    with Session(engine) as session:

        return session.exec(
            select(Investigation)
            .order_by(
                Investigation.id.desc()
            )
        ).all()


@router.get("/investigations/latest")
def latest_investigation():

    with Session(engine) as session:

        investigation = session.exec(
            select(Investigation)
            .order_by(
                Investigation.id.desc()
            )
        ).first()

        if investigation is None:
            return {
                "investigation": None,
                "events": [],
                "approvals": [],
                "recoveries": [],
            }

        return _investigation_payload(
            session,
            investigation,
        )


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: int,
):

    with Session(engine) as session:

        investigation = session.get(
            Investigation,
            investigation_id,
        )

        if investigation is None:
            raise HTTPException(
                status_code=404,
                detail="Investigation not found",
            )

        return _investigation_payload(
            session,
            investigation,
        )


# ---------------------------------------------------------------------------
# Approval endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/investigations/{investigation_id}/approve"
)
async def approve_investigation(
    investigation_id: int,
    body: DecisionBody,
):

    return await _decide(
        investigation_id,
        approved=True,
        body=body,
    )


@router.post(
    "/investigations/{investigation_id}/reject"
)
async def reject_investigation(
    investigation_id: int,
    body: DecisionBody,
):

    return await _decide(
        investigation_id,
        approved=False,
        body=body,
    )


# ---------------------------------------------------------------------------
# Approval decision
# ---------------------------------------------------------------------------

async def _decide(
    investigation_id: int,
    approved: bool,
    body: DecisionBody,
) -> dict:
    """
    Apply an explicit human approval/rejection.

    High-impact actions are NEVER executed before
    explicit human approval.
    """

    # ===============================================================
    # STEP 1 — Validate and record human decision
    # ===============================================================

    with Session(engine) as session:

        investigation = session.get(
            Investigation,
            investigation_id,
        )

        if investigation is None:
            raise HTTPException(
                status_code=404,
                detail="Investigation not found",
            )

        approval = session.exec(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.investigation_id
                == investigation_id
            )
            .where(
                ApprovalRequest.status == "pending"
            )
            .order_by(
                ApprovalRequest.id.desc()
            )
        ).first()

        if approval is None:
            raise HTTPException(
                status_code=409,
                detail="No pending approval request",
            )

        action_type = approval.action_type

        if not requires_approval(
            action_type
        ):
            raise HTTPException(
                status_code=400,
                detail="Action is not high-impact",
            )

        decision = (
            "approved"
            if approved
            else "rejected"
        )

        approval.status = decision
        approval.decided_at = _now()
        approval.decided_by = body.operator
        approval.decision_note = body.note

        investigation.approval_status = decision
        investigation.updated_at = _now()

        session.add(
            InvestigationEvent(
                investigation_id=investigation_id,
                incident_id=investigation.incident_id,
                event_type="approval_decision",
                decision=decision,
                details=(
                    f"operator={body.operator}"
                ),
            )
        )

        session.add(approval)
        session.add(investigation)

        session.commit()

        session.refresh(approval)
        session.refresh(investigation)

        approval_id = approval.id
        incident_id = investigation.incident_id

    # ===============================================================
    # Metrics
    # ===============================================================

    APPROVAL_DECISIONS.labels(
        decision=(
            "approved"
            if approved
            else "rejected"
        )
    ).inc()

    # ===============================================================
    # STEP 2 — Rejection
    # ===============================================================

    if not approved:

        with Session(engine) as session:

            investigation = session.get(
                Investigation,
                investigation_id,
            )

            if investigation is None:
                raise HTTPException(
                    status_code=404,
                    detail="Investigation not found",
                )

            investigation.stage = "ESCALATED"
            investigation.status = "REJECTED"
            investigation.updated_at = _now()

            session.add(investigation)

            session.commit()

            session.refresh(investigation)

            INVESTIGATIONS_COMPLETED.labels(
                outcome="rejected"
            ).inc()

            return _investigation_payload(
                session,
                investigation,
            )

    # ===============================================================
    # STEP 3 — Execute ONLY after approval
    # ===============================================================

    execution = await execute_controlled_action(
        action_type
    )

    # Never assume recovery before verification.
    recovered = False

    snapshot: dict | None = None

    if execution.get("ok"):

        # Give the simulated service/action a moment
        # to reach its new state if necessary.
        snapshot = (
            await collect_full_diagnostics()
        )

        recovered = _service_recovered(
            snapshot,
            execution,
        )

    # ===============================================================
    # STEP 4 — Persist execution + verification
    # ===============================================================

    with Session(engine) as session:

        approval = session.get(
            ApprovalRequest,
            approval_id,
        )

        investigation = session.get(
            Investigation,
            investigation_id,
        )

        if approval is None:
            raise HTTPException(
                status_code=500,
                detail="Approval record disappeared",
            )

        if investigation is None:
            raise HTTPException(
                status_code=500,
                detail="Investigation record disappeared",
            )

        # -----------------------------------------------------------
        # Execution result
        # -----------------------------------------------------------

        approval.execution_status = (
            "executed"
            if execution.get("ok")
            else "failed"
        )

        approval.execution_result = str(
            execution
        )

        # -----------------------------------------------------------
        # Investigation status
        # -----------------------------------------------------------

        if recovered:

            investigation.stage = "RECOVERED"
            investigation.status = "RECOVERED"

        else:

            investigation.stage = "VERIFYING"
            investigation.status = "FAILED"

        # -----------------------------------------------------------
        # Recovery verification
        # -----------------------------------------------------------

        recovery_status = (
            snapshot.get("overall_status")
            if snapshot
            else "UNKNOWN"
        )

        session.add(
            RecoveryVerification(
                investigation_id=investigation_id,
                incident_id=incident_id,
                approval_id=approval_id,
                recovered=recovered,
                status=recovery_status,
                details=(
                    str(snapshot)[:2000]
                    if snapshot
                    else str(execution)
                ),
            )
        )

        # -----------------------------------------------------------
        # Event — action executed
        # -----------------------------------------------------------

        session.add(
            InvestigationEvent(
                investigation_id=investigation_id,
                incident_id=incident_id,
                event_type="action_executed",
                tool_name=action_type,
                tool_result_summary=str(
                    execution
                )[:1200],
                decision="executed_after_approval",
            )
        )

        # -----------------------------------------------------------
        # Event — recovery verification
        # -----------------------------------------------------------

        session.add(
            InvestigationEvent(
                investigation_id=investigation_id,
                incident_id=incident_id,
                event_type="recovery_verification",
                decision=(
                    "recovered"
                    if recovered
                    else "not_recovered"
                ),
                details=recovery_status,
            )
        )

        # ===========================================================
        # STEP 5 — Only recovered incident becomes HEALTHY
        # ===========================================================

        if (
            investigation.incident_id
            and recovered
        ):

            incident = session.get(
                Incident,
                investigation.incident_id,
            )

            if incident is not None:

                incident.status = "HEALTHY"
                incident.severity = "LOW"

                incident.reason = (
                    (incident.reason or "")
                    + "\n"
                    "Recovery verified after "
                    "approved action."
                )

                session.add(incident)

        investigation.updated_at = _now()

        session.add(approval)
        session.add(investigation)

        session.commit()

        session.refresh(investigation)

        payload = _investigation_payload(
            session,
            investigation,
        )

    # ===============================================================
    # STEP 6 — Metrics
    # ===============================================================

    RECOVERY_RESULTS.labels(
        result=(
            "success"
            if recovered
            else "failure"
        )
    ).inc()

    INVESTIGATIONS_COMPLETED.labels(
        outcome=(
            "recovered"
            if recovered
            else "recovery_failed"
        )
    ).inc()

    return payload