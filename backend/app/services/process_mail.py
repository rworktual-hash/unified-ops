from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib
from zoneinfo import ZoneInfo

from app.config import settings

IST = ZoneInfo("Asia/Kolkata")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class MailNotConfigured(Exception):
    pass


class MailSendError(Exception):
    pass


def format_detected_at(down_since: str) -> str:
    text = down_since.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    local = parsed.astimezone(IST)
    month = _MONTHS[local.month - 1]
    return f"{local.day:02d}-{month}-{local.year} {local:%H:%M:%S} IST"


def process_down_body(*, ip_address: str, process_name: str, down_since: str) -> str:
    detected = format_detected_at(down_since)
    return "\n".join(
        [
            "Hello Team,",
            "",
            "The following service is currently not running.",
            "",
            f"Service: {process_name}",
            f"Server IP: {ip_address}",
            "Status: DOWN",
            f"Detected At: {detected}",
            "",
            "The monitoring system will continue sending alerts until the service is restored.",
            "",
            "Please check and take the necessary action.",
            "",
            "Regards,",
            "Worktual Monitoring System",
            "",
            "This is an automated notification. Please do not reply.",
        ]
    )


def process_up_body(*, ip_address: str, process_name: str, restored_at: str) -> str:
    restored = format_detected_at(restored_at)
    return "\n".join(
        [
            "Hello Team,",
            "",
            "The following service is running again.",
            "",
            f"Service: {process_name}",
            f"Server IP: {ip_address}",
            "Status: UP",
            f"Restored At: {restored}",
            "",
            "No further alerts will be sent until the service goes down again.",
            "",
            "Regards,",
            "Worktual Monitoring System",
            "",
            "This is an automated notification. Please do not reply.",
        ]
    )


def _deliver(message: EmailMessage) -> None:
    if not settings.smtp_host.strip() or not settings.smtp_from.strip():
        raise MailNotConfigured("SMTP is not configured")
    try:
        with smtplib.SMTP(settings.smtp_host.strip(), settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_username.strip():
                smtp.login(settings.smtp_username.strip(), settings.smtp_password)
            smtp.send_message(message)
    except MailNotConfigured:
        raise
    except Exception as exc:
        raise MailSendError(str(exc) or "SMTP send failed") from exc


def send_process_down_mail(*, ip_address: str, process_name: str, recipients: list[str], down_since: str) -> None:
    if not recipients:
        raise MailSendError("No recipients")
    message = EmailMessage()
    message["Subject"] = f"Process down: {process_name} on {ip_address}"
    message["From"] = settings.smtp_from.strip()
    message["To"] = ", ".join(recipients)
    message.set_content(process_down_body(ip_address=ip_address, process_name=process_name, down_since=down_since))
    _deliver(message)


def send_process_up_mail(*, ip_address: str, process_name: str, recipients: list[str], restored_at: str) -> None:
    if not recipients:
        raise MailSendError("No recipients")
    message = EmailMessage()
    message["Subject"] = f"Process up: {process_name} on {ip_address}"
    message["From"] = settings.smtp_from.strip()
    message["To"] = ", ".join(recipients)
    message.set_content(process_up_body(ip_address=ip_address, process_name=process_name, restored_at=restored_at))
    _deliver(message)
