from app.models.incident import Incident


def handle_incident_alert(incident: Incident):
    """
    Handle alerts for reliability incidents.
    """

    if incident.status == "HEALTHY":
        return

    if incident.severity == "CRITICAL":
        print(
            f"[ALERT][CRITICAL] "
            f"Incident #{incident.id} - "
            f"{incident.service_name} is DOWN"
        )

    elif incident.severity == "HIGH":
        print(
            f"[ALERT][HIGH] "
            f"Incident #{incident.id} - "
            f"{incident.service_name} has high error rate"
        )

    elif incident.severity == "MEDIUM":
        print(
            f"[ALERT][MEDIUM] "
            f"Incident #{incident.id} - "
            f"{incident.service_name} is DEGRADED"
        )