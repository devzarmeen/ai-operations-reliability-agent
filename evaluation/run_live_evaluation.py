import sys
import time
from concurrent.futures import ThreadPoolExecutor
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
# Constants
# ============================================================

PROMETHEUS_WAIT_SECONDS = 10

# Agent investigation can involve multiple diagnostic tools.
INVESTIGATION_TIMEOUT_SECONDS = 60

# Polling interval while the agent is investigating.
INVESTIGATION_POLL_SECONDS = 2

# Give Prometheus enough time to age old samples.
METRIC_AGING_SECONDS = 30


# ============================================================
# Generic result helpers
# ============================================================

def failed_result(name: str, reason: str) -> dict:
    """Create a consistent failed scenario result."""

    return {
        "name": name,
        "ok": False,
        "reason": reason,
        "diagnosis_correct": False,
        "recommendation_correct": False,
        "approval_policy_compliant": False,
        "recovery_success": False,
        "recovery_verified": False,
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

        print("  Chaos state reset successfully.")
        return True

    except requests.RequestException as exc:
        print(
            f"  [ERROR] Chaos reset request failed: {exc}"
        )
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

def send_single_event(index: int) -> bool:
    """Send one event request."""

    try:
        response = requests.post(
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
            timeout=3,
        )

        return response.status_code < 500

    except requests.RequestException:
        return False


def send_normal_traffic() -> None:
    """
    Generate normal evaluation traffic.

    We intentionally send both /events and /health requests
    so multiple metrics/log signals are produced.
    """

    successful = 0
    total = 30

    for index in range(total):

        if send_single_event(index):
            successful += 1

        try:
            requests.get(
                f"{SIMULATED_API_URL}/health",
                timeout=3,
            )
        except requests.RequestException:
            pass

    print(
        f"  Normal traffic generated: "
        f"{successful}/{total}"
    )


def send_traffic_spike() -> None:
    """
    Generate a real burst of concurrent traffic.

    This is intentionally much stronger than normal traffic
    so Prometheus can observe a measurable request-rate spike.
    """

    total_requests = 200
    workers = 25

    print(
        f"  Generating traffic spike: "
        f"{total_requests} requests "
        f"with {workers} workers..."
    )

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        results = list(
            executor.map(
                send_single_event,
                range(total_requests),
            )
        )

    successful = sum(
        1
        for result in results
        if result
    )

    print(
        f"  Traffic spike generated: "
        f"{successful}/{total_requests}"
    )


def send_traffic(scenario_name: str) -> None:
    """
    Generate scenario-appropriate traffic.
    """

    if scenario_name == "traffic_spike":
        send_traffic_spike()
    else:
        send_normal_traffic()


# ============================================================
# Investigation polling
# ============================================================

def fetch_investigation(
    investigation_id: int,
) -> dict | None:
    """
    Fetch one investigation payload from the backend.
    """

    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/investigations/"
            f"{investigation_id}",
            timeout=10,
        )

    except requests.RequestException as exc:
        print(
            f"  [WARN] Investigation fetch failed: {exc}"
        )
        return None

    if response.status_code != 200:
        print(
            f"  [WARN] Investigation fetch returned "
            f"{response.status_code}"
        )
        return None

    try:
        return response.json()

    except ValueError:
        print(
            "  [WARN] Investigation response "
            "was not valid JSON."
        )
        return None


