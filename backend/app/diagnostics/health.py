import time

import httpx
from agents import function_tool

from app.core.config import settings


async def service_health(
    service_name: str = "simulated-api-service",
) -> dict:
    health_url = f"{settings.simulated_api_url.rstrip('/')}/health"
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)

        elapsed_ms = (time.perf_counter() - started) * 1000
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"raw": response.text[:200]}

        api_status = str(response_data.get("status", "")).lower()
        is_healthy = response.status_code == 200 and api_status == "healthy"

        return {
            "service": service_name,
            "url": health_url,
            "status_code": response.status_code,
            "healthy": is_healthy,
            "latency_ms": round(elapsed_ms, 2),
            "response": response_data,
        }

    except httpx.RequestError as exc:
        return {
            "service": service_name,
            "url": health_url,
            "status_code": None,
            "healthy": False,
            "latency_ms": None,
            "error": str(exc),
        }


@function_tool
async def check_service_health(
    service_name: str = "simulated-api-service",
) -> dict:
    """
    Check the health of the simulated production API.
    """
    return await service_health(service_name)
