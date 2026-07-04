"""Transactional email via the Resend HTTP API (one httpx POST, no SDK).

Falls back to logging the link when RESEND_API_KEY is unset (development).
"""

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger()

RESEND_API = "https://api.resend.com/emails"
FROM_ADDRESS = "Cryo <onboarding@resend.dev>"


async def send_magic_link(email: str, link: str) -> bool:
    """Email a sign-in link. Returns True when the email was accepted.

    Without an API key (dev), the link is logged instead and True is returned.
    """
    if not settings.resend_api_key:
        logger.info("cryo.email.dev_mode_link", email=email, link=link)
        return True
    payload = {
        "from": FROM_ADDRESS,
        "to": [email],
        "subject": "Your Cryo sign-in link",
        "html": (
            f'<p>Click to sign in to Cryo:</p><p><a href="{link}">{link}</a></p>'
            "<p>This link expires in 15 minutes. If you didn't request it, ignore this email.</p>"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                RESEND_API,
                json=payload,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            )
            resp.raise_for_status()
        logger.info("cryo.email.sent", email=email)
        return True
    except Exception as exc:
        logger.error("cryo.email.send_failed", email=email, error=str(exc))
        return False