def wait_for_investigation(
    investigation_id: int,
    timeout_seconds: int = INVESTIGATION_TIMEOUT_SECONDS,
) -> dict | None:
    """
    Wait until the investigation has reached a meaningful
    terminal/decision state.

    Backend states handled here:

        RECEIVED
            -> keep polling

        INVESTIGATING
            -> keep polling

        RECOMMENDED
            -> diagnosis/recommendation complete

        AWAITING_APPROVAL
            -> diagnosis complete and approval required

        RECOVERED
            -> recovery completed

        FAILED
            -> investigation/recovery failed

        REJECTED
            -> action rejected

        ESCALATED
            -> escalated for human handling
    """

    print(
        "  Waiting for investigation to complete..."
    )

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    last_status = None
    last_stage = None

    while time.monotonic() < deadline:

        payload = fetch_investigation(
            investigation_id
        )

        if payload is None:
            time.sleep(
                INVESTIGATION_POLL_SECONDS
            )
            continue

        investigation = payload.get(
            "investigation"
        )

        if not investigation:
            time.sleep(
                INVESTIGATION_POLL_SECONDS
            )
            continue

        status = investigation.get(
            "status"
        )

        stage = investigation.get(
            "stage"
        )

        cause = investigation.get(
            "likely_cause"
        )

        action = investigation.get(
            "recommended_action_type"
        )

        if (
            status != last_status
            or stage != last_stage
        ):

            print(
                f"    Investigation state: "
                f"status={status}, "
                f"stage={stage}"
            )

            last_status = status
            last_stage = stage

        # ----------------------------------------------------
        # High-impact action:
        # AWAITING_APPROVAL means diagnosis is complete.
        # ----------------------------------------------------

        if (
            status == "AWAITING_APPROVAL"
            or stage == "AWAITING_APPROVAL"
        ):
            print(
                f"    Investigation ready for approval: "
                f"cause={cause}, action={action}"
            )

            return payload

        # ----------------------------------------------------
        # Diagnosis/recommendation complete.
        #
        # IMPORTANT:
        # The backend can use:
        #
        #     status = RECOMMENDED
        #     stage  = DIAGNOSING
        #
        # This is NOT an active investigation anymore.
        # It is a valid decision state for evaluation.
        # ----------------------------------------------------

        if status == "RECOMMENDED":
            print(
                f"    Investigation produced diagnosis: "
                f"cause={cause}, action={action}"
            )

            return payload

        # ----------------------------------------------------
        # Non-recovery terminal states
        # ----------------------------------------------------

        terminal_statuses = {
            "RECOVERED",
            "FAILED",
            "REJECTED",
            "ESCALATED",
        }

        if status in terminal_statuses:
            print(
                f"    Investigation reached terminal "
                f"state: {status}"
            )

            return payload

        # ----------------------------------------------------
        # Generic fallback:
        #
        # If a backend implementation has produced a real
        # cause + action and moved beyond the initial states,
        # allow the evaluator to continue.
        # ----------------------------------------------------

        if (
            cause is not None
            and action is not None
            and status not in {
                "RECEIVED",
                "INVESTIGATING",
            }
            and stage not in {
                "RECEIVED",
                "INVESTIGATING",
            }
        ):
            print(
                f"    Investigation produced diagnosis: "
                f"cause={cause}, action={action}"
            )

            return payload

        time.sleep(
            INVESTIGATION_POLL_SECONDS
        )

    print(
        f"  [ERROR] Investigation {investigation_id} "
        f"did not complete within "
        f"{timeout_seconds}s."
    )

    return None


# ============================================================
# Live scenario execution
# ============================================================

