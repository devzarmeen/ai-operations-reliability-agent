from __future__ import annotations

import pytest

from app.agent.investigation import (
    _candidate_order,
    _extract_signals,
    _test_hypothesis,
    diagnose_from_signals,
)


# ============================================================
# Helpers
# ============================================================


def base_signals() -> dict:
    """
    Healthy baseline signals.
    Individual scenarios override only what they need.
    """

    return {
        "error_rate": 0.0,
        "client_error_rate": 0.0,
        "p95": 0.02,
        "request_rate": 1.0,

        "health_ok": True,
        "health_evidence_available": True,

        "container_state": "running",
        "container_health": "healthy",
        "restart_count": 0,
        "container_evidence_available": True,

        "current_version": "v1.0.0",
        "recent_deployment": False,
        "bad_deployment": False,
        "deployed_at": None,
        "deployment_evidence_available": True,

        "simulated_db_available": True,
        "simulated_db_latency_ms": 20.0,
        "postgres_available": True,
        "database_evidence_available": True,

        "repeated_errors": [],
        "error_patterns": [],

        "log_5xx_evidence": False,
        "log_client_error_evidence": False,
    }


def alert(name: str, summary: str) -> dict:
    return {
        "alert_id": f"test-{name}",
        "alert_name": name,
        "status": "firing",
        "severity": "critical",
        "service_name": "simulated-api-service",
        "summary": summary,
        "reason": summary,
    }


def run_case(
    name: str,
    summary: str,
    overrides: dict,
    expected_cause: str,
    expected_action: str,
):
    """
    Execute one diagnosis scenario against the real
    investigation decision logic.
    """

    signals = base_signals()
    signals.update(overrides)

    result = diagnose_from_signals(
        alert(name, summary),
        signals,
    )

    assert result["likely_cause"] == expected_cause

    assert result["action_type"] == expected_action

    assert "recommended_action" in result

    assert "confidence" in result

    assert isinstance(
        result["tests"],
        list,
    )

    assert len(result["tests"]) >= 1

    return result


# ============================================================
# 01. Normal / healthy service
# ============================================================


def test_01_normal_healthy_service():
    result = run_case(
        "Normal Service",
        "Service is healthy",
        {},
        "false_positive",
        "observe",
    )

    assert result["approval_required"] is False


# ============================================================
# 02. High 5xx error rate
# ============================================================


