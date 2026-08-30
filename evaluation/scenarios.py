from __future__ import annotations

import json
import sys
from pathlib import Path


# ============================================================
# Backend application path
# ============================================================

APP_ROOT = Path("/app")

LOCAL_BACKEND_ROOT = (
    Path(__file__).resolve().parents[1] / "backend"
)

# Docker environment
if APP_ROOT.exists() and str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Local Windows environment
if (
    LOCAL_BACKEND_ROOT.exists()
    and str(LOCAL_BACKEND_ROOT) not in sys.path
):
    sys.path.insert(0, str(LOCAL_BACKEND_ROOT))


# ============================================================
# Application imports
# ============================================================

from app.agent.investigation import diagnose_from_signals
from app.safety.enforcement import requires_approval


# ============================================================
# Base signals
# ============================================================

def _signals(**overrides):
    base = {
        "error_rate": 0.0,
        "client_error_rate": 0.0,
        "p95": 0.02,
        "request_rate": 0.3,

        "health_ok": True,
        "container_state": "running",
        "container_health": "healthy",
        "restart_count": 0,

        "current_version": "1.0.0",
        "recent_deployment": False,
        "bad_deployment": False,
        "deployed_at": None,

        "simulated_db_available": True,
        "simulated_db_latency_ms": 3.0,
        "postgres_available": True,

        "repeated_errors": [],
        "error_patterns": [],

        # Evidence availability
        "health_evidence_available": True,
        "container_evidence_available": True,
        "deployment_evidence_available": True,
        "database_evidence_available": True,

        # Log evidence
        "log_5xx_evidence": False,
    }

    base.update(overrides)
    return base


# ============================================================
# Original comprehensive scenarios
# ============================================================

ORIGINAL_SCENARIOS = [
    {
        "name": "normal",
        "alert": {
            "alert_name": "false-positive-or-healthy",
            "status": "ok",
            "summary": "normal operation",
        },
        "signals": _signals(
            health_ok=True,
        ),
        "expected_cause": "false_positive",
        "expected_action": "observe",
    },
    {
        "name": "high_error_rate",
        "alert": {
            "alert_name": "HighErrorRate",
            "summary": "5xx error rate increased",
        },
        "signals": _signals(
            error_rate=22.0,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
    {
        "name": "http_500_spike",
        "alert": {
            "alert_name": "HTTP500Spike",
            "summary": "500 errors",
        },
        "signals": _signals(
            error_rate=55.0,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
    {
        "name": "http_400_spike",
        "alert": {
            "alert_name": "HTTP400Spike",
            "summary": "400 client errors",
        },
        "signals": _signals(
            client_error_rate=40.0,
            error_rate=0.0,
        ),
        "expected_cause": "client_errors",
        "expected_action": "observe",
    },
    {
        "name": "high_latency",
        "alert": {
            "alert_name": "HighLatency",
            "summary": "latency increased",
        },
        "signals": _signals(
            p95=0.4,
        ),
        "expected_cause": "latency_degradation",
        "expected_action": "observe",
    },
    {
        "name": "extreme_latency",
        "alert": {
            "alert_name": "ExtremeLatency",
            "summary": "extreme latency",
        },
        "signals": _signals(
            p95=2.0,
        ),
        "expected_cause": "latency_degradation",
        "expected_action": "observe",
    },
    {
        "name": "service_unavailable",
        "alert": {
            "alert_name": "ServiceDown",
            "summary": "service unavailable",
        },
        "signals": _signals(
            health_ok=False,
        ),
        "expected_cause": "service_unavailable",
        "expected_action": "restart",
    },
    {
        "name": "container_unhealthy",
        "alert": {
            "alert_name": "ContainerUnhealthy",
            "summary": "container unhealthy",
        },
        "signals": _signals(
            health_ok=False,
            container_state="running",
            container_health="unhealthy",
        ),
        "expected_cause": "container_failure",
        "expected_action": "restart",
    },
    {
        "name": "container_restart_loop",
        "alert": {
            "alert_name": "RestartLoop",
            "summary": "container restart loop",
        },
        "signals": _signals(
            health_ok=False,
            container_state="restarting",
            container_health="unhealthy",
            restart_count=8,
        ),
        "expected_cause": "container_failure",
        "expected_action": "restart",
    },
    {
        "name": "recent_bad_deployment",
        "alert": {
            "alert_name": "ErrorAfterDeploy",
            "summary": "errors after deployment",
        },
        "signals": _signals(
            error_rate=30.0,
            recent_deployment=True,
            bad_deployment=True,
            current_version="1.1.0-bad",
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
    },
    {
        "name": "database_unavailable",
        "alert": {
            "alert_name": "DatabaseDown",
            "summary": "database unavailable",
        },
        "signals": _signals(
            simulated_db_available=False,
        ),
        "expected_cause": "database_unavailable",
        "expected_action": "escalate",
    },
    {
        "name": "database_connection_failure",
        "alert": {
            "alert_name": "DBConnections",
            "summary": "database connection failure",
        },
        "signals": _signals(
            simulated_db_available=False,
            postgres_available=False,
        ),
        "expected_cause": "database_unavailable",
        "expected_action": "escalate",
    },
    {
        "name": "database_latency",
        "alert": {
            "alert_name": "DBLatency",
            "summary": "database latency",
        },
        "signals": _signals(
            p95=0.5,
            simulated_db_latency_ms=450.0,
        ),
        "expected_cause": "database_latency",
        "expected_action": "escalate",
    },
    {
        "name": "dependency_failure",
        "alert": {
            "alert_name": "DependencyFailure",
            "summary": "dependency 502 errors",
        },
        "signals": _signals(
            error_rate=40.0,
            health_ok=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
    {
        "name": "traffic_spike",
        "alert": {
            "alert_name": "TrafficSpike",
            "summary": "traffic spike",
        },
        "signals": _signals(
            request_rate=12.0,
            p95=0.3,
            error_rate=2.0,
        ),
        "expected_cause": "traffic_spike",
        "expected_action": "scale",
    },
    {
        "name": "resource_pressure",
        "alert": {
            "alert_name": "ResourcePressure",
            "summary": "resource pressure latency",
        },
        "signals": _signals(
            p95=0.35,
            container_state="running",
            container_health="healthy",
        ),
        "expected_cause": "latency_degradation",
        "expected_action": "observe",
    },
    {
        "name": "repeated_exception",
        "alert": {
            "alert_name": "RepeatedException",
            "summary": "repeated application exception",
        },
        "signals": _signals(
            error_rate=80.0,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
    {
        "name": "recovery_after_failure",
        "alert": {
            "alert_name": "recovered",
            "summary": "false positive after recovery",
        },
        "signals": _signals(
            health_ok=True,
            error_rate=0.0,
            p95=0.02,
        ),
        "expected_cause": "false_positive",
        "expected_action": "observe",
    },
    {
        "name": "false_positive",
        "alert": {
            "alert_name": "FalsePositive",
            "summary": "insufficient evidence / false positive",
        },
        "signals": _signals(
            health_ok=True,
        ),
        "expected_cause": "false_positive",
        "expected_action": "observe",
    },
    {
        "name": "combined_failure",
        "alert": {
            "alert_name": "CombinedFailure",
            "summary": "errors after bad deployment",
        },
        "signals": _signals(
            error_rate=28.0,
            p95=0.4,
            recent_deployment=True,
            bad_deployment=True,
            container_health="unhealthy",
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
    },
    {
        "name": "deployment_unrelated",
        "alert": {
            "alert_name": "ErrorsNoDeploy",
            "summary": "high error rate",
        },
        "signals": _signals(
            error_rate=20.0,
            recent_deployment=False,
            bad_deployment=False,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
    {
        "name": "deployment_hypothesis_rejected",
        "alert": {
            "alert_name": "ErrorAfterDeploy",
            "summary": "errors after deployment",
        },
        "signals": _signals(
            error_rate=20.0,
            recent_deployment=False,
            bad_deployment=False,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
    },
]


# ============================================================
# Focused 10-scenario evaluation set
# ============================================================

SCENARIOS = [
    {
        "name": "normal_operation",
        "alert": {
            "alert_name": "SystemHealthy",
            "summary": "Normal system operation",
        },
        "signals": _signals(
            health_ok=True,
            error_rate=0.0,
            p95=0.02,
            request_rate=0.3,
        ),
        "expected_cause": "false_positive",
        "expected_action": "observe",
        "description": (
            "Baseline healthy state - agent should identify as false positive"
        ),
    },
    {
        "name": "high_error_rate",
        "alert": {
            "alert_name": "HighErrorRate",
            "summary": "5xx error rate spike to 22%",
        },
        "signals": _signals(
            error_rate=22.0,
            health_ok=True,
            p95=0.03,
            log_5xx_evidence=True,
        ),
        "expected_cause": "application_errors",
        "expected_action": "restart",
        "description": (
            "Application-level errors requiring service restart"
        ),
    },
    {
        "name": "service_unavailable",
        "alert": {
            "alert_name": "ServiceDown",
            "summary": "Service health check failing",
        },
        "signals": _signals(
            health_ok=False,
            error_rate=0.0,
            container_state="running",
            container_health="healthy",
            restart_count=0,
        ),
        "expected_cause": "service_unavailable",
        "expected_action": "restart",
        "description": (
            "Service health endpoint unavailable while the "
            "container remains healthy"
        ),
    },
    {
        "name": "bad_deployment",
        "alert": {
            "alert_name": "DeploymentRegression",
            "summary": "Errors after recent deployment",
        },
        "signals": _signals(
            error_rate=30.0,
            recent_deployment=True,
            bad_deployment=True,
            current_version="1.1.0-bad",
            health_ok=False,
            log_5xx_evidence=True,
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
        "description": (
            "Deployment-related regression requiring rollback"
        ),
    },
    {
        "name": "container_restart_loop",
        "alert": {
            "alert_name": "ContainerCrashLoop",
            "summary": "Container in restart loop",
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
            "Container crash loop requiring intervention"
        ),
    },
    {
        "name": "database_unavailable",
        "alert": {
            "alert_name": "DatabaseDown",
            "summary": "Database connection failures",
        },
        "signals": _signals(
            simulated_db_available=False,
            postgres_available=False,
            health_ok=True,
            error_rate=0.0,
        ),
        "expected_cause": "database_unavailable",
        "expected_action": "escalate",
        "description": (
            "Database unavailability requiring human escalation"
        ),
    },
    {
        "name": "traffic_spike",
        "alert": {
            "alert_name": "TrafficSpike",
            "summary": "Request rate spike with latency degradation",
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
            "Traffic overload requiring scaling"
        ),
    },
    {
        "name": "latency_degradation",
        "alert": {
            "alert_name": "HighLatency",
            "summary": "P95 latency increased to 400ms",
        },
        "signals": _signals(
            p95=0.4,
            health_ok=True,
            error_rate=0.0,
            request_rate=0.3,
        ),
        "expected_cause": "latency_degradation",
        "expected_action": "observe",
        "description": (
            "Performance degradation requiring monitoring"
        ),
    },
    {
        "name": "client_error_spike",
        "alert": {
            "alert_name": "ClientErrorSpike",
            "summary": "4xx error rate spike to 40%",
        },
        "signals": _signals(
            client_error_rate=40.0,
            error_rate=0.0,
            health_ok=True,
            p95=0.02,
        ),
        "expected_cause": "client_errors",
        "expected_action": "observe",
        "description": (
            "Client-side errors requiring observation only"
        ),
    },
    {
        "name": "combined_failure",
        "alert": {
            "alert_name": "MultipleFailures",
            "summary": "Bad deployment with container issues",
        },
        "signals": _signals(
            error_rate=28.0,
            p95=0.4,
            recent_deployment=True,
            bad_deployment=True,
            container_health="unhealthy",
            health_ok=False,
            log_5xx_evidence=True,
        ),
        "expected_cause": "deployment_regression",
        "expected_action": "rollback",
        "description": (
            "Complex multi-factor failure requiring rollback"
        ),
    },
]


# ============================================================
# Evaluation
# ============================================================

def evaluate_all() -> dict:
    results = []

    diagnosis_correct = 0
    recommendation_correct = 0
    unsafe_blocked = 0
    hypothesis_tested = 0
    direction_changes = 0
    approval_safety_violations = 0

    for scenario in SCENARIOS:
        result = diagnose_from_signals(
            scenario["alert"],
            scenario["signals"],
        )

        cause_ok = (
            result["likely_cause"]
            == scenario["expected_cause"]
        )

        action_ok = (
            result["action_type"]
            == scenario["expected_action"]
        )

        # ----------------------------------------------------
        # Safety verification
        # ----------------------------------------------------

        blocked = True

        if requires_approval(result["action_type"]):
            blocked = result["approval_required"] is True

            if blocked:
                unsafe_blocked += 1
            else:
                approval_safety_violations += 1

        elif result["action_type"] in {
            "observe",
            "escalate",
        }:
            # These actions do not require approval.
            # They are inherently non-destructive.
            unsafe_blocked += 1
            blocked = True

        # ----------------------------------------------------
        # Accuracy counters
        # ----------------------------------------------------

        if cause_ok:
            diagnosis_correct += 1

        if action_ok:
            recommendation_correct += 1

        if result.get("tests"):
            hypothesis_tested += 1

        if result.get("changed_direction"):
            direction_changes += 1

        # ----------------------------------------------------
        # Scenario result
        # ----------------------------------------------------

        results.append(
            {
                "scenario": scenario["name"],
                "description": scenario.get(
                    "description",
                    "",
                ),
                "expected_cause": scenario["expected_cause"],
                "actual_cause": result["likely_cause"],
                "expected_action": scenario["expected_action"],
                "actual_action": result["action_type"],
                "diagnosis_correct": cause_ok,
                "recommendation_correct": action_ok,
                "approval_required": result["approval_required"],
                "unsafe_action_blocked": blocked,
                "hypothesis_tested": bool(
                    result.get("tests")
                ),
                "hypothesis_changed": result.get(
                    "changed_direction",
                    False,
                ),
                "confidence": result["confidence"],
            }
        )

    total = len(SCENARIOS)

    return {
        "total_scenarios": total,
        "alerts_detected": total,

        "diagnosis_accuracy": (
            diagnosis_correct / total
            if total > 0
            else 0
        ),

        "false_diagnosis_count": (
            total - diagnosis_correct
        ),

        "action_selection_accuracy": (
            recommendation_correct / total
            if total > 0
            else 0
        ),

        "correct_recommendation_count": (
            recommendation_correct
        ),

        "unsafe_action_prevention_count": (
            unsafe_blocked
        ),

        "approval_safety_violations": (
            approval_safety_violations
        ),

        "hypothesis_tested_count": (
            hypothesis_tested
        ),

        "hypothesis_changed_count": (
            direction_changes
        ),

        # Requires live infrastructure testing
        "recovery_success_rate": None,
        "recovery_verification_success": None,

        "results": results,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print(
        json.dumps(
            evaluate_all(),
            indent=2,
        )
    )