def run_live_scenario(scenario: dict) -> dict:

    name = scenario["name"]

    alert = scenario["alert"]
    expected_cause = scenario["expected_cause"]
    expected_action = scenario["expected_action"]

    print()
    print("=" * 60)
    print(
        f"--- Running Live Scenario: {name} ---"
    )
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Reset simulated API
    # --------------------------------------------------------

    print()
    print("  [1/10] Resetting simulated API...")

    if not reset_simulated_api():
        return failed_result(
            name,
            "chaos_reset_failed",
        )

    # --------------------------------------------------------
    # 2. Give previous Prometheus data time to age
    # --------------------------------------------------------

    print()
    print(
        "  [2/10] Waiting "
        f"{METRIC_AGING_SECONDS}s "
        "for old metrics to age out..."
    )

    time.sleep(
        METRIC_AGING_SECONDS
    )

    # --------------------------------------------------------
    # 3. Inject scenario
    # --------------------------------------------------------

    print()
    print("  [3/10] Injecting scenario...")

    if not inject_chaos(name):
        return failed_result(
            name,
            "chaos_injection_failed",
        )

    # --------------------------------------------------------
    # 4. Generate traffic
    # --------------------------------------------------------

    print()
    print("  [4/10] Generating traffic...")

    send_traffic(name)

    # --------------------------------------------------------
    # 5. Wait for Prometheus
    # --------------------------------------------------------

    print()
    print(
        "  [5/10] Waiting "
        f"{PROMETHEUS_WAIT_SECONDS}s "
        "for Prometheus scrape..."
    )

    time.sleep(
        PROMETHEUS_WAIT_SECONDS
    )

    # --------------------------------------------------------
    # 6. Send alert to backend webhook
    # --------------------------------------------------------

    print()
    print(
        "  [6/10] Sending alert to backend..."
    )

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
            f"  [ERROR] Alert webhook request failed: "
            f"{exc}"
        )

        return failed_result(
            name,
            "webhook_request_failed",
        )

    if response.status_code != 200:

        print(
            f"  [ERROR] Alert webhook failed: "
            f"{response.status_code}"
        )

        print(
            f"  Response: {response.text}"
        )

        return failed_result(
            name,
            "webhook_failed",
        )

    try:
        webhook_res = response.json()

    except ValueError:

        print(
            "  [ERROR] Webhook response "
            "was not valid JSON."
        )

        return failed_result(
            name,
            "invalid_webhook_response",
        )

    ingested = webhook_res.get(
        "ingested",
        [],
    )

    if not ingested:

        print(
            "  [ERROR] Alert was not ingested."
        )

        print(
            f"  Response: {webhook_res}"
        )

        return failed_result(
            name,
            "alert_skipped",
        )

    investigation_id = ingested[0].get(
        "investigation_id"
    )

    if not investigation_id:

        print(
            "  [ERROR] Webhook did not return "
            "an investigation ID."
        )

        return failed_result(
            name,
            "no_investigation_id",
        )

    print(
        f"  Investigation ID: "
        f"{investigation_id}"
    )

    # --------------------------------------------------------
    # 7. WAIT for investigation
    # --------------------------------------------------------

    print()
    print(
        "  [7/10] Waiting for investigation..."
    )

    payload = wait_for_investigation(
        investigation_id
    )

    if payload is None:

        return failed_result(
            name,
            "investigation_timeout",
        )

    investigation = payload.get(
        "investigation"
    )

    if not investigation:

        print(
            "  [ERROR] Investigation payload "
            "is missing."
        )

        return failed_result(
            name,
            "invalid_investigation_payload",
        )

    # --------------------------------------------------------
    # 8. Validate investigation
    # --------------------------------------------------------

    print()
    print(
        "  [8/10] Validating investigation..."
    )

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

    status = investigation.get(
        "status"
    )

    stage = investigation.get(
        "stage"
    )

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
        approval_required
        == expected_approval
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
        f"  Approval Required: "
        f"{approval_required} "
        f"(Expected: {expected_approval}) -> "
        f"{'OK' if approval_correct else 'FAIL'}"
    )

    print(
        f"  Investigation Status: {status}"
    )

    print(
        f"  Investigation Stage: {stage}"
    )

    # --------------------------------------------------------
    # 9. Recovery policy
    # --------------------------------------------------------

    print()
    print(
        "  [9/10] Processing recovery policy..."
    )

    recovery_ok = None
    recovery_verified = None

    # --------------------------------------------------------
    # High-impact action
    # --------------------------------------------------------

    if approval_required:

        # ----------------------------------------------------
        # Safety requirement:
        # high-impact action MUST remain pending until
        # explicit approval.
        # ----------------------------------------------------

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
            f"  Approval Required for "
            f"{actual_action}: YES"
        )

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
                timeout=30,
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

            print(
                f"  Response: {response.text}"
            )

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

        try:
            approve_res = response.json()

        except ValueError:

            print(
                "  [ERROR] Approval response "
                "was not valid JSON."
            )

            return {
                "name": name,
                "ok": False,
                "reason": "invalid_approval_response",
                "diagnosis_correct": cause_correct,
                "recommendation_correct": action_correct,
                "approval_policy_compliant": approval_correct,
                "recovery_success": False,
                "recovery_verified": False,
                "actual_cause": actual_cause,
                "actual_action": actual_action,
            }

        updated_inv = (
            approve_res.get(
                "investigation"
            )
            or {}
        )

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
            f"  Recovery Success: "
            f"{recovery_ok} -> "
            f"{'OK' if recovery_ok else 'FAIL'}"
        )

        print(
            f"  Recovery Verified: "
            f"{recovery_verified} -> "
            f"{'OK' if recovery_verified else 'FAIL'}"
        )

    # --------------------------------------------------------
    # Non-recovery actions
    # --------------------------------------------------------

    elif actual_action in {
        "observe",
        "escalate",
    }:

        print(
            f"  Action {actual_action} "
            "does not perform automatic recovery."
        )

        recovery_ok = True
        recovery_verified = True

        print(
            "  Recovery: N/A / not required -> OK"
        )

    else:

        print(
            f"  [ERROR] Unexpected action type: "
            f"{actual_action}"
        )

        recovery_ok = False
        recovery_verified = False

    # --------------------------------------------------------
    # 10. Final scenario result
    # --------------------------------------------------------

    print()
    print(
        "  [10/10] Calculating scenario result..."
    )

    ok = (
        cause_correct
        and action_correct
        and approval_correct
        and recovery_ok is not False
        and recovery_verified is not False
    )

    result = {
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

    print(
        f"  [{'PASS' if ok else 'FAIL'}] "
        f"Scenario {name}"
    )

    return result


# ============================================================
# Main evaluation
# ============================================================

def main() -> int:

    print()
    print("=" * 60)
    print(
        "Starting Live Integration Evaluation..."
    )
    print("=" * 60)

    print(
        f"Target simulated-api: "
        f"{SIMULATED_API_URL}"
    )

    print(
        f"Target backend-api: "
        f"{BACKEND_API_URL}"
    )

    print(
        f"Evaluation scenarios: "
        f"{len(SCENARIOS)}"
    )

    print(
        f"Investigation timeout: "
        f"{INVESTIGATION_TIMEOUT_SECONDS}s"
    )

    results = []

    # --------------------------------------------------------
    # Validate scenario mappings
    # --------------------------------------------------------

    missing_mappings = [
        scenario["name"]
        for scenario in SCENARIOS
        if scenario["name"]
        not in SCENARIO_MAP
    ]

    if missing_mappings:

        print()
        print(
            "[ERROR] Missing scenario mappings:"
        )

        for name in missing_mappings:
            print(
                f"  - {name}"
            )

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

        except KeyboardInterrupt:

            print()
            print(
                "[ERROR] Evaluation interrupted "
                "by user."
            )

            reset_simulated_api()
            return 1

        except Exception as exc:

            print()
            print(
                f"  [CRITICAL ERROR] Scenario "
                f"{scenario['name']} crashed:"
            )

            print(
                f"  {type(exc).__name__}: {exc}"
            )

            results.append(
                failed_result(
                    scenario["name"],
                    f"exception: {exc}",
                )
            )

    # --------------------------------------------------------
    # Final reset
    # --------------------------------------------------------

    print()
    print(
        "Resetting simulated API..."
    )

    reset_simulated_api()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "LIVE EVALUATION SUMMARY"
    )
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
        if result.get(
            "diagnosis_correct"
        )
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

    recovery_verification_attempts = sum(
        1
        for result in results
        if result.get(
            "recovery_verified"
        )
        is not None
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

    if recovery_attempts:

        print(
            f"Recovery Success Rate: "
            f"{recovery_successes} / "
            f"{recovery_attempts} "
            f"({recovery_successes / recovery_attempts * 100:.1f}%)"
        )

    else:

        print(
            "Recovery Success Rate: N/A"
        )

    if recovery_verification_attempts:

        print(
            f"Recovery Verification Success: "
            f"{recovery_verifications} / "
            f"{recovery_verification_attempts} "
            f"({recovery_verifications / recovery_verification_attempts * 100:.1f}%)"
        )

    else:

        print(
            "Recovery Verification Success: N/A"
        )

    # --------------------------------------------------------
    # Detailed report
    # --------------------------------------------------------

    print()
    print(
        "Detailed Scenario Report:"
    )

    for result in results:

        status = (
            "PASS"
            if result.get("ok")
            else "FAIL"
        )

        if "actual_cause" in result:

            details = (
                f"cause={result.get('actual_cause')}, "
                f"action={result.get('actual_action')}, "
                f"recovery={result.get('recovery_success')}, "
                f"verified={result.get('recovery_verified')}"
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

    # --------------------------------------------------------
    # Failed scenarios
    # --------------------------------------------------------

    failed = [
        result
        for result in results
        if not result.get("ok")
    ]

    if failed:

        print()
        print(
            "Failed Scenarios:"
        )

        for result in failed:

            print(
                f"  - {result['name']}: "
                f"{result.get('reason', 'validation_failed')}"
            )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 60)

    if (
        total > 0
        and passed == total
    ):

        print(
            "FINAL RESULT: PASS"
        )

        print(
            f"{passed}/{total} scenarios passed."
        )

    else:

        print(
            "FINAL RESULT: FAIL"
        )

        print(
            f"{passed}/{total} scenarios passed."
        )

    print("=" * 60)

    return (
        0
        if total > 0
        and passed == total
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())