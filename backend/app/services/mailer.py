import asyncio
import smtplib
from email.message import EmailMessage

from app.config import settings


class MailNotConfigured(Exception):
    """Faltan los datos SMTP."""


class MailError(Exception):
    """El servidor de correo rechazó el envío."""


def mail_is_configured() -> bool:
    return bool((settings.smtp_host or "").strip())


def _send_sync(to: str, subject: str, body: str) -> None:
    host = (settings.smtp_host or "").strip()
    sender = (settings.smtp_from or settings.smtp_user or "").strip()
    if not host or not sender:
        raise MailNotConfigured("Falta SMTP_HOST y SMTP_FROM en el .env del backend")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            user = (settings.smtp_user or "").strip()
            if user:
                smtp.login(user, settings.smtp_password or "")
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise MailError("No se pudo enviar el mail") from exc


async def send_email(to: str, subject: str, body: str) -> None:
    if not mail_is_configured():
        raise MailNotConfigured("Falta SMTP_HOST en el .env del backend")
    await asyncio.to_thread(_send_sync, to, subject, body)
