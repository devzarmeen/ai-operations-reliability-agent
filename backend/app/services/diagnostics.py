"""Read-only diagnostic collection for the simulated production service."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.metrics import (
    record_tool_call,
    record_tool_failure,
)
from app.services.database_test import (
    test_database_connection,
)
from app.services.prometheus import (
    prometheus_service,
)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _success(
    tool_name: str,
    result: Any,
) -> dict[str, Any]:
    """Build a successful diagnostic tool response."""

    return {
        "ok": True,
        "tool": tool_name,
        "result": result,
    }


def _failure(
    tool_name: str,
    error: str,
    result: Any | None = None,
) -> dict[str, Any]:
    """Build a failed diagnostic tool response."""

    payload: dict[str, Any] = {
        "ok": False,
        "tool": tool_name,
        "error": error,
    }

    if result is not None:
        payload["result"] = result

    return payload


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def _sanitize(payload: Any) -> Any:
    """Remove sensitive-looking values from diagnostic output."""

    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}

        sensitive_tokens = (
            "password",
            "token",
            "webhook",
            "api_key",
            "authorization",
            "secret",
        )

        for key, value in payload.items():
            lowered = str(key).lower()

            if any(
                token in lowered
                for token in sensitive_tokens
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


# ---------------------------------------------------------------------------
# Simulated API helper
# ---------------------------------------------------------------------------

async def _simulated_get(
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Perform a read-only request against the simulated API.
    """

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
                "raw": response.text[:500],
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

    except httpx.TimeoutException as exc:
        return {
            "available": False,
            "status_code": None,
            "error": f"timeout: {exc}",
            "data": None,
        }

    except httpx.RequestError as exc:
        return {
            "available": False,
            "status_code": None,
            "error": f"request_failed: {exc}",
            "data": None,
        }

    except Exception as exc:
        return {
            "available": False,
            "status_code": None,
            "error": str(exc),
            "data": None,
        }


# ---------------------------------------------------------------------------
# Prometheus diagnostics
# ---------------------------------------------------------------------------

async def collect_prometheus_snapshot() -> dict[str, Any]:

    tool_name = "prometheus_metrics"

    record_tool_call(tool_name)

    queries = {
        "error_rate_percent": (
            "reliability_error_rate"
        ),
        "p95_latency_seconds": (
            "reliability_p95_latency_seconds"
        ),
        "request_rate_per_second": (
            "reliability_request_rate"
        ),
        "service_health": (
            "reliability_service_health"
        ),
    }

    metrics: dict[str, Any] = {}
    query_errors: dict[str, str] = {}

    for name, promql in queries.items():

        try:
            result = await prometheus_service.scalar(
                promql
            )

            if result.get("ok"):

                metrics[name] = result.get(
                    "value"
                )

                # Prometheus successfully answered,
                # but the query may have no series.
                if result.get("value") is None:
                    query_errors[name] = (
                        "metric returned no numeric value"
                    )

            else:
                metrics[name] = None

                query_errors[name] = (
                    result.get("error")
                    or "prometheus query failed"
                )

        except Exception as exc:

            metrics[name] = None

            query_errors[name] = str(exc)

    usable_metrics = {
        key: value
        for key, value in metrics.items()
        if value is not None
    }

    if not usable_metrics:

        record_tool_failure(tool_name)

        return _failure(
            tool_name,
            "Prometheus returned no usable metric values",
            {
                "source": "prometheus",
                "queries": queries,
                "metrics": metrics,
                "query_errors": query_errors,
            },
        )

    # ---------------------------------------------------------------
    # Determine Prometheus service health.
    # ---------------------------------------------------------------

    health_value = metrics.get(
        "service_health"
    )

    if health_value is None:
        overall_status = "UNKNOWN"

    elif float(health_value) >= 1:
        overall_status = "HEALTHY"

    else:
        overall_status = "UNHEALTHY"

    return _success(
        tool_name,
        {
            "overall_status": overall_status,
            "source": "prometheus",
            "job": "operations-reliability-agent",

            "metrics": metrics,

            # Compatibility fields
            # used by investigation.py
            "error_rate_percent": metrics.get(
                "error_rate_percent"
            ),
            "p95_latency_seconds": metrics.get(
                "p95_latency_seconds"
            ),
            "request_rate_per_second": metrics.get(
                "request_rate_per_second"
            ),
            "service_health": metrics.get(
                "service_health"
            ),

            "queries": queries,
            "query_errors": query_errors,
        },
    )


