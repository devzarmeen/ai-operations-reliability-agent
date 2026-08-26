import os
from email.message import EmailMessage

import aiosmtplib
from dotenv import load_dotenv

from app.models.incident import Incident


load_dotenv()


async def send_email_alert(incident: Incident):
    """
    Send an email alert for a non-healthy incident.
    """

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    alert_email_to = os.getenv("ALERT_EMAIL_TO")

    if not all(
        [
            smtp_host,
            smtp_username,
            smtp_password,
            alert_email_to,
        ]
    ):
        print("[ALERT] SMTP configuration missing. Email skipped.")
        return

    subject = (
        f"[{incident.severity}] "
        f"{incident.service_name} - {incident.status}"
    )

    body = f"""
Operations Reliability Alert

Incident ID: #{incident.id}
Service: {incident.service_name}
Status: {incident.status}
Severity: {incident.severity}

Request Rate: {incident.request_rate} requests/sec
5xx Error Rate: {incident.error_rate}%
P95 Latency: {incident.p95_latency_seconds} seconds

Reason:
{incident.reason}

Please investigate the service.
"""

    message = EmailMessage()

    message["From"] = smtp_username
    message["To"] = alert_email_to
    message["Subject"] = subject

    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=smtp_host,
        port=smtp_port,
        start_tls=True,
        username=smtp_username,
        password=smtp_password,
    )

    print(
        f"[ALERT][EMAIL] Sent for Incident #{incident.id}"
    )


async def handle_incident_alert(incident: Incident):
    """
    Handle external alerts for reliability incidents.
    """

    if incident.status == "HEALTHY":
        return

    print(
        f"[ALERT][{incident.severity}] "
        f"Incident #{incident.id} - "
        f"{incident.service_name} is {incident.status}"
    )

    await send_email_alert(incident)