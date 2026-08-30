from datetime import datetime, timezone

from app.state import state


# ============================================================
# Supported chaos scenarios
# ============================================================

SCENARIOS = {
    "normal",
    "high_error_rate",
    "service_unavailable",
    "recent_bad_deployment",
    "container_restart_loop",
    "database_unavailable",
    "traffic_spike",
    "high_latency",
    "http_400_spike",
    "combined_failure",
}


# ============================================================
# Reset scenario
# ============================================================

def reset_scenario() -> dict:
    with state.lock:
        state.scenario = "normal"
        state.version = "1.0.0"
        state.deployed_at = datetime.now(
            timezone.utc
        ).isoformat()

        state.restart_count = 0
        state.container_state = "running"
        state.container_health = "healthy"
        state.replicas = 1

        state.db_available = True
        state.db_latency_ms = 3.0
        state.db_connection_errors = 0

        state.resource_pressure = False

        state.history = [
            {
                "version": "1.0.0",
                "deployed_at": state.deployed_at,
                "bad": False,
            }
        ]

        state.logs.clear()

    return state.snapshot()


# ============================================================
# Apply chaos scenario
# ============================================================

def apply_scenario(name: str) -> dict:
    if name not in SCENARIOS:
        raise ValueError(
            f"Unknown chaos scenario: {name}"
        )

    # Always start from a clean baseline.
    reset_scenario()

    log_message = None

    with state.lock:
        state.scenario = name

        # ----------------------------------------------------
        # Normal
        # ----------------------------------------------------

        if name == "normal":
            pass

        # ----------------------------------------------------
        # High 5xx error rate
        # ----------------------------------------------------

        elif name == "high_error_rate":
            log_message = "Injected elevated 5xx rate"

        # ----------------------------------------------------
        # Service unavailable
        # ----------------------------------------------------

        elif name == "service_unavailable":
            state.container_state = "running"
            state.container_health = "healthy"

        # ----------------------------------------------------
        # Bad deployment
        # ----------------------------------------------------

        elif name == "recent_bad_deployment":
            state.version = "1.1.0-bad"

            state.deployed_at = datetime.now(
                timezone.utc
            ).isoformat()

            state.history.append(
                {
                    "version": "1.1.0-bad",
                    "deployed_at": state.deployed_at,
                    "bad": True,
                }
            )

            log_message = (
                "Application errors after bad deployment"
            )

        # ----------------------------------------------------
        # Container restart loop
        # ----------------------------------------------------

        elif name == "container_restart_loop":
            state.container_state = "restarting"
            state.container_health = "unhealthy"
            state.restart_count = 8

        # ----------------------------------------------------
        # Database unavailable
        # ----------------------------------------------------

        elif name == "database_unavailable":
            state.db_available = False
            state.db_connection_errors = 5

        # ----------------------------------------------------
        # Traffic spike
        # ----------------------------------------------------

        elif name == "traffic_spike":
            state.resource_pressure = True

        # ----------------------------------------------------
        # High latency
        # ----------------------------------------------------

        elif name == "high_latency":
            state.resource_pressure = True

        # ----------------------------------------------------
        # HTTP 400 spike
        # ----------------------------------------------------

        elif name == "http_400_spike":
            pass

        # ----------------------------------------------------
        # Combined failure
        # ----------------------------------------------------

        elif name == "combined_failure":
            state.version = "1.1.0-bad"

            state.deployed_at = datetime.now(
                timezone.utc
            ).isoformat()

            state.history.append(
                {
                    "version": "1.1.0-bad",
                    "deployed_at": state.deployed_at,
                    "bad": True,
                }
            )

            state.container_health = "unhealthy"
            state.container_state = "running"
            state.resource_pressure = True

            log_message = (
                "Combined failure after bad deployment"
            )

    # IMPORTANT:
    # add_log() acquires state.lock itself, so it must NOT
    # be called while already holding state.lock.
    if log_message:
        state.add_log(
            severity="ERROR",
            message=log_message,
            status="500",
        )

    return state.snapshot()


# ============================================================
# Restart service
# ============================================================

def restart_service() -> dict:
    with state.lock:
        state.restart_count += 1
        state.container_state = "running"
        state.container_health = "healthy"
        state.scenario = "normal"
        state.resource_pressure = False

    # Outside the lock to prevent deadlock.
    state.add_log(
        severity="INFO",
        message="Service restarted successfully",
    )

    return state.snapshot()


# ============================================================
# Rollback service
# ============================================================

def rollback_service() -> dict:
    with state.lock:
        state.version = "1.0.0"
        state.container_state = "running"
        state.container_health = "healthy"
        state.scenario = "normal"
        state.resource_pressure = False

    # Outside the lock to prevent deadlock.
    state.add_log(
        severity="INFO",
        message="Service rolled back to stable version",
    )

    return state.snapshot()


# ============================================================
# Scale service
# ============================================================

def scale_service() -> dict:
    with state.lock:
        state.replicas = max(
            2,
            state.replicas + 1,
        )

        state.resource_pressure = False

        replicas = state.replicas

    # Outside the lock to prevent deadlock.
    state.add_log(
        severity="INFO",
        message=(
            f"Service scaled to {replicas} replicas"
        ),
    )

    return state.snapshot()