# ---------------------------------------------------------------------------
# Structured logs
# ---------------------------------------------------------------------------

async def collect_logs(
    service: str | None = None,
    severity: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:

    tool_name = "structured_logs"

    record_tool_call(tool_name)

    params: dict[str, str] = {}

    if service:
        params["service"] = service

    if severity:
        params["severity"] = severity

    if correlation_id:
        params["correlation_id"] = correlation_id

    result = await _simulated_get(
        "/internal/logs",
        params,
    )

    if not result["available"]:
        record_tool_failure(tool_name)

    return {
        "ok": result["available"],
        "tool": tool_name,
        "result": _sanitize(result),
    }


# ---------------------------------------------------------------------------
# Container health
# ---------------------------------------------------------------------------

async def collect_container_health() -> dict[str, Any]:

    tool_name = "container_health"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/internal/container"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

    return {
        "ok": result["available"],
        "tool": tool_name,
        "result": _sanitize(result),
    }


# ---------------------------------------------------------------------------
# Database signals
# ---------------------------------------------------------------------------

async def collect_database_signals() -> dict[str, Any]:

    tool_name = "database_signals"

    record_tool_call(tool_name)

    simulated = await _simulated_get(
        "/internal/database"
    )

    try:
        select_result = (
            test_database_connection()
        )

        postgres = {
            "available": True,
            "select_1": select_result,
            "error": None,
        }

    except Exception as exc:

        postgres = {
            "available": False,
            "select_1": None,
            "error": str(exc),
        }

    simulated_ok = bool(
        simulated.get("available")
    )

    postgres_ok = bool(
        postgres.get("available")
    )

    if not simulated_ok and not postgres_ok:
        record_tool_failure(tool_name)

    return {
        "ok": simulated_ok or postgres_ok,
        "tool": tool_name,
        "result": {
            "simulated_service_db": _sanitize(
                simulated
            ),
            "reliability_postgres": _sanitize(
                postgres
            ),
        },
    }


# ---------------------------------------------------------------------------
# Deployment diagnostics
# ---------------------------------------------------------------------------

async def collect_deployments() -> dict[str, Any]:

    tool_name = "deployments"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/internal/deployment"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

    return {
        "ok": result["available"],
        "tool": tool_name,
        "result": _sanitize(result),
    }


# ---------------------------------------------------------------------------
# Service health
# ---------------------------------------------------------------------------

async def collect_service_health() -> dict[str, Any]:

    tool_name = "service_health"

    record_tool_call(tool_name)

    result = await _simulated_get(
        "/health"
    )

    if not result["available"]:
        record_tool_failure(tool_name)

    return {
        "ok": result["available"],
        "tool": tool_name,
        "result": _sanitize(result),
    }


# ---------------------------------------------------------------------------
# Full diagnostics
# ---------------------------------------------------------------------------

async def collect_full_diagnostics() -> dict[str, Any]:
    """
    Collect the complete read-only diagnostic snapshot.

    IMPORTANT:
    This function only reads diagnostic information.
    It never performs recovery actions.
    """

    prometheus = (
        await collect_prometheus_snapshot()
    )

    health = (
        await collect_service_health()
    )

    logs = (
        await collect_logs()
    )

    container = (
        await collect_container_health()
    )

    database = (
        await collect_database_signals()
    )

    deployments = (
        await collect_deployments()
    )

    prometheus_result = (
        prometheus.get("result")
        if prometheus.get("ok")
        else {}
    )

    if not isinstance(
        prometheus_result,
        dict,
    ):
        prometheus_result = {}

    return {
        "service": "simulated-api-service",

        "overall_status": (
            prometheus_result.get(
                "overall_status",
                "UNKNOWN",
            )
        ),

        "prometheus": prometheus,

        "service_health": health,

        "logs": logs,

        "container": container,

        "database": database,

        "deployments": deployments,
    }