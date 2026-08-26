import httpx
from agents import function_tool


PRODUCTION_API_URL = "http://127.0.0.1:8001"


async def service_health(
    service_name: str = "simulated-api-service",
) -> dict:
    health_url = f"{PRODUCTION_API_URL}/health"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)

        response_data = response.json()

        api_status = response_data.get("status", "").lower()

        is_healthy = (
            response.status_code == 200
            and api_status == "healthy"
        )

        return {
            "service": service_name,
            "url": health_url,
            "status_code": response.status_code,
            "healthy": is_healthy,
            "response": response_data,
        }

    except httpx.RequestError as exc:
        return {
            "service": service_name,
            "url": health_url,
            "status_code": None,
            "healthy": False,
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