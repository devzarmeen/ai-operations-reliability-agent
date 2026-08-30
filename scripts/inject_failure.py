"""Reproducible failure injection for the simulated API."""

from __future__ import annotations

import argparse
import json
import sys

import requests


BASE_URL = "http://localhost:8001"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject a controlled simulated-api failure scenario")
    parser.add_argument("name", help="Scenario name or 'reset'")
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    if args.name == "reset":
        response = requests.post(f"{args.base_url}/chaos/reset", timeout=10)
    else:
        response = requests.post(
            f"{args.base_url}/chaos/scenario",
            json={"name": args.name},
            timeout=10,
        )

    print(json.dumps(response.json(), indent=2))
    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
