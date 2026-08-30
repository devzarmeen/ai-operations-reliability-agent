"""Run the offline reliability-agent evaluation."""

from __future__ import annotations

import json

from evaluation_scenarios import evaluate_all


def main() -> int:
    summary = evaluate_all()

    print("\n=== Operations Reliability Agent Evaluation ===\n")

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

    print("\n=== Per Scenario ===\n")

    for row in summary["results"]:
        passed = (
            row["diagnosis_correct"]
            and row["recommendation_correct"]
        )

        mark = "PASS" if passed else "FAIL"

        print(
            f"[{mark}] {row['scenario']}"
        )

        print(
            f"  Expected : "
            f"{row['expected_cause']} "
            f"-> "
            f"{row['expected_action']}"
        )

        print(
            f"  Actual   : "
            f"{row['actual_cause']} "
            f"-> "
            f"{row['actual_action']}"
        )

        print(
            f"  Diagnosis: "
            f"{'PASS' if row['diagnosis_correct'] else 'FAIL'}"
        )

        print(
            f"  Action   : "
            f"{'PASS' if row['recommendation_correct'] else 'FAIL'}"
        )

        print(
            f"  Approval : "
            f"{row['approval_required']}"
        )

        print(
            f"  Blocked  : "
            f"{row['unsafe_action_blocked']}"
        )

        print(
            f"  Confidence: "
            f"{row['confidence']:.2f}"
        )

        print()

    failed = [
        row["scenario"]
        for row in summary["results"]
        if not (
            row["diagnosis_correct"]
            and row["recommendation_correct"]
        )
    ]

    print("=== Final Summary ===\n")

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
        f"Hypotheses tested: "
        f"{summary['hypothesis_tested_count']}"
    )

    print(
        f"Direction changes: "
        f"{summary['hypothesis_changed_count']}"
    )

    if failed:
        print(
            "\nFAILED SCENARIOS:"
        )

        for name in failed:
            print(
                f"  - {name}"
            )

        return 1

    if (
        summary[
            "approval_safety_violations"
        ]
        > 0
    ):
        print(
            "\nFAIL: Approval safety violations detected."
        )
        return 1

    print(
        "\nALL EVALUATION SCENARIOS PASSED."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())