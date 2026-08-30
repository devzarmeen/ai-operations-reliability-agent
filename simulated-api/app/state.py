from collections import deque
from datetime import datetime, timezone
from threading import Lock


class SimulatedState:
    def __init__(self) -> None:
        self.lock = Lock()
        self.scenario = "normal"
        self.version = "1.0.0"
        self.deployed_at = datetime.now(timezone.utc).isoformat()
        self.history = [
            {
                "version": "1.0.0",
                "deployed_at": self.deployed_at,
                "bad": False,
            }
        ]
        self.restart_count = 0
        self.container_state = "running"
        self.container_health = "healthy"
        self.replicas = 1
        self.db_available = True
        self.db_latency_ms = 3.0
        self.db_connection_errors = 0
        self.resource_pressure = False
        self.logs: deque = deque(maxlen=400)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "scenario": self.scenario,
                "version": self.version,
                "deployed_at": self.deployed_at,
                "history": list(self.history),
                "restart_count": self.restart_count,
                "container_state": self.container_state,
                "container_health": self.container_health,
                "replicas": self.replicas,
                "db_available": self.db_available,
                "db_latency_ms": self.db_latency_ms,
                "db_connection_errors": self.db_connection_errors,
                "resource_pressure": self.resource_pressure,
            }

    def add_log(
        self,
        *,
        severity: str,
        message: str,
        endpoint: str | None = None,
        correlation_id: str | None = None,
        status: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "simulated-api-service",
            "severity": severity,
            "message": message,
            "endpoint": endpoint,
            "correlation_id": correlation_id,
            "status": status,
        }
        with self.lock:
            self.logs.append(entry)

    def query_logs(
        self,
        service: str | None = None,
        severity: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        with self.lock:
            items = list(self.logs)
        if service:
            items = [item for item in items if item["service"] == service]
        if severity:
            items = [item for item in items if item["severity"].lower() == severity.lower()]
        if correlation_id:
            items = [item for item in items if item.get("correlation_id") == correlation_id]

        counts: dict[str, int] = {}
        for item in items:
            if item["severity"] in {"ERROR", "CRITICAL"}:
                counts[item["message"]] = counts.get(item["message"], 0) + 1
        repeated = [
            {"message": message, "count": count}
            for message, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
            if count >= 3
        ]
        return {
            "count": len(items),
            "entries": items[-50:],
            "repeated_errors": repeated,
            "error_patterns": [item["message"] for item in repeated],
        }


state = SimulatedState()
