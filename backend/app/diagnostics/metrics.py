from agents import function_tool


async def request_metrics(
    metric_name: str = "api_request_rate",
) -> dict:
    """
    Get the current API request rate metric.

    This is currently simulated production telemetry.
    """

    # Simulated production metric
    request_rate = 0.20

    return {
        "metric_name": metric_name,
        "value": request_rate,
        "unit": "requests_per_second",
        "healthy": True,
        "description": "Current API request rate is steady.",
    }


@function_tool
async def get_request_metrics(
    metric_name: str = "api_request_rate",
) -> dict:
    """
    Get the current API request rate metric.
    """

    return await request_metrics(metric_name)