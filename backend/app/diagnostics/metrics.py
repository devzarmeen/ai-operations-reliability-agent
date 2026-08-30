from agents import function_tool

from app.services.prometheus import prometheus_service


REQUEST_RATE_QUERY = "sum(rate(simulated_api_requests_total[30s]))"


async def request_metrics(
    metric_name: str = "api_request_rate",
) -> dict:
    """Get the current API request rate from Prometheus."""
    result = await prometheus_service.scalar(REQUEST_RATE_QUERY)

    if not result["ok"]:
        return {
            "metric_name": metric_name,
            "value": None,
            "unit": "requests_per_second",
            "healthy": None,
            "available": False,
            "error": result["error"],
            "query": result["query"],
            "description": "Request rate is unavailable; Prometheus query failed.",
        }

    value = result["value"]
    return {
        "metric_name": metric_name,
        "value": value,
        "unit": "requests_per_second",
        "healthy": True if value is not None else None,
        "available": value is not None,
        "error": None,
        "query": result["query"],
        "description": (
            "Current API request rate from Prometheus."
            if value is not None
            else "No request-rate series found for the selected window."
        ),
    }


@function_tool
async def get_request_metrics(
    metric_name: str = "api_request_rate",
) -> dict:
    """
    Get the current API request rate metric.
    """
    return await request_metrics(metric_name)
