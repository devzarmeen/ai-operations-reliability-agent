from agents import function_tool


async def latency(
    metric_name: str = "p95_request_latency",
) -> dict:
    """
    Get the current P95 API request latency.

    This is currently simulated production telemetry.
    """

    p95_latency_seconds = 0.022

    return {
        "metric_name": metric_name,
        "value": p95_latency_seconds,
        "unit": "seconds",
        "milliseconds": p95_latency_seconds * 1000,
        "healthy": p95_latency_seconds < 0.100,
        "description": "P95 latency is within the acceptable threshold.",
    }


@function_tool
async def get_latency(
    metric_name: str = "p95_request_latency",
) -> dict:
    """
    Get the current P95 API request latency.
    """

    return await latency(metric_name)