from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.core.database import engine
from app.metrics import (
    APPROVAL_REQUESTS,
    INVESTIGATIONS_COMPLETED,
    INVESTIGATIONS_STARTED,
)
from app.models.investigation import (
    ApprovalRequest,
    Investigation,
    InvestigationEvent,
)
from app.safety.enforcement import requires_approval
from app.services.diagnostics import (
    collect_container_health,
    collect_database_signals,
    collect_full_diagnostics,
    collect_logs,
    collect_prometheus_snapshot,
    collect_service_health,
    collect_deployments,
)


# ============================================================
# Utility helpers
# ============================================================


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary(payload: Any, limit: int = 1200) -> str:
    """
    Convert arbitrary diagnostic data into a compact JSON
    representation suitable for audit logging.
    """
    try:
        text = json.dumps(payload, default=str)
    except Exception:
        text = str(payload)

    if len(text) <= limit:
        return text

    return text[: limit - 3] + "..."


def _log_event(
    session: Session,
    investigation: Investigation,
    event_type: str,
    **kwargs: Any,
) -> None:
    """
    Add an investigation audit event.
    """
    if investigation.id is None:
        return

    session.add(
        InvestigationEvent(
            investigation_id=investigation.id,
            incident_id=investigation.incident_id,
            event_type=event_type,
            **kwargs,
        )
    )


def _num(value: Any) -> float | None:
    """
    Safely convert a value to float.
    """
    if value is None or isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nested(data: Any, *path: str) -> Any:
    """
    Safely access nested dictionary values.
    """
    current = data

    for key in path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


# ============================================================
# Tool selection
# ============================================================


def select_tools(alert: dict[str, Any]) -> list[str]:
    """
    Select diagnostic tools based on alert content.

    Service health and Prometheus metrics are always collected.
    Additional tools are selected according to the alert.
    """

    text = " ".join(
        str(alert.get(key) or "")
        for key in (
            "alert_name",
            "status",
            "severity",
            "summary",
            "reason",
        )
    ).lower()

    tools = [
        "service_health",
        "prometheus_metrics",
    ]

    if any(
        token in text
        for token in (
            "error",
            "5xx",
            "500",
            "exception",
            "degraded",
        )
    ):
        tools.extend(
            [
                "structured_logs",
                "deployments",
                "container_health",
            ]
        )

    if any(
        token in text
        for token in (
            "latency",
            "slow",
            "timeout",
        )
    ):
        tools.extend(
            [
                "database_signals",
                "container_health",
            ]
        )

    if any(
        token in text
        for token in (
            "down",
            "unavailable",
            "health",
        )
    ):
        tools.extend(
            [
                "container_health",
                "database_signals",
            ]
        )

    if any(
        token in text
        for token in (
            "deploy",
            "rollback",
            "version",
        )
    ):
        tools.append("deployments")

    if any(
        token in text
        for token in (
            "database",
            "postgres",
            "connection",
        )
    ):
        tools.append("database_signals")

    if "log" in text:
        tools.append("structured_logs")

    # Preserve order and remove duplicates.
    ordered: list[str] = []

    for tool in tools:
        if tool not in ordered:
            ordered.append(tool)

    return ordered


# ============================================================
# Diagnostic tool execution
# ============================================================


async def _run_tool(name: str) -> dict[str, Any]:
    """
    Execute one read-only diagnostic tool.
    """

    mapping = {
        "service_health": collect_service_health,
        "prometheus_metrics": collect_prometheus_snapshot,
        "structured_logs": collect_logs,
        "container_health": collect_container_health,
        "database_signals": collect_database_signals,
        "deployments": collect_deployments,
    }

    func = mapping.get(name)

    if func is None:
        return {
            "ok": False,
            "tool": name,
            "error": "unknown_tool",
            "result": None,
        }

    try:
        result = await func()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "tool": name,
            "result": result,
        }

    except Exception as exc:
        return {
            "ok": False,
            "tool": name,
            "error": str(exc),
            "result": None,
        }


# ============================================================
# Signal extraction
# ============================================================


