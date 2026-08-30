"""Query Prometheus over its HTTP API."""

from __future__ import annotations

import math
from typing import Any

import httpx

from app.core.config import settings


class PrometheusQueryError(Exception):
    """Raised when Prometheus cannot be queried safely."""


def _scalar(
    result: list[dict[str, Any]],
) -> float | None:
    """
    Extract the first numeric value from a Prometheus vector result.

    Prometheus instant-vector values normally look like:
        ["timestamp", "value"]
    """

    if not result:
        return None

    try:
        raw_value = result[0]["value"][1]
        value = float(raw_value)
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        return None

    if math.isnan(value) or math.isinf(value):
        return None

    return value


class PrometheusService:
    """Small async client for the Prometheus HTTP API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.base_url = (
            base_url or settings.prometheus_url
        ).rstrip("/")

        self.timeout = timeout

    async def query(
        self,
        promql: str,
    ) -> dict[str, Any]:
        """Execute an instant PromQL query."""

        url = f"{self.base_url}/api/v1/query"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:
                response = await client.get(
                    url,
                    params={"query": promql},
                )

        except httpx.TimeoutException as exc:
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": f"timeout: {exc}",
            }

        except httpx.RequestError as exc:
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": (
                    f"request_failed: {exc}"
                    f" | url={url}"
                ),
            }

        except Exception as exc:
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": str(exc),
            }

        if response.status_code != 200:
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": (
                    f"http_{response.status_code}"
                ),
            }

        try:
            payload = response.json()

        except ValueError:
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": "invalid_json",
            }

        if payload.get("status") != "success":
            return {
                "ok": False,
                "query": promql,
                "result_type": None,
                "result": [],
                "value": None,
                "error": str(
                    payload.get("error")
                    or "prometheus_error"
                ),
            }

        data = payload.get("data") or {}

        result = data.get("result") or []

        return {
            "ok": True,
            "query": promql,
            "result_type": data.get("resultType"),
            "result": result,
            "value": _scalar(result),
            "error": None,
        }

    async def scalar(
        self,
        promql: str,
    ) -> dict[str, Any]:
        """
        Execute a PromQL query and return its first numeric value.
        """

        response = await self.query(promql)

        return {
            "ok": response["ok"],
            "query": promql,
            "value": response["value"],
            "error": response["error"],
        }


prometheus_service = PrometheusService()