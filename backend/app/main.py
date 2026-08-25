from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agent import router as agent_router
from app.api.incidents import router as incidents_router
from app.core.database import create_db_and_tables
from app.services.database_test import test_database_connection
from app.scheduler.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    create_db_and_tables()

    # Start automatic reliability checks
    start_scheduler()

    print("[APP] Operations Reliability Agent started")

    yield

    # Stop scheduler when application shuts down
    stop_scheduler()

    print("[APP] Operations Reliability Agent stopped")


app = FastAPI(
    title="Operations Reliability Agent API",
    description="Backend API for the Operations Reliability Agent",
    version="0.1.0",
    lifespan=lifespan,
)


app.include_router(agent_router)
app.include_router(incidents_router)


@app.get("/")
async def root():
    return {
        "message": "Operations Reliability Agent API"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "operations-reliability-agent",
    }


@app.get("/health/database")
def database_health():
    result = test_database_connection()

    return {
        "database": "connected",
        "result": result,
    }