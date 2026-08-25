import asyncio

from app.diagnostics.health import check_service_health
from app.diagnostics.metrics import get_request_metrics
from app.diagnostics.errors import get_error_rate
from app.diagnostics.latency import get_latency


async def get_service_status() -> dict:
    """
    Get a complete reliability snapshot of the simulated API.
    """

    health, metrics, errors, latency = await asyncio.gather(
        check_service_health(),
        get_request_metrics(),
        get_error_rate(),
        get_latency(),
    )

    request_rate = None

    if metrics.get("result"):
        request_rate = float(metrics["result"][0]["value"][1])

    error_rate = errors.get("error_rate")
    p95_latency = latency.get("p95_latency_seconds")

    if not health.get("healthy"):
        overall_status = "DOWN"
    elif error_rate is not None and error_rate > 0:
        overall_status = "DEGRADED"
    else:
        overall_status = "HEALTHY"

    return {
        "service": "simulated-api-service",
        "overall_status": overall_status,
        "health": {
            "healthy": health.get("healthy"),
            "status_code": health.get("status_code"),
        },
        "metrics": {
            "request_rate_per_second": request_rate,
            "error_rate_per_second": error_rate,
            "p95_latency_seconds": p95_latency,
        },
    }