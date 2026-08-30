import os
from email.message import EmailMessage

import aiosmtplib
import httpx
from dotenv import load_dotenv

from app.models.incident import Incident


load_dotenv()


async def send_email_alert(incident: Incident):
    """
    Send an email alert for a reliability incident or recovery event.
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
        print(
            "[ALERT][EMAIL] SMTP configuration missing. "
            "Email skipped."
        )
        return

    # Use a different subject for recovery
    if incident.status == "HEALTHY":
        subject = (
            f"[RECOVERY] "
            f"{incident.service_name} - {incident.status}"
        )
    else:
        subject = (
            f"[{incident.severity}] "
            f"{incident.service_name} - {incident.status}"
        )

    # Use a different body for recovery
    if incident.status == "HEALTHY":
        title = "Operations Reliability Recovery"
        message_line = (
            "The service has recovered and is reporting "
            "a healthy status."
        )
    else:
        title = "Operations Reliability Alert"
        message_line = "Please investigate the service."

    body = f"""
{title}

Incident ID: #{incident.id}
Service: {incident.service_name}
Status: {incident.status}
Severity: {incident.severity}

Request Rate: {incident.request_rate} requests/sec
5xx Error Rate: {incident.error_rate}%
P95 Latency: {incident.p95_latency_seconds} seconds

Reason:
{incident.reason}

{message_line}
"""

    message = EmailMessage()

    message["From"] = smtp_username
    message["To"] = alert_email_to
    message["Subject"] = subject

    message.set_content(body)

    try:
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

    except Exception as exc:
        print(
            f"[ALERT][EMAIL] Failed for Incident "
            f"#{incident.id}: {exc}"
        )


async def send_slack_alert(incident: Incident, investigation=None):
    """
    Send a Slack alert for a reliability incident or recovery event.
    """

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print(
            "[ALERT][SLACK] Webhook URL missing. "
            "Slack alert skipped."
        )
        return

    # Different Slack message for recovery
    if incident.status == "HEALTHY":
        icon = "✅"
        title = "Operations Reliability Recovery"
        message_line = (
            "The service has recovered and is healthy again."
        )
    else:
        icon = "🚨"
        title = "Operations Reliability Alert"
        message_line = "Please investigate the service."

    extra = ""
    if investigation is not None:
        extra = (
            f"\n*Investigation:* #{investigation.id}\n"
            f"*Likely cause:* {investigation.likely_cause}\n"
            f"*Confidence:* {investigation.confidence}\n"
            f"*Recommended action:* {investigation.recommended_action}\n"
            f"*Approval required:* {investigation.approval_required}\n"
            f"*Approval status:* {investigation.approval_status}\n"
        )

    message = {
        "text": (
            f"{icon} *{title}*\n\n"
            f"*Incident:* #{incident.id}\n"
            f"*Service:* {incident.service_name}\n"
            f"*Status:* {incident.status}\n"
            f"*Severity:* {incident.severity}\n\n"
            f"*Request Rate:* {incident.request_rate} req/s\n"
            f"*5xx Error Rate:* {incident.error_rate}%\n"
            f"*P95 Latency:* {incident.p95_latency_seconds}s\n\n"
            f"*Reason:*\n"
            f"{incident.reason}\n"
            f"{extra}\n"
            f"{message_line}"
        )
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json=message,
            )

        if response.status_code != 200:
            print(
                f"[ALERT][SLACK] Failed: "
                f"{response.status_code} - {response.text}"
            )
            return

        print(
            f"[ALERT][SLACK] Sent for Incident #{incident.id}"
        )

    except httpx.RequestError as exc:
        print(
            f"[ALERT][SLACK] Request failed for Incident "
            f"#{incident.id}: {exc}"
        )


async def handle_incident_alert(incident: Incident, investigation=None):
    """
    Handle external alerts for reliability incidents
    and recovery events.

    The scheduler already determines whether the state changed.
    Therefore, this function should send the alert for whichever
    incident state it receives, including HEALTHY recovery events.
    """

    print(
        f"[ALERT][{incident.severity}] "
        f"Incident #{incident.id} - "
        f"{incident.service_name} is {incident.status}"
    )

    await send_email_alert(incident)
    await send_slack_alert(incident, investigation=investigation)
