import asyncio

from app.diagnostics.errors import error_rate
from app.diagnostics.health import service_health
from app.diagnostics.latency import latency
from app.diagnostics.metrics import request_metrics


async def get_service_status() -> dict:
    """
    Get a complete reliability snapshot of the simulated API.
    """
    health, metrics, errors, latency_result = await asyncio.gather(
        service_health(),
        request_metrics(),
        error_rate(),
        latency(),
    )

    request_rate = metrics.get("value")
    current_error_rate = errors.get("error_rate")
    p95_latency = latency_result.get("value")

    if not health.get("healthy"):
        overall_status = "DOWN"
    elif current_error_rate is not None and current_error_rate > 5:
        overall_status = "DEGRADED"
    elif p95_latency is not None and p95_latency > 0.100:
        overall_status = "DEGRADED"
    else:
        overall_status = "HEALTHY"

    return {
        "service": "simulated-api-service",
        "overall_status": overall_status,
        "health": {
            "healthy": health.get("healthy"),
            "status_code": health.get("status_code"),
            "latency_ms": health.get("latency_ms"),
        },
        "metrics": {
            "request_rate_per_second": request_rate,
            "error_rate_percent": current_error_rate,
            "error_count_5m": errors.get("error_count_5m"),
            "client_error_rate_percent": errors.get("client_error_rate"),
            "p50_latency_seconds": latency_result.get("p50"),
            "p95_latency_seconds": p95_latency,
            "p99_latency_seconds": latency_result.get("p99"),
        },
        "sources": {
            "health": health,
            "request_rate": metrics,
            "errors": errors,
            "latency": latency_result,
        },
    }
