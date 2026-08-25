import time

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.metrics import REQUEST_COUNT, REQUEST_LATENCY
from app.routes.health import router as health_router


app = FastAPI(
    title="Simulated Production API",
    version="1.0.0",
)


app.include_router(health_router)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    endpoint = request.url.path
    method = request.method
    status = str(response.status_code)

    REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status=status,
    ).inc()

    REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration)

    return response


@app.get("/")
def root():
    return {
        "service": "simulated-api-service",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )