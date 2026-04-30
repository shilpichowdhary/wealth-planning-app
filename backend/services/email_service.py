"""SMTP delivery of transactional emails (advisor access notifications).

Advisors authenticate via Microsoft Entra SSO ("Sign in with LC Account"), so
these emails contain no password-set magic link — they just direct the
advisor to the login page. The url passed in is the public app login URL.

Synchronous smtplib calls are wrapped in asyncio.to_thread so the FastAPI
event loop is never blocked. Failures are caught and logged — callers always
receive a (sent: bool, error: str | None) tuple so the admin UI can surface a
delivery problem without the request itself failing.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from backend.config import settings

logger = logging.getLogger(__name__)


def _build_message(*, to_email: str, name: str, login_url: str,
                   kind: str) -> EmailMessage:
    first_name = (name.split(" ")[0] if name else "there")

    if kind == "reset":
        subject = "Lighthouse Canton — Wealth Planning console access"
        body = (
            f"Hi {first_name},\n\n"
            f"Your access to the Lighthouse Canton Wealth Planning console "
            f"has been refreshed.\n\n"
            f"Sign in with your LC Account (single sign-on) here:\n{login_url}\n\n"
            f"Use the \"Sign in with LC Account\" button — there is no separate "
            f"password to remember. Your login email is {to_email}.\n\n"
            f"If you weren't expecting this, please notify your administrator.\n\n"
            f"Internal use only — please do not forward."
        )
    else:
        subject = "Lighthouse Canton — Wealth Planning console access"
        body = (
            f"Hi {first_name},\n\n"
            f"You've been added to the Lighthouse Canton Wealth Planning console.\n\n"
            f"Sign in with your LC Account (single sign-on) here:\n{login_url}\n\n"
            f"Use the \"Sign in with LC Account\" button — there is no separate "
            f"password to set up. Your login email is {to_email}.\n\n"
            f"Internal use only — please do not forward."
        )

    msg = EmailMessage()
    from_addr = settings.smtp_from or settings.smtp_user
    msg["From"] = formataddr((settings.smtp_from_name, from_addr))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def _send_blocking(msg: EmailMessage) -> None:
    """Open SMTP, STARTTLS, login, send. Raises on any failure."""
    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


async def send_invite_email(
    *, to_email: str, name: str, login_url: str,
    kind: str = "invite",
) -> tuple[bool, str | None]:
    """Email the advisor a sign-in notification. Never raises — returns (sent, error).

    kind: "invite" for new advisors, "reset" for re-sends/access refreshes.
    """
    if not is_configured():
        return False, "SMTP not configured"
    msg = _build_message(
        to_email=to_email, name=name, login_url=login_url, kind=kind,
    )
    try:
        await asyncio.to_thread(_send_blocking, msg)
        logger.info("Sent %s access email to %s", kind, to_email)
        return True, None
    except Exception as e:  # noqa: BLE001 — we want any SMTP failure surfaced
        logger.exception("SMTP send failed for %s: %s", to_email, e)
        return False, str(e)