def _extract_signals(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize diagnostic evidence into one signal dictionary.

    IMPORTANT:
    Missing evidence is represented as None.
    Missing evidence is NEVER converted into False.

    Additional evidence flags are returned so hypothesis
    testing can distinguish:

        False = actual negative evidence
        None  = evidence unavailable
        True  = actual positive evidence
    """

    # --------------------------------------------------------
    # Prometheus
    # --------------------------------------------------------

    prometheus = (
        _nested(
            evidence,
            "prometheus_metrics",
            "result",
        )
        or {}
    )

    if not isinstance(prometheus, dict):
        prometheus = {}

    metrics = prometheus.get("metrics") or {}

    if not isinstance(metrics, dict):
        metrics = {}

    # --------------------------------------------------------
    # Service health
    # --------------------------------------------------------

    health = (
        _nested(
            evidence,
            "service_health",
            "result",
            "data",
        )
        or {}
    )

    if not isinstance(health, dict):
        health = {}

    # --------------------------------------------------------
    # Container
    # --------------------------------------------------------

    container = (
        _nested(
            evidence,
            "container_health",
            "result",
            "data",
        )
        or {}
    )

    if not isinstance(container, dict):
        container = {}

    # --------------------------------------------------------
    # Deployment
    # --------------------------------------------------------

    deployment_result = (
        _nested(
            evidence,
            "deployments",
            "result",
        )
        or {}
    )

    if not isinstance(deployment_result, dict):
        deployment_result = {}

    deployment = (
        deployment_result.get("data")
        or deployment_result
        or {}
    )

    if not isinstance(deployment, dict):
        deployment = {}

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    database = (
        _nested(
            evidence,
            "database_signals",
            "result",
        )
        or {}
    )

    if not isinstance(database, dict):
        database = {}

    simulated_db = (
        _nested(
            database,
            "simulated_service_db",
            "data",
        )
        or {}
    )

    if not isinstance(simulated_db, dict):
        simulated_db = {}

    postgres = database.get(
        "reliability_postgres"
    ) or {}

    if not isinstance(postgres, dict):
        postgres = {}

    # --------------------------------------------------------
    # Logs
    # --------------------------------------------------------

    logs = (
        _nested(
            evidence,
            "structured_logs",
            "result",
            "data",
        )
        or {}
    )

    if not isinstance(logs, dict):
        logs = {}

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    error_rate = _num(
        metrics.get("error_rate_percent")
    )

    client_error_rate = _num(
        metrics.get("client_error_rate_percent")
    )

    p95 = _num(
        metrics.get("p95_latency_seconds")
    )

    request_rate = _num(
        metrics.get("request_rate_per_second")
    )

    # --------------------------------------------------------
    # Log evidence
    # --------------------------------------------------------

    repeated_errors = (
        logs.get("repeated_errors")
        or []
    )

    if not isinstance(repeated_errors, list):
        repeated_errors = []

    log_5xx_evidence = any(
        (
            "5xx"
            in str(
                item.get("message", "")
            ).lower()
            or "500"
            in str(
                item.get("message", "")
            ).lower()
        )
        for item in repeated_errors
        if isinstance(item, dict)
    )

    # --------------------------------------------------------
    # Health determination
    # --------------------------------------------------------

    health_evidence_available = False
    health_ok: bool | None = None

    # First preference: Prometheus health.
    prometheus_health_ok = _nested(
        prometheus,
        "health",
        "healthy",
    )

    if prometheus_health_ok is not None:
        health_evidence_available = True

        if isinstance(
            prometheus_health_ok,
            bool,
        ):
            health_ok = prometheus_health_ok
        else:
            health_ok = (
                str(
                    prometheus_health_ok
                ).lower()
                in {
                    "true",
                    "healthy",
                    "ok",
                    "up",
                }
            )

    # Second preference: service-health result.
    if not health_evidence_available:
        health_status = health.get("status")

        if health_status is not None:
            health_evidence_available = True

            status = str(
                health_status
            ).lower()

            if status in {
                "healthy",
                "ok",
                "up",
                "true",
            }:
                health_ok = True

            elif status in {
                "unhealthy",
                "down",
                "unavailable",
                "failed",
                "false",
            }:
                health_ok = False

            else:
                health_ok = None

    # --------------------------------------------------------
    # Container evidence availability
    # --------------------------------------------------------

    container_evidence_available = any(
        container.get(key) is not None
        for key in (
            "state",
            "health",
            "restart_count",
        )
    )

    # --------------------------------------------------------
    # Deployment evidence availability
    # --------------------------------------------------------

    deployment_evidence_available = any(
        deployment.get(key) is not None
        for key in (
            "current_version",
            "recent_deployment",
            "bad_deployment",
            "deployed_at",
        )
    )

    # --------------------------------------------------------
    # Database evidence availability
    # --------------------------------------------------------

    database_evidence_available = (
        any(
            simulated_db.get(key) is not None
            for key in (
                "available",
                "latency_ms",
            )
        )
        or postgres.get("available")
        is not None
    )

    # --------------------------------------------------------
    # Final normalized signals
    # --------------------------------------------------------

    return {
        "error_rate": error_rate,
        "client_error_rate": client_error_rate,
        "p95": p95,
        "request_rate": request_rate,

        # IMPORTANT:
        # None = evidence unavailable.
        "health_ok": health_ok,
        "health_evidence_available": (
            health_evidence_available
        ),

        "container_state": container.get(
            "state"
        ),

        "container_health": container.get(
            "health"
        ),

        "restart_count": container.get(
            "restart_count"
        ),

        "container_evidence_available": (
            container_evidence_available
        ),

        "current_version": deployment.get(
            "current_version"
        ),

        "recent_deployment": (
            bool(
                deployment.get(
                    "recent_deployment"
                )
            )
            if deployment.get(
                "recent_deployment"
            )
            is not None
            else None
        ),

        "bad_deployment": (
            bool(
                deployment.get(
                    "bad_deployment"
                )
            )
            if deployment.get(
                "bad_deployment"
            )
            is not None
            else None
        ),

        "deployed_at": deployment.get(
            "deployed_at"
        ),

        "deployment_evidence_available": (
            deployment_evidence_available
        ),

        "simulated_db_available": (
            simulated_db.get("available")
        ),

        "simulated_db_latency_ms": _num(
            simulated_db.get("latency_ms")
        ),

        "postgres_available": (
            postgres.get("available")
        ),

        "database_evidence_available": (
            database_evidence_available
        ),

        "repeated_errors": repeated_errors,

        "error_patterns": (
            logs.get("error_patterns")
            or []
        ),

        "log_5xx_evidence": (
            log_5xx_evidence
        ),
    }


# ============================================================
# Hypothesis testing
# ============================================================


def _test_hypothesis(
    name: str,
    signals: dict[str, Any],
) -> dict[str, Any]:
    """
    Test one reliability hypothesis against evidence.

    Missing evidence NEVER counts as negative evidence.
    """

    error_rate = _num(
        signals.get("error_rate")
    ) or 0.0

    client_error_rate = _num(
        signals.get("client_error_rate")
    ) or 0.0

    p95 = _num(
        signals.get("p95")
    ) or 0.0

    request_rate = _num(
        signals.get("request_rate")
    ) or 0.0

    container_state = signals.get(
        "container_state"
    )

    container_health = signals.get(
        "container_health"
    )

    try:
        restart_count = int(
            signals.get("restart_count")
            or 0
        )
    except (TypeError, ValueError):
        restart_count = 0

    health_ok = signals.get(
        "health_ok"
    )

    health_evidence_available = (
        signals.get(
            "health_evidence_available"
        )
        is True
    )

    container_evidence_available = (
        signals.get(
            "container_evidence_available"
        )
        is True
    )

    container_failure = (
        container_evidence_available
        and (
            container_state
            in {
                "restarting",
                "stopped",
                "unhealthy",
            }
            or container_health
            in {
                "unhealthy",
            }
            or restart_count >= 5
        )
    )

    # IMPORTANT:
    # A service can only be classified as unavailable
    # when actual health evidence exists.
    service_unavailable = (
        health_evidence_available
        and health_ok is False
        and not container_failure
    )

    tests = {
        # ----------------------------------------------------
        # Deployment regression
        # ----------------------------------------------------

        "deployment_regression": (
            signals.get(
                "bad_deployment"
            )
            is True
            and signals.get(
                "recent_deployment"
            )
            is True
            and (
                health_ok is False
                or error_rate > 5
                or p95 > 0.1
                or signals.get(
                    "log_5xx_evidence",
                    False,
                )
            )
        ),

        # ----------------------------------------------------
        # Container failure
        # ----------------------------------------------------

        "container_failure": (
            container_failure
        ),

        # ----------------------------------------------------
        # Database unavailable
        # ----------------------------------------------------

        "database_unavailable": (
            (
                signals.get(
                    "simulated_db_available"
                )
                is False
                or signals.get(
                    "postgres_available"
                )
                is False
            )
        ),

        # ----------------------------------------------------
        # Database latency
        # ----------------------------------------------------

        "database_latency": (
            (
                _num(
                    signals.get(
                        "simulated_db_latency_ms"
                    )
                )
                or 0.0
            )
            > 200
            and p95 > 0.1
        ),

        # ----------------------------------------------------
        # Application errors
        # ----------------------------------------------------

        "application_errors": (
            error_rate > 5
            or signals.get(
                "log_5xx_evidence",
                False,
            )
        ),

        # ----------------------------------------------------
        # Client errors
        # ----------------------------------------------------

        "client_errors": (
            client_error_rate > 15
            and error_rate <= 5
        ),

        # ----------------------------------------------------
        # Traffic spike
        # ----------------------------------------------------

        "traffic_spike": (
            request_rate > 5
            and (
                p95 > 0.1
                or error_rate > 1
            )
        ),

        # ----------------------------------------------------
        # Latency degradation
        # ----------------------------------------------------

        "latency_degradation": (
            p95 > 0.1
        ),

        # ----------------------------------------------------
        # Service unavailable
        # ----------------------------------------------------

        "service_unavailable": (
            service_unavailable
        ),

        # ----------------------------------------------------
        # False positive
        # ----------------------------------------------------

        # IMPORTANT:
        # Missing health evidence cannot be treated as
        # healthy.
        "false_positive": (
            health_evidence_available
            and health_ok is True
            and error_rate <= 1
            and client_error_rate <= 5
            and p95 <= 0.1
        ),

        # ----------------------------------------------------
        # Safe fallback
        # ----------------------------------------------------

        "insufficient_evidence": True,
    }

    supported = bool(
        tests.get(name, False)
    )

    return {
        "hypothesis": name,
        "supported": supported,
        "status": (
            "supported"
            if supported
            else "rejected"
        ),
    }


# ============================================================
# Candidate hypothesis ordering
# ============================================================


def _candidate_order(
    alert: dict[str, Any],
    signals: dict[str, Any],
) -> list[str]:
    """
    Build an evidence-driven hypothesis order.

    Specific causes are tested before generic causes.

    Missing evidence does not create a hypothesis.
    """

    text = " ".join(
        str(value)
        for value in alert.values()
    ).lower()

    ordered: list[str] = []

    error_rate = _num(
        signals.get("error_rate")
    ) or 0.0

    client_error_rate = _num(
        signals.get("client_error_rate")
    ) or 0.0

    p95 = _num(
        signals.get("p95")
    ) or 0.0

    request_rate = _num(
        signals.get("request_rate")
    ) or 0.0

    container_state = signals.get(
        "container_state"
    )

    container_health = signals.get(
        "container_health"
    )

    try:
        restart_count = int(
            signals.get("restart_count")
            or 0
        )
    except (TypeError, ValueError):
        restart_count = 0

    health_ok = signals.get(
        "health_ok"
    )

    health_evidence_available = (
        signals.get(
            "health_evidence_available"
        )
        is True
    )

    container_evidence_available = (
        signals.get(
            "container_evidence_available"
        )
        is True
    )

    recent_deployment = (
        signals.get(
            "recent_deployment"
        )
        is True
    )

    bad_deployment = (
        signals.get(
            "bad_deployment"
        )
        is True
    )

    db_available = signals.get(
        "simulated_db_available"
    )

    postgres_available = signals.get(
        "postgres_available"
    )

    db_latency = _num(
        signals.get(
            "simulated_db_latency_ms"
        )
    ) or 0.0

    container_failure = (
        container_evidence_available
        and (
            container_state
            in {
                "restarting",
                "stopped",
                "unhealthy",
            }
            or container_health
            in {
                "unhealthy",
            }
            or restart_count >= 5
        )
    )

    # --------------------------------------------------------
    # 1. Deployment regression
    # --------------------------------------------------------

    if (
        recent_deployment
        and bad_deployment
        and (
            health_ok is False
            or error_rate > 5
            or p95 > 0.1
            or signals.get(
                "log_5xx_evidence",
                False,
            )
        )
    ):
        ordered.append(
            "deployment_regression"
        )

    # --------------------------------------------------------
    # 2. Database unavailable
    # --------------------------------------------------------

    if (
        db_available is False
        or postgres_available is False
    ):
        ordered.append(
            "database_unavailable"
        )

    # --------------------------------------------------------
    # 3. Database latency
    # --------------------------------------------------------

    if (
        db_latency > 200
        and p95 > 0.1
    ):
        ordered.append(
            "database_latency"
        )

    # --------------------------------------------------------
    # 4. Container failure
    # --------------------------------------------------------

    if container_failure:
        ordered.append(
            "container_failure"
        )

    # --------------------------------------------------------
    # 5. Service unavailable
    # --------------------------------------------------------

    # IMPORTANT:
    # Do not infer service_unavailable merely because
    # health data is missing.
    if (
        health_evidence_available
        and health_ok is False
        and not container_failure
    ):
        ordered.append(
            "service_unavailable"
        )

    # --------------------------------------------------------
    # 6. Traffic spike
    # --------------------------------------------------------

    if (
        request_rate > 5
        and (
            p95 > 0.1
            or error_rate > 1
        )
    ):
        ordered.append(
            "traffic_spike"
        )

    # --------------------------------------------------------
    # 7. Application errors
    # --------------------------------------------------------

    if (
        error_rate > 5
        or signals.get(
            "log_5xx_evidence",
            False,
        )
    ):
        ordered.append(
            "application_errors"
        )

    # --------------------------------------------------------
    # 8. Client errors
    # --------------------------------------------------------

    if (
        client_error_rate > 15
        and error_rate <= 5
    ):
        ordered.append(
            "client_errors"
        )

    # --------------------------------------------------------
    # 9. Generic latency
    # --------------------------------------------------------

    if p95 > 0.1:
        ordered.append(
            "latency_degradation"
        )

    # --------------------------------------------------------
    # Alert-text hints
    # --------------------------------------------------------

    if any(
        token in text
        for token in (
            "deploy",
            "rollback",
            "version",
        )
    ):
        ordered.append(
            "deployment_regression"
        )

    if any(
        token in text
        for token in (
            "container",
            "restart",
            "crash",
        )
    ):
        ordered.append(
            "container_failure"
        )

    if any(
        token in text
        for token in (
            "database",
            "postgres",
            "connection",
        )
    ):
        ordered.extend(
            [
                "database_unavailable",
                "database_latency",
            ]
        )

    if any(
        token in text
        for token in (
            "traffic",
            "spike",
            "load",
        )
    ):
        ordered.append(
            "traffic_spike"
        )

    if any(
        token in text
        for token in (
            "error",
            "500",
            "5xx",
        )
    ):
        ordered.append(
            "application_errors"
        )

    if any(
        token in text
        for token in (
            "latency",
            "slow",
            "timeout",
        )
    ):
        ordered.append(
            "latency_degradation"
        )

    if any(
        token in text
        for token in (
            "down",
            "unavailable",
        )
    ):
        # Alert text alone must NOT create
        # service_unavailable.
        #
        # Actual health evidence is required.
        if (
            health_evidence_available
            and health_ok is False
        ):
            ordered.append(
                "service_unavailable"
            )

    # --------------------------------------------------------
    # Safe fallbacks
    # --------------------------------------------------------

    ordered.append(
        "false_positive"
    )

    ordered.append(
        "insufficient_evidence"
    )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique: list[str] = []

    for item in ordered:
        if item not in unique:
            unique.append(item)

    return unique


# ============================================================
# Confidence calculation
# ============================================================


def _calculate_confidence(
    cause: str,
    signals: dict[str, Any],
) -> float:
    """
    Calculate confidence based on evidence strength.

    High-impact actions should have stronger evidence than
    simple alert-text matching.
    """

    if cause in {
        "insufficient_evidence",
        "false_positive",
    }:
        return 0.40

    evidence_count = 0

    if signals.get(
        "health_evidence_available"
    ):
        evidence_count += 1

    if signals.get(
        "container_evidence_available"
    ):
        evidence_count += 1

    if signals.get(
        "deployment_evidence_available"
    ):
        evidence_count += 1

    if signals.get(
        "database_evidence_available"
    ):
        evidence_count += 1

    if signals.get(
        "log_5xx_evidence"
    ):
        evidence_count += 1

    if (
        signals.get("error_rate")
        is not None
    ):
        evidence_count += 1

    if (
        signals.get("p95")
        is not None
    ):
        evidence_count += 1

    if (
        signals.get("request_rate")
        is not None
    ):
        evidence_count += 1

    # Strong multi-signal evidence.
    if evidence_count >= 4:
        return 0.90

    if evidence_count >= 3:
        return 0.86

    if evidence_count >= 2:
        return 0.78

    # One actual piece of evidence is still usable,
    # but confidence must be lower.
    if evidence_count == 1:
        return 0.70

    return 0.40


# ============================================================
# Diagnosis
# ============================================================


def diagnose_from_signals(
    alert: dict[str, Any],
    signals: dict[str, Any],
) -> dict[str, Any]:
    """
    Test hypotheses sequentially until evidence supports one.

    If no hypothesis is supported by real evidence,
    the investigation safely ends with insufficient_evidence.
    """

    candidates = _candidate_order(
        alert,
        signals,
    )

    tests: list[dict[str, Any]] = []

    accepted: str | None = None
    changed_direction = False

    for hypothesis in candidates:
        test = _test_hypothesis(
            hypothesis,
            signals,
        )

        tests.append(test)

        if (
            test["supported"]
            and hypothesis
            != "insufficient_evidence"
        ):
            accepted = hypothesis
            break

        changed_direction = True

    if accepted is None:
        accepted = (
            "insufficient_evidence"
        )

    (
        action_type,
        recommendation,
        impact,
    ) = _recommend(accepted)

    confidence = _calculate_confidence(
        accepted,
        signals,
    )

    if (
        changed_direction
        and accepted
        != "insufficient_evidence"
        and accepted
        != "false_positive"
    ):
        confidence = max(
            0.55,
            confidence - 0.05,
        )

    return {
        "likely_cause": accepted,
        "tests": tests,
        "changed_direction": (
            changed_direction
        ),
        "action_type": action_type,
        "recommended_action": (
            recommendation
        ),
        "expected_impact": impact,
        "approval_required": (
            requires_approval(
                action_type
            )
        ),
        "confidence": confidence,
        "tools_would_select": (
            select_tools(alert)
        ),
    }


# ============================================================
# Recommendation mapping
# ============================================================


def _recommend(
    cause: str,
) -> tuple[str, str, str]:

    mapping = {
        "deployment_regression": (
            "rollback",
            (
                "Roll back the simulated service "
                "to the previous known-good version."
            ),
            (
                "Reverts the latest deployment; "
                "in-flight requests may fail briefly."
            ),
        ),

        "container_failure": (
            "restart",
            (
                "Restart the simulated API "
                "container/process to clear "
                "the unhealthy state."
            ),
            (
                "Restarts the service process; "
                "brief unavailability is expected."
            ),
        ),

        "traffic_spike": (
            "scale",
            (
                "Scale the simulated service "
                "replicas to absorb excess traffic."
            ),
            (
                "Increases replica count in the "
                "simulated environment."
            ),
        ),

        "database_unavailable": (
            "escalate",
            (
                "Escalate: do not run destructive "
                "database operations. Investigate "
                "database availability."
            ),
            "No infrastructure mutation.",
        ),

        "database_latency": (
            "escalate",
            (
                "Escalate database latency to a "
                "human operator; do not rewrite "
                "or drop data."
            ),
            "No infrastructure mutation.",
        ),

        "application_errors": (
            "restart",
            (
                "Restart the service after "
                "confirming error patterns in logs."
            ),
            (
                "Restarts the service process; "
                "brief unavailability is expected."
            ),
        ),

        "client_errors": (
            "observe",
            (
                "Continue monitoring. Client 4xx "
                "errors often indicate invalid "
                "traffic rather than a server fault."
            ),
            "No infrastructure mutation.",
        ),

        "latency_degradation": (
            "observe",
            (
                "Keep the service up and continue "
                "gathering latency evidence before "
                "a high-impact action."
            ),
            "No infrastructure mutation.",
        ),

        "service_unavailable": (
            "restart",
            (
                "Restart the unavailable service "
                "after confirming container and "
                "dependency state."
            ),
            (
                "Restarts the service process; "
                "brief unavailability is expected."
            ),
        ),

        "false_positive": (
            "observe",
            (
                "No recovery action. Treat as a "
                "false positive or insufficient-"
                "impact signal."
            ),
            "No infrastructure mutation.",
        ),

        "insufficient_evidence": (
            "escalate",
            (
                "Stop safely and escalate. "
                "Evidence is insufficient for "
                "a high-impact action."
            ),
            "No infrastructure mutation.",
        ),
    }

    return mapping.get(
        cause,
        mapping["insufficient_evidence"],
    )


# ============================================================
# Main investigation workflow
# ============================================================


async def run_investigation(
    *,
    alert: dict[str, Any],
    incident_id: int | None = None,
) -> Investigation:
    """
    Complete read-only investigation workflow.

    Alert
      ↓
    Tool selection
      ↓
    Diagnostics
      ↓
    Signal extraction
      ↓
    Follow-up diagnostics
      ↓
    Hypothesis testing
      ↓
    Diagnosis
      ↓
    Recommendation
      ↓
    Human approval if required

    IMPORTANT:
    This function NEVER executes recovery actions.
    """

    INVESTIGATIONS_STARTED.inc()

    investigation = Investigation(
        incident_id=incident_id,
        alert_id=str(
            alert.get("alert_id")
            or alert.get("fingerprint")
            or ""
        ),
        service_name=str(
            alert.get("service_name")
            or "simulated-api-service"
        ),
        stage="INVESTIGATING",
        status="INVESTIGATING",
    )

    with Session(engine) as session:
        session.add(investigation)
        session.commit()
        session.refresh(investigation)

        investigation_id = investigation.id

        if investigation_id is None:
            raise RuntimeError(
                "Investigation ID was not generated."
            )

        _log_event(
            session,
            investigation,
            "alert_received",
            details=_summary(alert),
        )

        session.commit()

    # --------------------------------------------------------
    # Initial tool selection
    # --------------------------------------------------------

    initial_tools = select_tools(alert)

    if "service_health" not in initial_tools:
        initial_tools.insert(
            0,
            "service_health",
        )

    if "prometheus_metrics" not in initial_tools:
        initial_tools.insert(
            1,
            "prometheus_metrics",
        )

    # --------------------------------------------------------
    # Audit selected tools
    # --------------------------------------------------------

    with Session(engine) as session:
        investigation = session.get(
            Investigation,
            investigation_id,
        )

        if investigation is not None:
            _log_event(
                session,
                investigation,
                "tools_selected",
                details=json.dumps(
                    initial_tools
                ),
                decision=(
                    "Selected initial diagnostic "
                    "tools from the alert."
                ),
            )

            session.commit()

    # --------------------------------------------------------
    # Initial diagnostics
    # --------------------------------------------------------

    evidence: dict[str, Any] = {}

    for tool in initial_tools:
        result = await _run_tool(tool)

        evidence[tool] = result

        with Session(engine) as session:
            investigation = session.get(
                Investigation,
                investigation_id,
            )

            if investigation is None:
                continue

            _log_event(
                session,
                investigation,
                "diagnostic_step",
                tool_name=tool,
                tool_input="{}",
                tool_result_summary=_summary(
                    result
                ),
                evidence=_summary(
                    result.get("result")
                ),
            )

            session.commit()

    # --------------------------------------------------------
    # Initial signal extraction
    # --------------------------------------------------------

    signals = _extract_signals(
        evidence
    )

    # --------------------------------------------------------
    # Evidence-driven follow-up
    # --------------------------------------------------------

    follow_up: list[str] = []

    error_rate = (
        signals.get("error_rate")
        or 0
    )

    health_ok = signals.get(
        "health_ok"
    )

    p95 = (
        signals.get("p95")
        or 0
    )

    # Error or confirmed unhealthy service.
    if (
        error_rate > 1
        or health_ok is False
    ):
        follow_up.extend(
            [
                "structured_logs",
                "container_health",
                "deployments",
                "database_signals",
            ]
        )

    # Latency degradation.
    if p95 > 0.1:
        follow_up.extend(
            [
                "database_signals",
                "container_health",
            ]
        )

    # --------------------------------------------------------
    # Remove duplicate follow-up tools
    # --------------------------------------------------------

    follow_up_unique: list[str] = []

    for tool in follow_up:
        if tool not in follow_up_unique:
            follow_up_unique.append(tool)

    # --------------------------------------------------------
    # Follow-up diagnostics
    # --------------------------------------------------------

    for tool in follow_up_unique:
        if tool in evidence:
            continue

        result = await _run_tool(tool)

        evidence[tool] = result

        with Session(engine) as session:
            investigation = session.get(
                Investigation,
                investigation_id,
            )

            if investigation is None:
                continue

            _log_event(
                session,
                investigation,
                "diagnostic_step",
                tool_name=tool,
                tool_input=(
                    '{"reason":'
                    '"follow_up_from_evidence"}'
                ),
                tool_result_summary=_summary(
                    result
                ),
                evidence=_summary(
                    result.get("result")
                ),
                decision=(
                    "Additional diagnostic tool "
                    "selected after reviewing evidence."
                ),
            )

            session.commit()

    # --------------------------------------------------------
    # Final signals
    # --------------------------------------------------------

    signals = _extract_signals(
        evidence
    )

    # --------------------------------------------------------
    # Diagnosis
    # --------------------------------------------------------

    diagnosis_state = diagnose_from_signals(
        alert,
        signals,
    )

    tests = diagnosis_state[
        "tests"
    ]

    accepted = diagnosis_state[
        "likely_cause"
    ]

    action_type = diagnosis_state[
        "action_type"
    ]

    recommendation = diagnosis_state[
        "recommended_action"
    ]

    impact = diagnosis_state[
        "expected_impact"
    ]

    approval_needed = diagnosis_state[
        "approval_required"
    ]

    confidence = diagnosis_state[
        "confidence"
    ]

    # --------------------------------------------------------
    # Audit hypothesis testing
    # --------------------------------------------------------

    for test in tests:
        with Session(engine) as session:
            investigation = session.get(
                Investigation,
                investigation_id,
            )

            if investigation is None:
                continue

            _log_event(
                session,
                investigation,
                "hypothesis",
                hypothesis=test[
                    "hypothesis"
                ],
                hypothesis_status=test[
                    "status"
                ],
                evidence=_summary(
                    signals
                ),
                decision=(
                    "Hypothesis supported by "
                    "current evidence."
                    if test["supported"]
                    else (
                        "Hypothesis rejected; "
                        "changing direction."
                    )
                ),
            )

            session.commit()

    # --------------------------------------------------------
    # Human-readable diagnosis
    # --------------------------------------------------------

    diagnosis = (
        f"Likely cause: {accepted}. "
        f"Health OK={signals.get('health_ok')}, "
        f"Health evidence="
        f"{signals.get('health_evidence_available')}, "
        f"5xx={signals.get('error_rate')}, "
        f"p95={signals.get('p95')}, "
        f"request_rate="
        f"{signals.get('request_rate')}, "
        f"version="
        f"{signals.get('current_version')}, "
        f"container="
        f"{signals.get('container_state')}/"
        f"{signals.get('container_health')}."
    )

    approval: ApprovalRequest | None = None

    # --------------------------------------------------------
    # Persist final state
    # --------------------------------------------------------

    with Session(engine) as session:
        investigation = session.get(
            Investigation,
            investigation_id,
        )

        if investigation is None:
            raise RuntimeError(
                "Investigation could not be reloaded."
            )

        investigation.stage = (
            "AWAITING_APPROVAL"
            if approval_needed
            else "DIAGNOSING"
        )

        investigation.status = (
            "AWAITING_APPROVAL"
            if approval_needed
            else "RECOMMENDED"
        )

        investigation.likely_cause = accepted
        investigation.confidence = confidence
        investigation.recommended_action = (
            recommendation
        )
        investigation.recommended_action_type = (
            action_type
        )
        investigation.approval_required = (
            approval_needed
        )
        investigation.approval_status = (
            "pending"
            if approval_needed
            else "not_required"
        )
        investigation.diagnosis = diagnosis
        investigation.updated_at = _now()

        session.add(investigation)

        _log_event(
            session,
            investigation,
            "diagnosis",
            hypothesis=accepted,
            hypothesis_status="accepted",
            confidence=confidence,
            decision=diagnosis,
        )

        _log_event(
            session,
            investigation,
            "recommendation",
            decision=recommendation,
            details=json.dumps(
                {
                    "action_type": action_type,
                    "approval_required": (
                        approval_needed
                    ),
                    "expected_impact": impact,
                    "tests": tests,
                },
                default=str,
            ),
        )

        # ----------------------------------------------------
        # Human approval
        # ----------------------------------------------------

        if approval_needed:
            approval = ApprovalRequest(
                investigation_id=investigation_id,
                incident_id=(
                    investigation.incident_id
                ),
                action_type=action_type,
                reason=recommendation,
                evidence_summary=_summary(
                    signals
                ),
                expected_impact=impact,
                status="pending",
                execution_status="blocked",
            )

            session.add(approval)

            APPROVAL_REQUESTS.labels(
                action=action_type
            ).inc()

            _log_event(
                session,
                investigation,
                "approval_requested",
                decision=action_type,
                details=(
                    "High-impact action blocked "
                    "until explicit human approval."
                ),
            )

        session.commit()
        session.refresh(investigation)

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    INVESTIGATIONS_COMPLETED.labels(
        outcome=(
            "awaiting_approval"
            if approval_needed
            else "recommended"
        )
    ).inc()

    return investigation


# ============================================================
# Full diagnostics helper
# ============================================================


async def collect_and_snapshot() -> dict[str, Any]:
    """
    Collect the complete read-only diagnostic snapshot.
    """

    try:
        result = await collect_full_diagnostics()

        if isinstance(result, dict):
            return result

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "result": None,
        }