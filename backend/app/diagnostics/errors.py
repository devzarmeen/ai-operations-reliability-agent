from agents import function_tool

from app.services.prometheus import prometheus_service


ERROR_RATE_QUERY = (
    "sum(rate("
    'simulated_api_requests_total{job="simulated-api",status=~"5.."}'
    "[5m]))"
    " / clamp_min("
    "sum(rate("
    'simulated_api_requests_total{job="simulated-api"}'
    "[5m])),"
    "1e-9"
    ") * 100"
)

ERROR_COUNT_QUERY = (
    "sum(increase("
    'simulated_api_requests_total{job="simulated-api",status=~"5.."}'
    "[5m]))"
)

CLIENT_ERROR_RATE_QUERY = (
    "sum(rate("
    'simulated_api_requests_total{job="simulated-api",status=~"4.."}'
    "[5m]))"
    " / clamp_min("
    "sum(rate("
    'simulated_api_requests_total{job="simulated-api"}'
    "[5m])),"
    "1e-9"
    ") * 100"
)


async def error_rate(
    metric_name: str = "5xx_error_rate",
) -> dict:
    """Get the current 5xx error rate from Prometheus."""

    rate = await prometheus_service.scalar(
        ERROR_RATE_QUERY
    )

    count = await prometheus_service.scalar(
        ERROR_COUNT_QUERY
    )

    client_rate = await prometheus_service.scalar(
        CLIENT_ERROR_RATE_QUERY
    )

    if not rate["ok"]:
        return {
            "metric_name": metric_name,
            "error_rate": None,
            "error_count_5m": None,
            "client_error_rate": None,
            "unit": "percent",
            "has_errors": None,
            "healthy": None,
            "available": False,
            "error": rate["error"],
            "query": rate["query"],
            "description": (
                "Error rate is unavailable; "
                "Prometheus query failed."
            ),
        }

    current = rate["value"]

    return {
        "metric_name": metric_name,
        "error_rate": current,
        "error_count_5m": count["value"],
        "client_error_rate": client_rate["value"],
        "unit": "percent",
        "has_errors": bool(
            current is not None and current > 0
        ),
        "healthy": (
            current is not None
            and current == 0
        ),
        "available": current is not None,
        "error": None,
        "query": rate["query"],
        "description": (
            "No server-side 5xx errors detected."
            if current == 0
            else (
                "Server-side 5xx error rate "
                "from Prometheus."
                if current is not None
                else (
                    "No 5xx error-rate series "
                    "found for the selected window."
                )
            )
        ),
    }


@function_tool
async def get_error_rate(
    metric_name: str = "5xx_error_rate",
) -> dict:
    """
    Get the current 5xx server error rate.
    """
    return await error_rate(metric_name)
