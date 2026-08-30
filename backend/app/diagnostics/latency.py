from agents import function_tool

from app.services.prometheus import prometheus_service


def _quantile_query(quantile: float) -> str:
    return (
        f"histogram_quantile({quantile}, "
        "sum(rate(simulated_api_request_latency_seconds_bucket[30s])) by (le))"
    )


async def latency(
    metric_name: str = "p95_request_latency",
) -> dict:
    """Get request latency percentiles from Prometheus."""
    p50 = await prometheus_service.scalar(_quantile_query(0.50))
    p95 = await prometheus_service.scalar(_quantile_query(0.95))
    p99 = await prometheus_service.scalar(_quantile_query(0.99))

    if not p95["ok"]:
        return {
            "metric_name": metric_name,
            "value": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "unit": "seconds",
            "milliseconds": None,
            "healthy": None,
            "available": False,
            "error": p95["error"],
            "query": p95["query"],
            "description": "Latency is unavailable; Prometheus query failed.",
        }

    value = p95["value"]
    return {
        "metric_name": metric_name,
        "value": value,
        "p50": p50["value"],
        "p95": value,
        "p99": p99["value"],
        "unit": "seconds",
        "milliseconds": None if value is None else value * 1000,
        "healthy": None if value is None else value < 0.100,
        "available": value is not None,
        "error": None,
        "query": p95["query"],
        "description": (
            "P95 latency is within the acceptable threshold."
            if value is not None and value < 0.100
            else "P95 latency from Prometheus."
            if value is not None
            else "No latency histogram series found for the selected window."
        ),
    }


@function_tool
async def get_latency(
    metric_name: str = "p95_request_latency",
) -> dict:
    """
    Get the current P95 API request latency.
    """
    return await latency(metric_name)
