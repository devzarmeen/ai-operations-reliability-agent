from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from app.api.actions import router as actions_router
from app.api.agent import router as agent_router
from app.api.alerts import router as alerts_router
from app.api.diagnostics import router as diagnostics_router
from app.api.incidents import router as incidents_router
from app.api.investigations import (
    router as investigations_router,
)

from app.core.database import create_db_and_tables

from app.scheduler.scheduler import (
    start_scheduler,
    stop_scheduler,
)

from app.services.database_test import (
    test_database_connection,
)


# ============================================================
# Application lifecycle
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup/shutdown lifecycle.
    """

    # --------------------------------------------------------
    # Startup
    # --------------------------------------------------------

    create_db_and_tables()

    start_scheduler()

    print(
        "[APP] Operations Reliability Agent started"
    )

    try:
        yield

    finally:
        # ----------------------------------------------------
        # Shutdown
        # ----------------------------------------------------

        stop_scheduler()

        print(
            "[APP] Operations Reliability Agent stopped"
        )


# ============================================================
# FastAPI application
# ============================================================


app = FastAPI(
    title="Operations Reliability Agent API",
    description=(
        "Backend API for the Operations Reliability Agent"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================
# CORS
# ============================================================


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API routers
# ============================================================


app.include_router(
    agent_router
)

app.include_router(
    incidents_router
)

app.include_router(
    diagnostics_router
)

app.include_router(
    alerts_router
)

app.include_router(
    investigations_router
)

app.include_router(
    actions_router
)


# ============================================================
# Root
# ============================================================


@app.get("/")
async def root():
    return {
        "message": (
            "Operations Reliability Agent API"
        )
    }


# ============================================================
# Application health
# ============================================================


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": (
            "operations-reliability-agent"
        ),
    }


# ============================================================
# Database health
# ============================================================


@app.get("/health/database")
def database_health():
    result = test_database_connection()

    return {
        "database": (
            "connected"
            if result
            else "unavailable"
        ),
        "result": result,
    }


# ============================================================
# Prometheus metrics
# ============================================================


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )