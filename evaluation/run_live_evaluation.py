import sys
import time
from pathlib import Path

import requests


# ============================================================
# Project paths
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))


from scenarios import SCENARIOS
from app.safety.enforcement import requires_approval


# ============================================================
# Service URLs
# ============================================================

SIMULATED_API_URL = "http://127.0.0.1:8001"
BACKEND_API_URL = "http://127.0.0.1:9000"


# ============================================================
# Evaluation scenario -> simulated-api scenario mapping
# ============================================================
#
# The evaluation scenario names describe the test.
# The simulated API has its own chaos scenario names.
#
# Keep these two namespaces separate.
# ============================================================

SCENARIO_MAP = {
    "normal_operation": "normal",
    "high_error_rate": "high_error_rate",
    "service_unavailable": "service_unavailable",
    "bad_deployment": "recent_bad_deployment",
    "container_restart_loop": "container_restart_loop",
    "database_unavailable": "database_unavailable",
    "traffic_spike": "traffic_spike",
    "latency_degradation": "high_latency",
    "client_error_spike": "http_400_spike",
    "combined_failure": "combined_failure",
}


# ============================================================
# HTTP helpers
# ============================================================

def reset_simulated_api() -> bool:
    """Reset simulated API to a clean normal state."""

    try:
        response = requests.post(
            f"{SIMULATED_API_URL}/chaos/reset",
            timeout=5,
        )

        if response.status_code != 200:
            print(
                f"  [ERROR] Chaos reset failed: "
                f"{response.status_code} {response.text}"
            )
            return False

        return True

    except requests.RequestException as exc:
        print(f"  [ERROR] Chaos reset request failed: {exc}")
        return False


def inject_chaos(evaluation_name: str) -> bool:
    """
    Translate evaluation scenario name into the actual
    simulated-api chaos scenario and inject it.
    """

    sim_scenario = SCENARIO_MAP.get(evaluation_name)

    if sim_scenario is None:
        print(
            f"  [ERROR] No chaos mapping found for "
            f"evaluation scenario: {evaluation_name}"
        )
        return False

    try:
        response = requests.post(
            f"{SIMULATED_API_URL}/chaos/scenario",
            json={"name": sim_scenario},
            timeout=5,
        )

        if response.status_code != 200:
            print(
                f"  [ERROR] Failed to inject chaos for "
                f"{evaluation_name}"
            )
            print(f"  Response: {response.text}")
            return False

        print(
            f"  Chaos injected: "
            f"{evaluation_name} -> {sim_scenario}"
        )

        return True

    except requests.RequestException as exc:
        print(
            f"  [ERROR] Chaos injection request failed: {exc}"
        )
        return False


# ============================================================
# Traffic generation
# ============================================================

def send_traffic() -> None:
    """
    Generate metric data points by calling simulated-api.
    """

    for index in range(30):
        try:
            requests.post(
                f"{SIMULATED_API_URL}/events",
                json={
                    "event_id": (
                        f"eval-{time.time_ns()}-{index}"
                    ),
                    "timestamp": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ",
                        time.gmtime(),
                    ),
                    "service": "simulated-api-service",
                    "operation": "create_event",
                    "status": "success",
                    "latency_ms": 15.0,
                },
                timeout=1,
            )

            requests.get(
                f"{SIMULATED_API_URL}/health",
                timeout=1,
            )

        except requests.RequestException:
            # Traffic generation is best-effort.
            pass


# ============================================================
# Live scenario execution
# ============================================================

