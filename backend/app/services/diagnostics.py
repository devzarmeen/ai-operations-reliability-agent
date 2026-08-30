"""Read-only diagnostic collection for the simulated service."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.diagnostics.status import get_service_status
from app.metrics import (
    record_tool_call,
    record_tool_failure,
)
from app.services.database_test import (
    test_database_connection,
)


def _sanitize(payload: Any) -> Any:
    """Recursively remove sensitive values."""

    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}

        for key, value in payload.items():
            lowered = key.lower()

            if any(
                token in lowered
                for token in (
                    "password",
                    "token",
                    "webhook",
                    "api_key",
                    "authorization",
                    "secret",
                )
            ):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = _sanitize(value)

        return redacted

    if isinstance(payload, list):
        return [
            _sanitize(item)
            for item in payload
        ]

    return payload


def _success(
    tool: str,
    result: Any,
) -> dict[str, Any]:
    return {
        "ok": True,
        "tool": tool,
        "result": _sanitize(result),
        "error": None,
    }


def _failure(
    tool: str,
    error: str,
    result: Any = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "result": _sanitize(result),
        "error": error,
    }


async def _simulated_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:

    url = (
        f"{settings.simulated_api_url.rstrip('/')}"
        f"{path}"
    )

    try:
        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:
            response = await client.get(
                url,
                params=params,
            )

        try:
            body = response.json()
        except ValueError:
            body = {
                "raw": response.text[:500]
            }

        if response.status_code >= 400:
            return {
                "available": False,
                "status_code": response.status_code,
                "error": (
                    f"http_{response.status_code}"
                ),
                "data": body,
            }

        return {
            "available": True,
            "status_code": response.status_code,
            "error": None,
            "data": body,
        }

    except httpx.RequestError as exc:
        return {
            "available": False,
            "status_code": None,
            "error": str(exc),
            "data": None,
        }


async def collect_prometheus_snapshot():
    tool_name = "prometheus_metrics"

    record_tool_call(tool_name)

    try:
        status = await get_service_status()

        return _success(
            tool_name,
            status,
        )

    except Exception as exc:
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            str(exc),
        )


async def collect_logs(
    service: str | None = None,
    severity: str | None = None,
    correlation_id: str | None = None,
):
    tool_name = "structured_logs"

    record_tool_call(tool_name)

    params: dict[str, Any] = {}

    if service:
        params["service"] = service

    if severity:
        params["severity"] = severity

    if correlation_id:
        params["correlation_id"] = (
            correlation_id
        )

    result = await _simulated_get(
        "/internal/logs",
        params,
    )

    if not result["available"]:
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            str(
                result.get("error")
                or "structured_logs_unavailable"
            ),
            result,
        )

    return _success(
        tool_name,
        result,
    )


async def collect_container_health():
    tool_name = "container_health"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/internal/container"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            str(
                result.get("error")
                or "container_health_unavailable"
            ),
            result,
        )

    return _success(
        tool_name,
        result,
    )


async def collect_database_signals():
    tool_name = "database_signals"

    record_tool_call(tool_name)

    simulated = await _simulated_get(
        "/internal/database"
    )

    try:
        select_1_result = test_database_connection()
        postgres = {
            "available": bool(select_1_result),
            "select_1": select_1_result,
            "error": None,
        }

    except Exception as exc:
        postgres = {
            "available": False,
            "select_1": None,
            "error": str(exc),
        }

    simulated_available = bool(
        simulated.get("available")
    )

    postgres_available = bool(
        postgres.get("available")
    )

    if (
        not simulated_available
        and not postgres_available
    ):
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            (
                "simulated_database_and_"
                "postgres_unavailable"
            ),
            {
                "simulated_service_db": simulated,
                "reliability_postgres": postgres,
            },
        )

    return _success(
        tool_name,
        {
            "simulated_service_db": simulated,
            "reliability_postgres": postgres,
        },
    )


async def collect_deployments():
    tool_name = "deployments"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/internal/deployment"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            str(
                result.get("error")
                or "deployment_information_unavailable"
            ),
            result,
        )

    return _success(
        tool_name,
        result,
    )


async def collect_service_health():
    tool_name = "service_health"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/health"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            str(
                result.get("error")
                or "service_health_unavailable"
            ),
            result,
        )

    return _success(
        tool_name,
        result,
    )


async def collect_full_diagnostics():
    """
    Collect all read-only diagnostic signals.

    Individual failures are preserved so one broken
    diagnostic source does not abort the investigation.
    """

    prometheus = (
        await collect_prometheus_snapshot()
    )

    health = (
        await collect_service_health()
    )

    logs = await collect_logs()

    container = (
        await collect_container_health()
    )

    database = (
        await collect_database_signals()
    )

    deployments = (
        await collect_deployments()
    )

    snapshot = (
        prometheus.get("result") or {}
        if prometheus.get("ok")
        else {}
    )

    return {
        "service": "simulated-api-service",
        "overall_status": snapshot.get(
            "overall_status",
            "UNKNOWN",
        ),
        "prometheus": prometheus,
        "service_health": health,
        "logs": logs,
        "container": container,
        "database": database,
        "deployments": deployments,
    }