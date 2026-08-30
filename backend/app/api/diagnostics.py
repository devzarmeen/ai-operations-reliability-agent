from fastapi import APIRouter

from app.services.diagnostics import collect_full_diagnostics
from app.services.prometheus import prometheus_service


router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"])


@router.get("")
async def diagnostics():
    """Structured service-health snapshot for operators and the agent."""
    return await collect_full_diagnostics()


@router.get("/prometheus")
async def prometheus_query(query: str):
    """Execute a read-only PromQL instant query."""
    return await prometheus_service.query(query)