def test_02_high_error_rate():
    result = run_case(
        "High Error Rate",
        "Simulated API has elevated 5xx errors",
        {
            "error_rate": 25.0,
            "log_5xx_evidence": True,
        },
        "application_errors",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 03. Low 5xx but strong 4xx/client errors
# ============================================================


def test_03_client_error_spike():
    result = run_case(
        "High Client Error Rate",
        "API has elevated 400/4xx client errors",
        {
            "error_rate": 1.0,
            "client_error_rate": 35.0,
            "log_client_error_evidence": True,
        },
        "client_errors",
        "observe",
    )

    assert result["approval_required"] is False


# ============================================================
# 04. Deployment regression
# ============================================================


def test_04_deployment_regression():
    result = run_case(
        "Deployment Regression",
        "Errors started after recent deployment",
        {
            "error_rate": 20.0,
            "recent_deployment": True,
            "bad_deployment": True,
            "current_version": "v2.0.0",
            "log_5xx_evidence": True,
        },
        "deployment_regression",
        "rollback",
    )

    assert result["approval_required"] is True


# ============================================================
# 05. Container stopped
# ============================================================


def test_05_container_stopped():
    result = run_case(
        "Container Failure",
        "Container stopped unexpectedly",
        {
            "health_ok": False,
            "container_state": "stopped",
            "container_health": "unhealthy",
        },
        "container_failure",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 06. Container restarting
# ============================================================


def test_06_container_restarting():
    result = run_case(
        "Container Restart Loop",
        "Container is repeatedly restarting",
        {
            "health_ok": False,
            "container_state": "restarting",
            "restart_count": 8,
        },
        "container_failure",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 07. Unhealthy container
# ============================================================


def test_07_container_unhealthy():
    result = run_case(
        "Unhealthy Container",
        "Container health check is failing",
        {
            "health_ok": False,
            "container_state": "running",
            "container_health": "unhealthy",
        },
        "container_failure",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 08. Database unavailable
# ============================================================


def test_08_database_unavailable():
    result = run_case(
        "Database Unavailable",
        "Database connection unavailable",
        {
            "simulated_db_available": False,
            "postgres_available": False,
            "error_rate": 10.0,
        },
        "database_unavailable",
        "escalate",
    )

    assert result["approval_required"] is False


# ============================================================
# 09. Database latency
# ============================================================


def test_09_database_latency():
    result = run_case(
        "Database Latency",
        "Database queries are slow",
        {
            "simulated_db_available": True,
            "postgres_available": True,
            "simulated_db_latency_ms": 500.0,
            "p95": 0.8,
        },
        "database_latency",
        "escalate",
    )

    assert result["approval_required"] is False


# ============================================================
# 10. General latency degradation
# ============================================================


def test_10_latency_degradation():
    result = run_case(
        "High Latency",
        "API latency is degraded",
        {
            "p95": 0.5,
            "simulated_db_latency_ms": 100.0,
        },
        "latency_degradation",
        "observe",
    )

    assert result["approval_required"] is False


# ============================================================
# 11. Traffic spike
# ============================================================


def test_11_traffic_spike():
    result = run_case(
        "Traffic Spike",
        "Traffic spike detected",
        {
            "request_rate": 10.0,
            "p95": 0.3,
            "error_rate": 2.0,
        },
        "traffic_spike",
        "scale",
    )

    assert result["approval_required"] is True


# ============================================================
# 12. Service unavailable
# ============================================================


def test_12_service_unavailable():
    result = run_case(
        "Service Unavailable",
        "Service is unavailable",
        {
            "health_ok": False,
            "container_state": "running",
            "container_health": "healthy",
            "restart_count": 0,
        },
        "service_unavailable",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 13. Alert with no meaningful evidence
# ============================================================


def test_13_insufficient_evidence():
    signals = {
        "error_rate": None,
        "client_error_rate": None,
        "p95": None,
        "request_rate": None,

        "health_ok": None,
        "health_evidence_available": False,

        "container_state": None,
        "container_health": None,
        "restart_count": None,
        "container_evidence_available": False,

        "current_version": None,
        "recent_deployment": None,
        "bad_deployment": None,
        "deployed_at": None,
        "deployment_evidence_available": False,

        "simulated_db_available": None,
        "simulated_db_latency_ms": None,
        "postgres_available": None,
        "database_evidence_available": False,

        "repeated_errors": [],
        "error_patterns": [],
        "log_5xx_evidence": False,
        "log_client_error_evidence": False,
    }

    result = diagnose_from_signals(
        alert(
            "Unknown Alert",
            "Something may be wrong",
        ),
        signals,
    )

    assert result["likely_cause"] == "insufficient_evidence"

    assert result["action_type"] == "escalate"

    assert result["approval_required"] is False


# ============================================================
# 14. Log-confirmed 5xx errors
# ============================================================


def test_14_log_confirmed_5xx():
    result = run_case(
        "Application Error Logs",
        "Repeated server exceptions found in logs",
        {
            "error_rate": 2.0,
            "log_5xx_evidence": True,
        },
        "application_errors",
        "restart",
    )

    assert result["approval_required"] is True


# ============================================================
# 15. 4xx spike must NOT become application error
# ============================================================


def test_15_4xx_does_not_become_5xx():
    result = run_case(
        "HTTP 400 Spike",
        "Large number of HTTP 400 requests",
        {
            "error_rate": 0.5,
            "client_error_rate": 40.0,
            "log_client_error_evidence": True,
            "log_5xx_evidence": False,
        },
        "client_errors",
        "observe",
    )

    assert result["likely_cause"] != "application_errors"


# ============================================================
# 16. Deployment hint without supporting evidence
# ============================================================


def test_16_deployment_hint_without_evidence():
    result = run_case(
        "Deployment Alert",
        "Deployment may be related to issue",
        {
            "recent_deployment": False,
            "bad_deployment": False,
            "error_rate": 0.0,
            "p95": 0.02,
        },
        "false_positive",
        "observe",
    )

    assert result["approval_required"] is False


# ============================================================
# 17. Database alert but database is healthy
# ============================================================


def test_17_healthy_database():
    result = run_case(
        "Database Alert",
        "Database performance warning",
        {
            "simulated_db_available": True,
            "postgres_available": True,
            "simulated_db_latency_ms": 30.0,
            "p95": 0.03,
        },
        "false_positive",
        "observe",
    )

    assert result["approval_required"] is False


# ============================================================
# 18. High traffic + high latency
# ============================================================


def test_18_high_traffic_latency():
    result = run_case(
        "Traffic and Latency",
        "Traffic load is causing latency",
        {
            "request_rate": 15.0,
            "p95": 0.5,
            "error_rate": 2.0,
        },
        "traffic_spike",
        "scale",
    )

    assert result["approval_required"] is True


# ============================================================
# 19. Multiple symptoms: deployment should win
# ============================================================


def test_19_deployment_wins_over_generic_application_error():
    result = run_case(
        "Deployment Regression",
        "High errors after deployment",
        {
            "error_rate": 30.0,
            "p95": 0.5,
            "recent_deployment": True,
            "bad_deployment": True,
            "log_5xx_evidence": True,
        },
        "deployment_regression",
        "rollback",
    )

    assert result["likely_cause"] != "application_errors"


# ============================================================
# 20. Multiple symptoms: database outage should win
# ============================================================


def test_20_database_outage_wins_over_application_error():
    result = run_case(
        "Database Outage",
        "API errors caused by database outage",
        {
            "error_rate": 30.0,
            "simulated_db_available": False,
            "postgres_available": False,
            "log_5xx_evidence": True,
        },
        "database_unavailable",
        "escalate",
    )

    assert result["likely_cause"] != "application_errors"


# ============================================================
# Additional core logic tests
# ============================================================


def test_extract_signals_preserves_missing_as_none():
    evidence = {
        "prometheus_metrics": {
            "ok": True,
            "result": {
                "metrics": {}
            },
        }
    }

    signals = _extract_signals(evidence)

    assert signals["error_rate"] is None
    assert signals["client_error_rate"] is None
    assert signals["p95"] is None
    assert signals["request_rate"] is None

    assert signals["health_ok"] is None


def test_candidate_order_removes_duplicates():
    signals = base_signals()

    signals.update(
        {
            "error_rate": 20.0,
            "recent_deployment": True,
            "bad_deployment": True,
        }
    )

    candidates = _candidate_order(
        alert(
            "Deployment Error",
            "Deployment caused 5xx errors",
        ),
        signals,
    )

    assert len(candidates) == len(set(candidates))


def test_hypothesis_missing_evidence_is_not_false():
    signals = base_signals()

    signals.update(
        {
            "health_ok": None,
            "health_evidence_available": False,
            "error_rate": None,
            "client_error_rate": None,
            "p95": None,
            "request_rate": None,
            "container_evidence_available": False,
            "deployment_evidence_available": False,
            "database_evidence_available": False,
            "log_5xx_evidence": False,
        }
    )

    result = _test_hypothesis(
        "service_unavailable",
        signals,
    )

    assert result["supported"] is False


# ============================================================
# Full test count
# ============================================================


def test_99_suite_contains_expected_scenarios():
    """
    Documentation/guard test.

    The main suite contains 20 required failure scenarios
    plus focused unit tests for core investigation behavior.
    """

    required_tests = [
        test_01_normal_healthy_service,
        test_02_high_error_rate,
        test_03_client_error_spike,
        test_04_deployment_regression,
        test_05_container_stopped,
        test_06_container_restarting,
        test_07_container_unhealthy,
        test_08_database_unavailable,
        test_09_database_latency,
        test_10_latency_degradation,
        test_11_traffic_spike,
        test_12_service_unavailable,
        test_13_insufficient_evidence,
        test_14_log_confirmed_5xx,
        test_15_4xx_does_not_become_5xx,
        test_16_deployment_hint_without_evidence,
        test_17_healthy_database,
        test_18_high_traffic_latency,
        test_19_deployment_wins_over_generic_application_error,
        test_20_database_outage_wins_over_application_error,
    ]

    assert len(required_tests) == 20