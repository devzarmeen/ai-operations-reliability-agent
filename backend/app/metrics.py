from prometheus_client import Counter, Gauge


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


# --------------------------------
# Agent observability
# --------------------------------

INVESTIGATIONS_STARTED = Counter(
    "reliability_investigations_started_total",
    "Investigations started by the reliability agent",
)

INVESTIGATIONS_COMPLETED = Counter(
    "reliability_investigations_completed_total",
    "Investigations completed by the reliability agent",
    ["outcome"],
)

DIAGNOSTIC_TOOL_CALLS = Counter(
    "reliability_diagnostic_tool_calls_total",
    "Diagnostic tool invocations",
    ["tool"],
)

DIAGNOSTIC_TOOL_FAILURES = Counter(
    "reliability_diagnostic_tool_failures_total",
    "Diagnostic tool failures",
    ["tool"],
)

APPROVAL_REQUESTS = Counter(
    "reliability_approval_requests_total",
    "High-impact approval requests created",
    ["action"],
)

APPROVAL_DECISIONS = Counter(
    "reliability_approval_decisions_total",
    "Human approval decisions",
    ["decision"],
)

RECOVERY_RESULTS = Counter(
    "reliability_recovery_results_total",
    "Recovery verification outcomes",
    ["result"],
)


def record_tool_call(tool: str) -> None:
    DIAGNOSTIC_TOOL_CALLS.labels(tool=tool).inc()


def record_tool_failure(tool: str) -> None:
    DIAGNOSTIC_TOOL_FAILURES.labels(tool=tool).inc()


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