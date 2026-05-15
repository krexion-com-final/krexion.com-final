"""
Krexion — Email Service
=======================
Thin Resend wrapper used by the Crypto Payment + License modules.

Usage from server.py:
    from email_service import send_email, send_license_email, send_rejection_email

All sends are non-blocking (run sync Resend SDK in a thread).
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Optional

import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "Krexion <onboarding@resend.dev>").strip()
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@krexion.com").strip()
DOMAIN = os.environ.get("KREXION_DOMAIN", "krexion.com").strip()

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY
    logger.info("Resend email service enabled.")
else:
    logger.warning("RESEND_API_KEY not set — emails will be skipped.")


def _enabled() -> bool:
    return bool(RESEND_API_KEY)


async def send_email(
    to: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> dict:
    """
    Send an email via Resend. Returns {"ok": bool, "id"|"error": ...}
    Never raises — logs and returns ok=False so callers can ignore failures.
    """
    if not _enabled():
        logger.info(f"[email skipped — no API key] to={to} subject={subject!r}")
        return {"ok": False, "error": "RESEND_API_KEY not configured"}

    params = {
        "from": SENDER_EMAIL,
        "to": [to],
        "subject": subject,
        "text": body,
    }
    if html:
        params["html"] = html

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        email_id = result.get("id") if isinstance(result, dict) else None
        logger.info(f"[email sent] id={email_id} to={to} subject={subject!r}")
        return {"ok": True, "id": email_id}
    except Exception as e:  # noqa: BLE001
        logger.error(f"[email failed] to={to} subject={subject!r} error={e}")
        return {"ok": False, "error": str(e)}


# ─── HTML template helpers ────────────────────────────────────────────
def _wrap_html(title: str, inner_html: str, cta_url: Optional[str] = None, cta_label: Optional[str] = None) -> str:
    cta_block = ""
    if cta_url and cta_label:
        cta_block = f"""
        <tr><td align="center" style="padding:24px 0 8px 0;">
          <a href="{cta_url}" style="background:#A78BFA;color:#0a0a0f;font-weight:700;
             text-decoration:none;padding:14px 28px;border-radius:8px;
             font-family:Arial,sans-serif;font-size:14px;display:inline-block;">
            {cta_label}
          </a>
        </td></tr>"""

    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#0a0a0f;font-family:Arial,Helvetica,sans-serif;color:#E4E4E7;">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#0a0a0f;">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" cellpadding="0" cellspacing="0" width="600" style="max-width:600px;background:#0f0a18;border:1px solid rgba(255,255,255,0.08);border-radius:14px;overflow:hidden;">
        <tr><td style="padding:24px 28px;border-bottom:1px solid rgba(255,255,255,0.06);">
          <table role="presentation" width="100%"><tr>
            <td style="font-size:20px;font-weight:800;letter-spacing:0.5px;color:#ffffff;">KREXION</td>
            <td align="right" style="font-size:11px;color:#71717A;text-transform:uppercase;letter-spacing:1px;">Traffic that converts</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:32px 28px 8px 28px;">
          <h1 style="margin:0 0 16px 0;font-size:22px;font-weight:700;color:#ffffff;">{title}</h1>
        </td></tr>
        <tr><td style="padding:0 28px 8px 28px;font-size:14px;line-height:1.6;color:#D4D4D8;">
          {inner_html}
        </td></tr>
        {cta_block}
        <tr><td style="padding:28px 28px 24px 28px;border-top:1px solid rgba(255,255,255,0.06);font-size:12px;color:#71717A;">
          Questions? Reply to this email or contact <a href="mailto:{SUPPORT_EMAIL}" style="color:#A78BFA;text-decoration:none;">{SUPPORT_EMAIL}</a>.<br/>
          © {DOMAIN} — All rights reserved.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


# ─── Specific transactional emails ────────────────────────────────────
async def send_license_email(
    customer_email: str,
    customer_name: str,
    plan_name: str,
    license_key: str,
    duration_days: int,
    order_id: str,
) -> dict:
    subject = f"Your Krexion License is Ready — {plan_name}"
    inner = f"""
      <p>Hi {customer_name},</p>
      <p>Thanks for your purchase! Your payment has been verified and your license is now active.</p>
      <table cellpadding="0" cellspacing="0" width="100%" style="margin:18px 0;background:#0a0a0f;border:1px solid rgba(167,139,250,0.3);border-radius:10px;">
        <tr><td style="padding:18px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#71717A;margin-bottom:6px;">Your License Key</div>
          <div style="font-family:Consolas,Menlo,monospace;font-size:18px;font-weight:700;color:#A78BFA;word-break:break-all;">{license_key}</div>
        </td></tr>
      </table>
      <table cellpadding="0" cellspacing="0" width="100%" style="margin:10px 0;font-size:13px;color:#A1A1AA;">
        <tr><td style="padding:4px 0;width:140px;">Plan:</td><td style="color:#ffffff;font-weight:600;">{plan_name}</td></tr>
        <tr><td style="padding:4px 0;">Duration:</td><td style="color:#ffffff;">{duration_days} day(s)</td></tr>
        <tr><td style="padding:4px 0;">Order ID:</td><td style="color:#ffffff;font-family:monospace;">{order_id}</td></tr>
      </table>
      <p style="margin-top:18px;">Download Krexion and enter your license key when prompted during setup.</p>
    """
    body = (
        f"Hi {customer_name},\n\n"
        f"Your Krexion license is ready.\n\n"
        f"License Key: {license_key}\n"
        f"Plan: {plan_name}\n"
        f"Duration: {duration_days} day(s)\n"
        f"Order ID: {order_id}\n\n"
        f"Download: https://{DOMAIN}/download\n\n"
        f"Need help? Reply to this email.\n— Krexion Team"
    )
    html = _wrap_html(
        title="License Issued",
        inner_html=inner,
        cta_url=f"https://{DOMAIN}/download",
        cta_label="Download Krexion",
    )
    return await send_email(customer_email, subject, body, html=html)


async def send_rejection_email(
    customer_email: str,
    customer_name: str,
    order_id: str,
    reason: str,
) -> dict:
    subject = "Your Krexion Order Was Rejected"
    inner = f"""
      <p>Hi {customer_name},</p>
      <p>We were unable to verify your payment for order <code style="background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">{order_id}</code>.</p>
      <table cellpadding="0" cellspacing="0" width="100%" style="margin:14px 0;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.3);border-radius:10px;">
        <tr><td style="padding:14px 16px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:2px;color:#EF4444;margin-bottom:6px;">Reason</div>
          <div style="font-size:14px;color:#ffffff;">{reason}</div>
        </td></tr>
      </table>
      <p>If you believe this is a mistake, please reply to this email with your transaction ID (TxID) and we'll review it personally.</p>
    """
    body = (
        f"Hi {customer_name},\n\n"
        f"Your order {order_id} was rejected.\n\n"
        f"Reason: {reason}\n\n"
        f"Reply with your TxID if you'd like us to review.\n— Krexion Team"
    )
    html = _wrap_html(
        title="Order Rejected",
        inner_html=inner,
        cta_url=f"mailto:{SUPPORT_EMAIL}",
        cta_label="Contact Support",
    )
    return await send_email(customer_email, subject, body, html=html)


async def send_welcome_email(customer_email: str, customer_name: str, order_id: str, plan_name: str) -> dict:
    subject = "We've received your Krexion order"
    inner = f"""
      <p>Hi {customer_name},</p>
      <p>Thanks for choosing Krexion — your order is in the system.</p>
      <table cellpadding="0" cellspacing="0" width="100%" style="margin:14px 0;font-size:13px;color:#A1A1AA;">
        <tr><td style="padding:4px 0;width:140px;">Plan:</td><td style="color:#ffffff;font-weight:600;">{plan_name}</td></tr>
        <tr><td style="padding:4px 0;">Order ID:</td><td style="color:#ffffff;font-family:monospace;">{order_id}</td></tr>
      </table>
      <p>Once your payment is confirmed on-chain, we'll email your license key (usually within 30 minutes).</p>
    """
    body = (
        f"Hi {customer_name},\n\nThanks for your order {order_id} ({plan_name}).\n"
        f"We'll email your license key once payment is confirmed.\n\n— Krexion Team"
    )
    html = _wrap_html(
        title="Order Received",
        inner_html=inner,
        cta_url=f"https://{DOMAIN}/order/{order_id}",
        cta_label="Track Your Order",
    )
    return await send_email(customer_email, subject, body, html=html)
