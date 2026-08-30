import asyncio
import random
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from app.chaos import (
    SCENARIOS,
    apply_scenario,
    reset_scenario,
    restart_service,
    rollback_service,
    scale_service,
)
from app.models import OperationEvent
from app.state import state


app = FastAPI(
    title="Operations Reliability Agent - Simulated API",
    version="1.0.0",
)


REQUEST_COUNT = Counter(
    "simulated_api_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "simulated_api_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)

CONTROL_PREFIXES = ("/health", "/metrics", "/chaos", "/admin", "/internal")


def _is_control_path(path: str) -> bool:
    return path == "/metrics" or path.startswith(CONTROL_PREFIXES)


@app.middleware("http")
async def chaos_and_metrics_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    path = request.url.path
    scenario = state.snapshot()["scenario"]

    if not _is_control_path(path):
        if scenario in {"high_latency", "combined_failure"}:
            await asyncio.sleep(0.35)
        elif scenario == "extreme_latency":
            await asyncio.sleep(1.5)
        elif scenario == "database_latency":
            await asyncio.sleep(0.25)
        elif scenario == "resource_pressure":
            await asyncio.sleep(0.2)

        forced_status = None
        error_message = None
        if scenario == "http_500_spike" and random.random() < 0.8:
            forced_status, error_message = 500, "Injected HTTP 500 spike"
        elif scenario == "high_error_rate" and random.random() < 0.35:
            forced_status, error_message = 500, "Injected elevated 5xx rate"
        elif scenario == "http_400_spike" and random.random() < 0.8:
            forced_status, error_message = 400, "Injected HTTP 400 spike"
        elif scenario == "repeated_exception":
            forced_status, error_message = 500, "Repeated application exception: NullPointer"
        elif scenario == "dependency_failure" and path != "/health":
            forced_status, error_message = 502, "Upstream dependency failure"
        elif scenario == "recent_bad_deployment" and random.random() < 0.5:
            forced_status, error_message = 500, "Regression in version 1.1.0-bad"
        elif scenario == "combined_failure" and random.random() < 0.45:
            forced_status, error_message = 500, "Combined failure: deploy + dependency"
        elif scenario == "database_unavailable" and path == "/events":
            forced_status, error_message = 503, "Simulated database unavailable"
        elif scenario == "database_connection_failure" and path == "/events":
            forced_status, error_message = 503, "Simulated database connection failure"
        elif scenario == "service_unavailable":
            forced_status, error_message = 503, "Service unavailable"

        if forced_status is not None:
            state.add_log(
                severity="ERROR",
                message=error_message or "Injected failure",
                endpoint=path,
                status=str(forced_status),
            )
            response = JSONResponse(
                status_code=forced_status,
                content={"status": "error", "error": error_message, "scenario": scenario},
            )
            duration = time.perf_counter() - start_time
            REQUEST_COUNT.labels(request.method, path, str(forced_status)).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(duration)
            return response

    response = await call_next(request)
    duration = time.perf_counter() - start_time
    REQUEST_COUNT.labels(
        request.method,
        path,
        str(response.status_code),
    ).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)

    severity = "INFO" if response.status_code < 400 else "ERROR"
    state.add_log(
        severity=severity,
        message=f"{request.method} {path} -> {response.status_code}",
        endpoint=path,
        status=str(response.status_code),
        correlation_id=request.headers.get("x-request-id"),
    )
    return response


@app.get("/health")
def health():
    snapshot = state.snapshot()
    scenario = snapshot["scenario"]
    if scenario in {"service_unavailable"}:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "service": "simulated-api-service", "scenario": scenario},
        )
    if scenario in {"container_unhealthy", "container_restart_loop"}:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "service": "simulated-api-service", "scenario": scenario},
        )
    return {
        "status": "healthy",
        "service": "simulated-api-service",
        "version": snapshot["version"],
        "scenario": scenario,
    }


@app.post("/events")
def create_event(event: OperationEvent):
    snapshot = state.snapshot()
    if snapshot["scenario"] == "database_latency":
        time.sleep(0.05)
    return {
        "status": "received",
        "event": event,
        "version": snapshot["version"],
    }


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/internal/logs")
def internal_logs(service: str | None = None, severity: str | None = None, correlation_id: str | None = None):
    return state.query_logs(service=service, severity=severity, correlation_id=correlation_id)


@app.get("/internal/container")
def internal_container():
    snapshot = state.snapshot()
    return {
        "name": "simulated-api",
        "state": snapshot["container_state"],
        "health": snapshot["container_health"],
        "restart_count": snapshot["restart_count"],
        "replicas": snapshot["replicas"],
        "resource_pressure": snapshot["resource_pressure"],
    }


@app.get("/internal/database")
def internal_database():
    snapshot = state.snapshot()
    return {
        "available": snapshot["db_available"],
        "latency_ms": snapshot["db_latency_ms"],
        "connection_errors": snapshot["db_connection_errors"],
        "engine": "simulated-postgres-signal",
    }


@app.get("/internal/deployment")
def internal_deployment():
    snapshot = state.snapshot()
    current = snapshot["history"][-1] if snapshot["history"] else {}
    bad = bool(current.get("bad")) or snapshot["scenario"] in {
        "recent_bad_deployment",
        "combined_failure",
    }
    return {
        "current_version": snapshot["version"],
        "deployed_at": snapshot["deployed_at"],
        "recent_deployment": bad,
        "bad_deployment": bad,
        "history": snapshot["history"][-10:],
    }


@app.post("/chaos/scenario")
def set_scenario(payload: dict):
    name = str(payload.get("scenario") or "")
    try:
        return apply_scenario(name)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc), "allowed": sorted(SCENARIOS)})


@app.post("/chaos/reset")
def chaos_reset():
    return reset_scenario()


@app.get("/chaos/status")
def chaos_status():
    return {"allowed": sorted(SCENARIOS), "state": state.snapshot()}


@app.post("/admin/restart")
def admin_restart():
    return restart_service()


@app.post("/admin/rollback")
def admin_rollback():
    return rollback_service()


@app.post("/admin/scale")
def admin_scale():
    return scale_service()
