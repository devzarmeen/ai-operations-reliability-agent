from prometheus_client import Gauge


# --------------------------------
# Incident Metrics
# --------------------------------

INCIDENTS_TOTAL = Gauge(
    "reliability_incidents_total",
    "Total number of reliability incidents",
)

INCIDENTS_BY_STATUS = Gauge(
    "reliability_incidents_by_status",
    "Number of incidents by status",
    ["status"],
)

INCIDENTS_BY_SEVERITY = Gauge(
    "reliability_incidents_by_severity",
    "Number of incidents by severity",
    ["severity"],
)


# --------------------------------
# Current Reliability Metrics
# --------------------------------

REQUEST_RATE = Gauge(
    "reliability_request_rate",
    "Current API request rate",
)

ERROR_RATE = Gauge(
    "reliability_error_rate",
    "Current 5xx error rate percentage",
)

P95_LATENCY = Gauge(
    "reliability_p95_latency_seconds",
    "Current P95 request latency in seconds",
)

SERVICE_HEALTH = Gauge(
    "reliability_service_health",
    "Current service health (1=healthy, 0=down)",
)


def update_reliability_metrics(
    *,
    total: int,
    healthy: int,
    degraded: int,
    down: int,
    low: int,
    medium: int,
    high: int,
    critical: int,
    request_rate: float | None = None,
    error_rate: float | None = None,
    p95_latency: float | None = None,
    service_healthy: bool | None = None,
):
    """
    Update Prometheus metrics using current reliability data.
    """

    INCIDENTS_TOTAL.set(total)

    INCIDENTS_BY_STATUS.labels("HEALTHY").set(healthy)
    INCIDENTS_BY_STATUS.labels("DEGRADED").set(degraded)
    INCIDENTS_BY_STATUS.labels("DOWN").set(down)

    INCIDENTS_BY_SEVERITY.labels("LOW").set(low)
    INCIDENTS_BY_SEVERITY.labels("MEDIUM").set(medium)
    INCIDENTS_BY_SEVERITY.labels("HIGH").set(high)
    INCIDENTS_BY_SEVERITY.labels("CRITICAL").set(critical)

    if request_rate is not None:
        REQUEST_RATE.set(request_rate)

    if error_rate is not None:
        ERROR_RATE.set(error_rate)

    if p95_latency is not None:
        P95_LATENCY.set(p95_latency)

    if service_healthy is not None:
        SERVICE_HEALTH.set(
            1 if service_healthy else 0
        )