from agents import function_tool


async def error_rate(
    metric_name: str = "5xx_error_rate",
) -> dict:
    """
    Get the current 5xx server error rate.

    This is currently simulated production telemetry.
    """

    current_error_rate = 0.0

    return {
        "metric_name": metric_name,
        "error_rate": current_error_rate,
        "unit": "percent",
        "has_errors": current_error_rate > 0,
        "healthy": current_error_rate == 0,
        "description": "No server-side 5xx errors detected.",
    }


@function_tool
async def get_error_rate(
    metric_name: str = "5xx_error_rate",
) -> dict:
    """
    Get the current 5xx server error rate.
    """

    return await error_rate(metric_name)