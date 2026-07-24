"""Notification channel dispatchers — SDD §12.10 decisión 3.1/7.

Default (zero marginal cost): Slack, Telegram, Email (SMTP).
Opt-in (explicit Meta cost): WhatsApp via Meta Cloud API directly (no BSP).

Each dispatch() returns (success: bool, meta_cost_usd: float | None).
The meta_cost_usd is non-None only for WhatsApp — it is read from the channel's
whatsapp_cost_per_conversation_usd config column and stored in action_log.meta_cost_usd
so it appears as an explicit line item in client invoicing.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any, Dict, Optional, Tuple

import httpx

log = logging.getLogger(__name__)


def _send_slack(config: Dict[str, Any], message: str) -> Tuple[bool, None]:
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return False, None
    try:
        resp = httpx.post(webhook_url, json={"text": message}, timeout=10.0)
        resp.raise_for_status()
        return True, None
    except Exception as exc:
        log.warning("Slack dispatch failed: %s", exc)
        return False, None


def _send_telegram(config: Dict[str, Any], message: str) -> Tuple[bool, None]:
    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")
    if not bot_token or not chat_id:
        return False, None
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = httpx.post(url, json={"chat_id": chat_id, "text": message}, timeout=10.0)
        resp.raise_for_status()
        return True, None
    except Exception as exc:
        log.warning("Telegram dispatch failed: %s", exc)
        return False, None


def _send_email(config: Dict[str, Any], message: str, subject: str) -> Tuple[bool, None]:
    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_password = config.get("smtp_password", "")
    from_addr = config.get("from_address", smtp_user)
    to_addrs = config.get("to_addresses", [])
    if not smtp_host or not to_addrs:
        return False, None
    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, to_addrs, msg.as_string())
        return True, None
    except Exception as exc:
        log.warning("Email dispatch failed: %s", exc)
        return False, None


def _send_whatsapp(
    config: Dict[str, Any],
    message: str,
    cost_per_conversation: Optional[float],
) -> Tuple[bool, Optional[float]]:
    """WhatsApp via Meta Cloud API — opt-in, explicit cost pass-through.

    The cost_per_conversation (from action_channels.whatsapp_cost_per_conversation_usd)
    is returned as-is so the caller can store it in action_log.meta_cost_usd.
    It is never absorbed — it must appear on the client's invoice.
    """
    access_token = config.get("access_token", "")
    phone_number_id = config.get("phone_number_id", "")
    to_phone = config.get("to_phone", "")
    if not access_token or not phone_number_id or not to_phone:
        return False, None
    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json=payload,
            timeout=15.0,
        )
        resp.raise_for_status()
        return True, cost_per_conversation
    except Exception as exc:
        log.warning("WhatsApp dispatch failed: %s", exc)
        return False, None


def dispatch(
    channel_type: str,
    config: Dict[str, Any],
    message: str,
    subject: str = "Traxia Action Alert",
    whatsapp_cost_per_conversation: Optional[float] = None,
) -> Tuple[bool, Optional[float]]:
    """Dispatch a notification to one channel. Returns (success, meta_cost_usd)."""
    if channel_type == "slack":
        return _send_slack(config, message)
    if channel_type == "telegram":
        return _send_telegram(config, message)
    if channel_type == "email":
        return _send_email(config, message, subject)
    if channel_type == "whatsapp":
        return _send_whatsapp(config, message, whatsapp_cost_per_conversation)
    log.error("Unknown channel_type: %s", channel_type)
    return False, None
