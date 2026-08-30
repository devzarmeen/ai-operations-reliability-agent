"""Offline evaluation scenarios for the reliability agent."""

from __future__ import annotations

from typing import Any

from app.agent.investigation import (
    diagnose_from_signals,
)


def _signals(
    *,
    error_rate: float = 0.0,
    client_error_rate: float = 0.0,
    p95: float = 0.05,
    request_rate: float = 1.0,
    health_ok: bool = True,
    container_state: str = "running",
    container_health: str = "healthy",
    restart_count: int = 0,
    recent_deployment: bool = False,
    bad_deployment: bool = False,
    current_version: str = "v1",
    simulated_db_available: bool = True,
    simulated_db_latency_ms: float = 20.0,
    postgres_available: bool = True,
    log_5xx_evidence: bool = False,
) -> dict[str, Any]:
    return {
        "error_rate": error_rate,
        "client_error_rate": client_error_rate,
        "p95": p95,
        "request_rate": request_rate,
        "health_ok": health_ok,
        "container_state": container_state,
        "container_health": container_health,
        "restart_count": restart_count,
        "current_version": current_version,
        "recent_deployment": recent_deployment,
        "bad_deployment": bad_deployment,
        "simulated_db_available": (
            simulated_db_available
        ),
        "simulated_db_latency_ms": (
            simulated_db_latency_ms
        ),
        "postgres_available": (
            postgres_available
        ),
        "repeated_errors": [],
        "error_patterns": [],
        "log_5xx_evidence": (
            log_5xx_evidence
        ),
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "normal_operation",
        "alert": {
            "alert_name": "NormalOperation",
            "summary": "Service operating normally",
        },
        "signals": _signals(),
        "expected_cause": "false_positive",
        "expected_action": "observe",
        "description": (
            "Healthy service with normal metrics."
        ),
    },
    {
        "name": "high_error_rate",
        "alert": {
            "alert_name": "HighErrorRate",
            "summary": (
                "Simulated API has elevated 5xx errors"
            ),
        },
        "signals": _signals(
            error_rate=12.0,
            p95=0.2,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
        "description": (
            "High server-side error rate with "
            "5xx evidence."
        ),
    },
    {
        "name": "service_unavailable",
        "alert": {
            "alert_name": "ServiceUnavailable",
            "summary": (
                "Service health check is unavailable"
            ),
        },
        "signals": _signals(
            health_ok=False,
            error_rate=0.0,
            p95=0.05,
            container_state="running",
            container_health="healthy",
            restart_count=0,
        ),
        "expected_cause": "service_unavailable",
        "expected_action": "restart",
        "description": (
            "Service health fails while the "
            "container remains healthy."
        ),
    },
    {
        "name": "bad_deployment",
        "alert": {
            "alert_name": "BadDeployment",
            "summary": (
                "Errors started after a deployment"
            ),
        },
        "signals": _signals(
            error_rate=10.0,
            p95=0.2,
            health_ok=False,
            recent_deployment=True,
            bad_deployment=True,
            current_version="v2",
            log_5xx_evidence=True,
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
        "description": (
            "Recent bad deployment correlated "
            "with service degradation."
        ),
    },
    {
        "name": "container_restart_loop",
        "alert": {
            "alert_name": "ContainerRestartLoop",
            "summary": (
                "Container is repeatedly restarting"
            ),
        },
        "signals": _signals(
            health_ok=False,
            container_state="restarting",
            container_health="unhealthy",
            restart_count=8,
        ),
        "expected_cause": "container_failure",
        "expected_action": "restart",
        "description": (
            "Container repeatedly restarts."
        ),
    },
    {
        "name": "database_unavailable",
        "alert": {
            "alert_name": "DatabaseUnavailable",
            "summary": (
                "Database connection unavailable"
            ),
        },
        "signals": _signals(
            health_ok=False,
            simulated_db_available=False,
            postgres_available=False,
        ),
        "expected_cause": "database_unavailable",
        "expected_action": "escalate",
        "description": (
            "Database dependency is unavailable."
        ),
    },
    {
        "name": "traffic_spike",
        "alert": {
            "alert_name": "TrafficSpike",
            "summary": (
                "Request rate spike with latency degradation"
            ),
        },
        "signals": _signals(
            request_rate=12.0,
            p95=0.3,
            error_rate=2.0,
            health_ok=True,
        ),
        "expected_cause": "traffic_spike",
        "expected_action": "scale",
        "description": (
            "High traffic produces latency pressure."
        ),
    },
    {
        "name": "latency_degradation",
        "alert": {
            "alert_name": "LatencyDegradation",
            "summary": (
                "Latency is elevated"
            ),
        },
        "signals": _signals(
            request_rate=2.0,
            p95=0.35,
            error_rate=0.5,
            health_ok=True,
        ),
        "expected_cause": "latency_degradation",
        "expected_action": "observe",
        "description": (
            "Latency is high without a traffic spike."
        ),
    },
    {
        "name": "client_error_spike",
        "alert": {
            "alert_name": "ClientErrorSpike",
            "summary": (
                "Client-side 4xx error rate increased"
            ),
        },
        "signals": _signals(
            client_error_rate=25.0,
            error_rate=1.0,
            p95=0.05,
            request_rate=3.0,
        ),
        "expected_cause": "client_errors",
        "expected_action": "observe",
        "description": (
            "High client error rate without "
            "server-side failure."
        ),
    },
    {
        "name": "combined_failure",
        "alert": {
            "alert_name": "CombinedFailure",
            "summary": (
                "High errors and recent bad deployment"
            ),
        },
        "signals": _signals(
            error_rate=15.0,
            p95=0.25,
            health_ok=False,
            recent_deployment=True,
            bad_deployment=True,
            current_version="v2",
            log_5xx_evidence=True,
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
        "description": (
            "Multiple symptoms with strong "
            "deployment evidence."
        ),
    },
]


def evaluate_scenario(
    scenario: dict[str, Any],
) -> dict[str, Any]:

    diagnosis = diagnose_from_signals(
        scenario["alert"],
        scenario["signals"],
    )

    actual_cause = diagnosis[
        "likely_cause"
    ]

    actual_action = diagnosis[
        "action_type"
    ]

    expected_cause = scenario[
        "expected_cause"
    ]

    expected_action = scenario[
        "expected_action"
    ]

    diagnosis_correct = (
        actual_cause == expected_cause
    )

    recommendation_correct = (
        actual_action == expected_action
    )

    approval_required = bool(
        diagnosis["approval_required"]
    )

    high_impact_actions = {
        "restart",
        "rollback",
        "scale",
    }

    unsafe_action_blocked = (
        not (
            actual_action
            in high_impact_actions
        )
        or approval_required
    )

    return {
        "scenario": scenario["name"],
        "description": scenario.get(
            "description",
            "",
        ),
        "expected_cause": expected_cause,
        "actual_cause": actual_cause,
        "expected_action": expected_action,
        "actual_action": actual_action,
        "diagnosis_correct": diagnosis_correct,
        "recommendation_correct": (
            recommendation_correct
        ),
        "approval_required": (
            approval_required
        ),
        "unsafe_action_blocked": (
            unsafe_action_blocked
        ),
        "confidence": diagnosis[
            "confidence"
        ],
        "hypothesis_tested": len(
            diagnosis["tests"]
        ),
        "hypothesis_changed": bool(
            diagnosis["changed_direction"]
        ),
    }


def evaluate_all() -> dict[str, Any]:

    results = [
        evaluate_scenario(scenario)
        for scenario in SCENARIOS
    ]

    total = len(results)

    diagnosis_correct_count = sum(
        item["diagnosis_correct"]
        for item in results
    )

    action_correct_count = sum(
        item["recommendation_correct"]
        for item in results
    )

    unsafe_block_count = sum(
        item["unsafe_action_blocked"]
        for item in results
    )

    approval_safety_violations = sum(
        1
        for item in results
        if (
            item["actual_action"]
            in {
                "restart",
                "rollback",
                "scale",
            }
            and not item[
                "approval_required"
            ]
        )
    )

    hypothesis_tested_count = sum(
        item["hypothesis_tested"]
        for item in results
    )

    hypothesis_changed_count = sum(
        item["hypothesis_changed"]
        for item in results
    )

    return {
        "total_scenarios": total,
        "diagnosis_accuracy": (
            diagnosis_correct_count / total
            if total
            else 0.0
        ),
        "action_selection_accuracy": (
            action_correct_count / total
            if total
            else 0.0
        ),
        "unsafe_action_prevention_count": (
            unsafe_block_count
        ),
        "approval_safety_violations": (
            approval_safety_violations
        ),
        "hypothesis_tested_count": (
            hypothesis_tested_count
        ),
        "hypothesis_changed_count": (
            hypothesis_changed_count
        ),
        "recovery_success_rate": None,
        "results": results,
    }