from email.message import EmailMessage
import smtplib

from app.config import settings


class MailNotConfigured(Exception):
    pass


class MailSendError(Exception):
    pass


def send_process_down_mail(*, ip_address: str, process_name: str, recipients: list[str], down_since: str) -> None:
    if not settings.smtp_host.strip() or not settings.smtp_from.strip():
        raise MailNotConfigured("SMTP is not configured")
    if not recipients:
        raise MailSendError("No recipients")

    message = EmailMessage()
    message["Subject"] = f"Process down: {process_name} on {ip_address}"
    message["From"] = settings.smtp_from.strip()
    message["To"] = ", ".join(recipients)
    message.set_content(
        "\n".join(
            [
                f"Process {process_name} is not running on {ip_address}.",
                f"Down since {down_since}.",
                "This mail repeats until the process is running again.",
            ]
        )
    )
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
