from fastapi import FastAPI

from app.models import OperationEvent


app = FastAPI(
    title="Operations Reliability Agent - Simulated API",
    version="1.0.0",
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "simulated-api-service",
    }


@app.post("/events")
def create_event(event: OperationEvent):
    return {
        "status": "received",
        "event": event,
    }