def run_live_scenario(scenario: dict) -> dict:
    name = scenario["name"]

    alert = scenario["alert"]
    expected_cause = scenario["expected_cause"]
    expected_action = scenario["expected_action"]

    print()
    print(f"--- Running Live Scenario: {name} ---")

    # --------------------------------------------------------
    # 1. Reset simulated API
    # --------------------------------------------------------

    if not reset_simulated_api():
        return {
            "name": name,
            "ok": False,
            "reason": "chaos_reset_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    # --------------------------------------------------------
    # 2. Give previous Prometheus data time to age
    # --------------------------------------------------------

    print("  Waiting 30s for old metrics to age out...")
    time.sleep(30)

    # --------------------------------------------------------
    # 3. Inject scenario
    # --------------------------------------------------------

    if not inject_chaos(name):
        return {
            "name": name,
            "ok": False,
            "reason": "chaos_injection_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    # --------------------------------------------------------
    # 4. Generate traffic
    # --------------------------------------------------------

    send_traffic()

    print("  Waiting 6s for Prometheus scrape...")
    time.sleep(6)

    # --------------------------------------------------------
    # 5. Send alert to backend webhook
    # --------------------------------------------------------

    webhook_payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert["alert_name"],
                    "service": "simulated-api-service",
                    "severity": alert.get(
                        "severity",
                        "HIGH",
                    ),
                },
                "annotations": {
                    "summary": (
                        alert.get("summary")
                        or alert.get("description")
                        or ""
                    ),
                },
                "fingerprint": (
                    f"eval-{name}-"
                    f"{int(time.time() * 1000)}"
                ),
            }
        ],
    }

    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/alerts/webhook",
            json=webhook_payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(
            f"  [ERROR] Alert webhook request failed: {exc}"
        )

        return {
            "name": name,
            "ok": False,
            "reason": "webhook_request_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    if response.status_code != 200:
        print(
            f"  [ERROR] Alert webhook failed: "
            f"{response.status_code}"
        )
        print(f"  Response: {response.text}")

        return {
            "name": name,
            "ok": False,
            "reason": "webhook_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    webhook_res = response.json()

    ingested = webhook_res.get("ingested", [])

    if not ingested:
        print(
            "  [ERROR] Alert was not ingested."
        )
        print(f"  Response: {webhook_res}")

        return {
            "name": name,
            "ok": False,
            "reason": "alert_skipped",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    investigation_id = ingested[0].get(
        "investigation_id"
    )

    if not investigation_id:
        print(
            "  [ERROR] Webhook did not return "
            "an investigation ID."
        )

        return {
            "name": name,
            "ok": False,
            "reason": "no_investigation_id",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    print(
        f"  Investigation ID: {investigation_id}"
    )

    # --------------------------------------------------------
    # 6. Fetch investigation
    # --------------------------------------------------------

    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/investigations/"
            f"{investigation_id}",
            timeout=10,
        )
    except requests.RequestException as exc:
        print(
            f"  [ERROR] Fetching investigation failed: "
            f"{exc}"
        )

        return {
            "name": name,
            "ok": False,
            "reason": "fetch_investigation_request_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    if response.status_code != 200:
        print(
            f"  [ERROR] Fetching investigation "
            f"{investigation_id} failed: "
            f"{response.text}"
        )

        return {
            "name": name,
            "ok": False,
            "reason": "fetch_investigation_failed",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    payload = response.json()

    investigation = payload.get(
        "investigation"
    )

    if not investigation:
        print(
            "  [ERROR] Investigation payload is missing."
        )

        return {
            "name": name,
            "ok": False,
            "reason": "invalid_investigation_payload",
            "diagnosis_correct": False,
            "recommendation_correct": False,
            "approval_policy_compliant": False,
            "recovery_success": False,
            "recovery_verified": False,
        }

    actual_cause = investigation.get(
        "likely_cause"
    )

    actual_action = investigation.get(
        "recommended_action_type"
    )

    approval_required = investigation.get(
        "approval_required"
    )

    approval_status = investigation.get(
        "approval_status"
    )

    # --------------------------------------------------------
    # 7. Validate diagnosis
    # --------------------------------------------------------

    cause_correct = (
        actual_cause == expected_cause
    )

    action_correct = (
        actual_action == expected_action
    )

    expected_approval = requires_approval(
        actual_action
    )

    approval_correct = (
        approval_required == expected_approval
    )

    print(
        f"  Diagnosis: {actual_cause} "
        f"(Expected: {expected_cause}) -> "
        f"{'OK' if cause_correct else 'FAIL'}"
    )

    print(
        f"  Action: {actual_action} "
        f"(Expected: {expected_action}) -> "
        f"{'OK' if action_correct else 'FAIL'}"
    )

    print(
        f"  Approval Required: {approval_required} "
        f"(Expected: {expected_approval}) -> "
        f"{'OK' if approval_correct else 'FAIL'}"
    )

    # --------------------------------------------------------
    # 8. Recovery values
    # --------------------------------------------------------

    recovery_ok = None
    recovery_verified = None

    # --------------------------------------------------------
    # 9. High-impact action
    # --------------------------------------------------------

    if approval_required:

        if approval_status != "pending":
            print(
                f"  [ERROR] Expected pending approval, "
                f"got {approval_status}"
            )

            return {
                "name": name,
                "ok": False,
                "reason": "not_pending_approval",
                "diagnosis_correct": cause_correct,
                "recommendation_correct": action_correct,
                "approval_policy_compliant": False,
                "recovery_success": False,
                "recovery_verified": False,
                "actual_cause": actual_cause,
                "actual_action": actual_action,
            }

        print(
            f"  Approving action {actual_action}..."
        )

        approve_body = {
            "operator": "live-eval-bot",
            "note": (
                "Automatic approval for live "
                f"evaluation of {name}"
            ),
        }

        try:
            response = requests.post(
                f"{BACKEND_API_URL}/api/investigations/"
                f"{investigation_id}/approve",
                json=approve_body,
                timeout=20,
            )
        except requests.RequestException as exc:
            print(
                f"  [ERROR] Action approval request "
                f"failed: {exc}"
            )

            return {
                "name": name,
                "ok": False,
                "reason": "approval_request_failed",
                "diagnosis_correct": cause_correct,
                "recommendation_correct": action_correct,
                "approval_policy_compliant": approval_correct,
                "recovery_success": False,
                "recovery_verified": False,
                "actual_cause": actual_cause,
                "actual_action": actual_action,
            }

        if response.status_code != 200:
            print(
                f"  [ERROR] Action approval failed: "
                f"{response.status_code}"
            )
            print(f"  Response: {response.text}")

            return {
                "name": name,
                "ok": False,
                "reason": "approval_post_failed",
                "diagnosis_correct": cause_correct,
                "recommendation_correct": action_correct,
                "approval_policy_compliant": approval_correct,
                "recovery_success": False,
                "recovery_verified": False,
                "actual_cause": actual_cause,
                "actual_action": actual_action,
            }

        approve_res = response.json()

        updated_inv = approve_res.get(
            "investigation"
        ) or {}

        recovery_ok = (
            updated_inv.get("status")
            == "RECOVERED"
        )

        recoveries = approve_res.get(
            "recoveries",
            [],
        )

        recovery_verified = (
            len(recoveries) > 0
            and recoveries[0].get(
                "recovered"
            )
            is True
        )

        print(
            f"  Recovery Success: {recovery_ok} -> "
            f"{'OK' if recovery_ok else 'FAIL'}"
        )

        print(
            f"  Recovery Verified: "
            f"{recovery_verified} -> "
            f"{'OK' if recovery_verified else 'FAIL'}"
        )

    # --------------------------------------------------------
    # 10. Non-recovery actions
    # --------------------------------------------------------

    elif actual_action in {
        "observe",
        "escalate",
    }:
        recovery_ok = True
        recovery_verified = True

    # --------------------------------------------------------
    # 11. Final scenario result
    # --------------------------------------------------------

    ok = (
        cause_correct
        and action_correct
        and approval_correct
        and recovery_ok is not False
    )

    return {
        "name": name,
        "ok": ok,
        "diagnosis_correct": cause_correct,
        "recommendation_correct": action_correct,
        "approval_policy_compliant": approval_correct,
        "recovery_success": recovery_ok,
        "recovery_verified": recovery_verified,
        "actual_cause": actual_cause,
        "actual_action": actual_action,
    }


# ============================================================
# Main evaluation
# ============================================================

def main() -> int:

    print(
        "Starting Live Integration Evaluation..."
    )

    print(
        f"Target simulated-api: "
        f"{SIMULATED_API_URL}"
    )

    print(
        f"Target backend-api: "
        f"{BACKEND_API_URL}"
    )

    print(
        f"Evaluation scenarios: {len(SCENARIOS)}"
    )

    results = []

    # --------------------------------------------------------
    # Validate scenario mappings before running
    # --------------------------------------------------------

    missing_mappings = [
        scenario["name"]
        for scenario in SCENARIOS
        if scenario["name"] not in SCENARIO_MAP
    ]

    if missing_mappings:
        print()
        print(
            "[ERROR] Missing scenario mappings:"
        )

        for name in missing_mappings:
            print(f"  - {name}")

        return 1

    # --------------------------------------------------------
    # Run scenarios
    # --------------------------------------------------------

    for scenario in SCENARIOS:

        try:
            result = run_live_scenario(
                scenario
            )

            results.append(result)

        except Exception as exc:

            print(
                f"  [CRITICAL ERROR] Scenario "
                f"{scenario['name']} crashed: {exc}"
            )

            results.append(
                {
                    "name": scenario["name"],
                    "ok": False,
                    "reason": (
                        f"exception: {exc}"
                    ),
                    "diagnosis_correct": False,
                    "recommendation_correct": False,
                    "approval_policy_compliant": False,
                    "recovery_success": False,
                    "recovery_verified": False,
                }
            )

    # --------------------------------------------------------
    # Final reset
    # --------------------------------------------------------

    print()
    print("Resetting simulated API...")

    reset_simulated_api()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("LIVE EVALUATION SUMMARY")
    print("=" * 60)

    total = len(results)

    passed = sum(
        1
        for result in results
        if result.get("ok")
    )

    diagnosis_correct = sum(
        1
        for result in results
        if result.get("diagnosis_correct")
    )

    recommendation_correct = sum(
        1
        for result in results
        if result.get(
            "recommendation_correct"
        )
    )

    policy_compliant = sum(
        1
        for result in results
        if result.get(
            "approval_policy_compliant"
        )
    )

    recovery_attempts = sum(
        1
        for result in results
        if result.get(
            "recovery_success"
        )
        is not None
    )

    recovery_successes = sum(
        1
        for result in results
        if result.get(
            "recovery_success"
        )
        is True
    )

    recovery_verifications = sum(
        1
        for result in results
        if result.get(
            "recovery_verified"
        )
        is True
    )

    print(
        f"Total Scenarios: {total}"
    )

    if total:
        print(
            f"Passed Scenarios: "
            f"{passed} / {total} "
            f"({passed / total * 100:.1f}%)"
        )

        print(
            f"Diagnosis Accuracy: "
            f"{diagnosis_correct} / {total} "
            f"({diagnosis_correct / total * 100:.1f}%)"
        )

        print(
            f"Recommendation Accuracy: "
            f"{recommendation_correct} / {total} "
            f"({recommendation_correct / total * 100:.1f}%)"
        )

        print(
            f"Approval Policy Compliance: "
            f"{policy_compliant} / {total} "
            f"({policy_compliant / total * 100:.1f}%)"
        )

    if recovery_attempts > 0:

        print(
            f"Recovery Success Rate: "
            f"{recovery_successes} / "
            f"{recovery_attempts} "
            f"({recovery_successes / recovery_attempts * 100:.1f}%)"
        )

        print(
            f"Recovery Verification Success: "
            f"{recovery_verifications} / "
            f"{recovery_attempts} "
            f"({recovery_verifications / recovery_attempts * 100:.1f}%)"
        )

    else:
        print(
            "Recovery Success Rate: N/A"
        )

        print(
            "Recovery Verification Success: N/A"
        )

    # --------------------------------------------------------
    # Detailed report
    # --------------------------------------------------------

    print()
    print("Detailed Scenario Report:")

    for result in results:

        status = (
            "PASS"
            if result.get("ok")
            else "FAIL"
        )

        if "actual_cause" in result:

            details = (
                f"cause={result.get('actual_cause')}, "
                f"action={result.get('actual_action')}"
            )

        else:

            details = result.get(
                "reason",
                "unknown",
            )

        print(
            f"  [{status}] "
            f"{result['name']}: "
            f"{details}"
        )

    print()
    print("=" * 60)

    return (
        0
        if total > 0 and passed == total
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())