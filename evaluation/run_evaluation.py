"""Run the offline evaluation suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The API package is installed/available under /app.
# The evaluation files live under /evaluation.
APP_ROOT = Path("/app")
EVALUATION_ROOT = Path("/evaluation")

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))

from scenarios import evaluate_all


def main() -> int:
    summary = evaluate_all()

    print(
        json.dumps(
            {
                key: value
                for key, value in summary.items()
                if key != "results"
            },
            indent=2,
        )
    )

    print("\nPer-scenario details:\n")

    for row in summary["results"]:
        diagnosis_ok = bool(
            row.get("diagnosis_correct", False)
        )

        action_ok = bool(
            row.get("recommendation_correct", False)
        )

        passed = diagnosis_ok and action_ok

        mark = "PASS" if passed else "FAIL"

        print(
            f"[{mark}] "
            f"{row.get('scenario', 'unknown')}"
        )

        print(
            f"    Expected: "
            f"{row.get('expected_cause')} -> "
            f"{row.get('expected_action')}"
        )

        print(
            f"    Actual:   "
            f"{row.get('actual_cause')} -> "
            f"{row.get('actual_action')}"
        )

        print(
            f"    Diagnosis: "
            f"{'PASS' if diagnosis_ok else 'FAIL'}"
        )

        print(
            f"    Action:    "
            f"{'PASS' if action_ok else 'FAIL'}"
        )

        print(
            f"    Approval:  "
            f"{row.get('approval_required')}"
        )

        print(
            f"    Blocked:   "
            f"{row.get('unsafe_action_blocked')}"
        )

        if row.get("changed_direction") is not None:
            print(
                f"    Direction changed: "
                f"{row.get('changed_direction')}"
            )

        print()

    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)

    print(
        f"Total scenarios: "
        f"{summary['total_scenarios']}"
    )

    print(
        f"Diagnosis accuracy: "
        f"{summary['diagnosis_accuracy']:.2%}"
    )

    print(
        f"Action selection accuracy: "
        f"{summary['action_selection_accuracy']:.2%}"
    )

    print(
        f"Unsafe actions blocked: "
        f"{summary['unsafe_action_prevention_count']}/"
        f"{summary['total_scenarios']}"
    )

    print(
        f"Approval safety violations: "
        f"{summary['approval_safety_violations']}"
    )

    print(
        f"Hypothesis tests executed: "
        f"{summary['hypothesis_tested_count']}"
    )

    print(
        f"Hypothesis direction changes: "
        f"{summary['hypothesis_changed_count']}"
    )

    failed = [
        row.get("scenario", "unknown")
        for row in summary["results"]
        if not (
            row.get("diagnosis_correct", False)
            and row.get(
                "recommendation_correct",
                False,
            )
        )
    ]

    print()

    if failed:
        print(
            "FAILED SCENARIOS: "
            + ", ".join(failed)
        )
        return 1

    if summary["approval_safety_violations"] > 0:
        print(
            "ERROR: Approval safety violations detected."
        )
        return 1

    print("ALL EVALUATION SCENARIOS PASSED.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())