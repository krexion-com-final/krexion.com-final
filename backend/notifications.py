"""
notifications.py
────────────────
Lightweight email helper + low-stock alert trigger for gsheet uploads.

Why a separate module:
    server.py is already 11k+ lines and the existing email-sending logic
    is buried inside `send_password_reset_email`. Pulling out a generic
    `send_alert_email()` here avoids further bloating server.py and lets
    `real_user_traffic.py` import the alert checker directly.

What's here:
    • send_alert_email(to_email, subject, html, plain=None) — three-tier
      fallback (Gmail SMTP → Resend → log only). Mirrors the pattern used
      for password resets.
    • maybe_send_low_stock_alert(...) — checks an upload's
      remaining/original ratio after each consume and fires off a
      notification email when the threshold is crossed for the first
      time. Idempotent (won't re-spam) and auto-resets when the sheet is
      refilled.

Configuration is read from env vars on demand so a missing config doesn't
crash anything — alerts gracefully degrade to log lines.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Threshold: send the alert when the live sheet has fewer than this fraction
# of its original-rows remaining. 0.10 == "only 10% left, refill soon".
LOW_STOCK_THRESHOLD = float(os.environ.get("LOW_STOCK_THRESHOLD", "0.10"))


# ──────────────────────── Generic email helper ──────────────────────────

async def send_alert_email(
    to_email: str,
    subject: str,
    html: str,
    plain: Optional[str] = None,
    db=None,
) -> Dict[str, Any]:
    """Send a transactional email. Tries Gmail SMTP first, then Resend,
    then logs (when no provider configured). Always returns a status
    dict, never raises — callers can fire and forget.

    Config resolution order:
      1. `admin_settings.email_config` doc in MongoDB (admin-managed)
      2. Env vars (legacy)
    Pass `db` to enable the DB lookup; omit for env-only behaviour."""
    if not to_email or "@" not in to_email:
        return {"status": "skipped", "reason": "invalid recipient"}

    # ── Pull admin-managed config first; env vars only used as fallback
    cfg: Dict[str, Any] = {}
    if db is not None:
        cfg = await get_email_config(db)

    def _pick(key: str, env_key: Optional[str] = None) -> str:
        v = (cfg.get(key) or "").strip() if isinstance(cfg.get(key), str) else cfg.get(key) or ""
        if v:
            return v
        return (os.environ.get(env_key or key.upper()) or "").strip()

    smtp_host = _pick("smtp_host", "SMTP_HOST")
    smtp_user = _pick("smtp_user", "SMTP_USER")
    smtp_password = _pick("smtp_password", "SMTP_PASSWORD")
    try:
        smtp_port_raw = cfg.get("smtp_port") or os.environ.get("SMTP_PORT") or "587"
        smtp_port = int(smtp_port_raw)
    except (ValueError, TypeError):
        smtp_port = 587
    resend_key = _pick("resend_api_key", "RESEND_API_KEY")
    resend_from = _pick("resend_from", "RESEND_FROM") or _pick("sender_email", "SENDER_EMAIL")
    sender_name = _pick("sender_name", "APP_NAME") or "RealFlow"
    sender_email = (
        cfg.get("sender_email")
        or smtp_user
        or resend_from
        or os.environ.get("SENDER_EMAIL")
        or ""
    )

    # ── Try Gmail / generic SMTP first ────────────────────────────────
    if smtp_host and smtp_user and smtp_password:
        try:
            def _send_smtp():
                import smtplib
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{sender_name} <{smtp_user}>"
                msg["To"] = to_email
                if plain:
                    msg.attach(MIMEText(plain, "plain"))
                msg.attach(MIMEText(html, "html"))
                with smtplib.SMTP(smtp_host, smtp_port) as srv:
                    srv.starttls()
                    srv.login(smtp_user, smtp_password)
                    srv.sendmail(smtp_user, to_email, msg.as_string())
                return True

            await asyncio.to_thread(_send_smtp)
            logger.info(f"[notify] alert email sent via SMTP to {to_email}")
            return {"status": "sent", "provider": "smtp"}
        except Exception as e:
            logger.warning(f"[notify] SMTP send failed for {to_email}: {e}")

    # ── Fallback: Resend ─────────────────────────────────────────────
    if resend_key:
        try:
            import resend  # type: ignore
            resend.api_key = resend_key
            params = {
                "from": resend_from or sender_email,
                "to": [to_email],
                "subject": subject,
                "html": html,
            }
            resp = await asyncio.to_thread(resend.Emails.send, params)
            logger.info(f"[notify] alert email sent via Resend to {to_email}, id={resp.get('id') if isinstance(resp, dict) else '?'}")
            return {"status": "sent", "provider": "resend"}
        except Exception as e:
            logger.warning(f"[notify] Resend send failed for {to_email}: {e}")

    # ── Last resort: log only ────────────────────────────────────────
    logger.info(f"[notify-LOG] would email {to_email!r}: {subject}")
    return {"status": "logged", "reason": "no email provider configured"}


# ──────────────────── Low-stock alert trigger ──────────────────────────

def _build_low_stock_html(
    *,
    app_name: str,
    upload_name: str,
    upload_type: str,
    remaining: int,
    consumed: int,
    total: int,
    sheet_url: str,
) -> str:
    """Self-contained inline-styled HTML so the email looks good without a
    template engine. Matches the existing brand palette (zinc / blue)."""
    pct_remaining = (remaining / total * 100) if total > 0 else 0
    pct_used = 100 - pct_remaining
    return f"""
    <!DOCTYPE html>
    <html><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#09090B;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#09090B;padding:32px 16px;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#18181B;border:1px solid #27272A;border-radius:12px;">
            <tr><td style="padding:32px 28px 12px 28px;">
              <h1 style="color:#F59E0B;margin:0 0 4px 0;font-size:20px;">⚠ Low-Stock Alert</h1>
              <p style="color:#A1A1AA;margin:0;font-size:13px;">{app_name} · live Google Sheet upload running low</p>
            </td></tr>
            <tr><td style="padding:0 28px 8px 28px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#0F0F11;border:1px solid #27272A;border-radius:8px;">
                <tr><td style="padding:18px 20px;">
                  <p style="color:#71717A;margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Upload</p>
                  <p style="color:#FAFAFA;margin:0 0 14px 0;font-size:16px;font-weight:600;">{upload_name}
                    <span style="color:#A1A1AA;font-weight:400;font-size:13px;"> · {upload_type}</span></p>
                  <p style="color:#71717A;margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Rows remaining</p>
                  <p style="margin:0;color:#F59E0B;font-size:28px;font-weight:700;">{remaining:,}
                    <span style="color:#A1A1AA;font-size:14px;font-weight:400;"> / {total:,} ({pct_remaining:.1f}%)</span></p>
                  <p style="color:#71717A;margin:14px 0 4px 0;font-size:11px;">{consumed:,} rows consumed ({pct_used:.1f}%)</p>
                </td></tr>
              </table>
            </td></tr>
            <tr><td style="padding:8px 28px 24px 28px;">
              <p style="color:#D4D4D8;margin:14px 0 18px 0;font-size:14px;line-height:1.6;">
                Aapki live Google-Sheet upload mein sirf <strong style="color:#F59E0B;">{remaining:,} rows</strong> bachi hain.
                Bot ka kaam ruk-ruk ke chal sakta hai jab tak aap sheet mein naye rows na add kar den.
                Sheet kholne ke liye yeh button click karen:
              </p>
              <table cellpadding="0" cellspacing="0">
                <tr><td style="border-radius:8px;background:#3B82F6;">
                  <a href="{sheet_url}" target="_blank" style="display:inline-block;padding:12px 24px;color:#FFF;text-decoration:none;font-weight:600;font-size:14px;">
                    Open Sheet & Refill →
                  </a>
                </td></tr>
              </table>
              <p style="color:#52525B;margin:24px 0 0 0;font-size:11px;line-height:1.6;">
                You're receiving this because low-stock alerts are enabled for this account.
                Disable in Settings → Notifications. Threshold: ≤ {LOW_STOCK_THRESHOLD * 100:.0f}% rows remaining.
              </p>
            </td></tr>
            <tr><td style="padding:16px 28px;border-top:1px solid #27272A;text-align:center;">
              <p style="color:#52525B;margin:0;font-size:11px;">© {datetime.now(timezone.utc).year} {app_name}</p>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body></html>
    """


async def maybe_send_low_stock_alert(
    *,
    user_db,
    user_id: str,
    upload_doc: Dict[str, Any],
    notification_email: Optional[str],
    primary_email: Optional[str],
    alerts_enabled: bool,
    app_name: str = "RealFlow",
) -> bool:
    """Check the upload's row counters and send a low-stock alert if the
    sheet has crossed the threshold for the first time. Returns True when
    an alert was actually dispatched.

    `upload_doc` should be the freshest doc available (we re-read the
    counters here just to be safe and we update `low_alert_sent_at`
    atomically to prevent re-firing).

    Caller is responsible for passing notification_email/primary_email
    (we don't query the user collection here to keep this function
    decoupled from the user DB layout).
    """
    if not alerts_enabled:
        return False
    if (upload_doc.get("gsheet_url") or "") == "":
        return False  # only gsheet uploads support live re-fills

    # Re-fetch the current counters so we don't act on a stale snapshot.
    fresh = await user_db["uploaded_resources"].find_one(
        {"id": upload_doc["id"], "user_id": user_id},
        {"_id": 0, "id": 1, "item_count": 1, "consumed_count": 1,
         "original_item_count": 1, "low_alert_sent_at": 1,
         "name": 1, "type": 1, "gsheet_url": 1, "consumed_keys": 1},
    )
    if not fresh:
        return False

    item_count = int(fresh.get("item_count") or 0)
    consumed_keys = fresh.get("consumed_keys") or []
    consumed_count = int(fresh.get("consumed_count") or len(consumed_keys))
    original = int(fresh.get("original_item_count") or 0)
    if original <= 0:
        return False

    # `available` = rows still pickable. For gsheet, item_count tracks the
    # live sheet size (drops as rows are physically deleted).
    available = max(0, item_count - max(0, consumed_count - (original - item_count)))
    # ↑ guard for double-counting when both physical-delete AND consumed_keys
    # tracking happen (the live delete path already shrinks item_count).
    available = item_count if consumed_keys else item_count

    ratio = available / original if original > 0 else 0
    if ratio > LOW_STOCK_THRESHOLD:
        return False

    # Already alerted? Don't re-spam.
    if fresh.get("low_alert_sent_at"):
        return False

    target = (notification_email or primary_email or "").strip()
    if not target:
        logger.info(f"[notify] low-stock threshold hit for upload {fresh.get('id')} but no email on file")
        # Still mark as sent so we don't loop on the check
        await user_db["uploaded_resources"].update_one(
            {"id": fresh["id"], "user_id": user_id},
            {"$set": {"low_alert_sent_at": datetime.now(timezone.utc).isoformat()}},
        )
        return False

    html = _build_low_stock_html(
        app_name=app_name,
        upload_name=fresh.get("name") or "Untitled upload",
        upload_type=fresh.get("type") or "data_file",
        remaining=available,
        consumed=consumed_count,
        total=original,
        sheet_url=fresh.get("gsheet_url") or "",
    )
    subject = f"⚠ Low-stock: {fresh.get('name') or 'upload'} ({available} of {original} rows left)"

    # Mark as sent BEFORE we hit the SMTP/Resend network so a slow
    # external API can't trigger duplicate emails from concurrent jobs.
    await user_db["uploaded_resources"].update_one(
        {"id": fresh["id"], "user_id": user_id},
        {"$set": {"low_alert_sent_at": datetime.now(timezone.utc).isoformat()}},
    )

    try:
        await send_alert_email(target, subject, html, db=user_db.client["realflow"] if user_db is not None else None)
    except Exception as e:
        logger.warning(f"[notify] low-stock send_alert_email failed: {e}")
        return False
    return True


def reset_low_alert_if_refilled(*, prev_item_count: int, new_item_count: int) -> bool:
    """Decision helper for `_refresh_gsheet_doc`: should we clear the
    `low_alert_sent_at` flag? We clear it the moment the live sheet has
    grown by at least 1 row vs the previous snapshot — that's the cleanest
    signal that the user has refilled and a future depletion should
    re-fire the alert."""
    return new_item_count > prev_item_count


__all__ = [
    "LOW_STOCK_THRESHOLD",
    "send_alert_email",
    "maybe_send_low_stock_alert",
    "reset_low_alert_if_refilled",
    "get_email_config",
    "save_email_config",
    "EMAIL_CONFIG_DOC_ID",
]


# ──────────────────── Admin-managed email config ────────────────────────
#
# The single source of truth for SMTP/Resend creds is a Mongo doc in the
# main `realflow` DB (collection `admin_settings`, doc id `email_config`).
# This keeps the config out of `.env` files (and out of git) and lets one
# admin configure email-sending for ALL users with a single form in the
# admin panel.
#
# `send_alert_email` reads this doc on every call (cheap — one find_one
# against an indexed _id), so admin changes take effect instantly without
# a server restart. Falls back to env vars when the doc is missing so the
# old env-based setup still works during transition.

EMAIL_CONFIG_DOC_ID = "email_config"


async def get_email_config(db) -> Dict[str, Any]:
    """Load the singleton email-config doc from `admin_settings`. Returns
    {} when the doc doesn't exist yet (first-time setup)."""
    if db is None:
        return {}
    try:
        doc = await db["admin_settings"].find_one({"_id": EMAIL_CONFIG_DOC_ID}, {"_id": 0})
        return doc or {}
    except Exception as e:
        logger.warning(f"[notify] failed to read email config from DB: {e}")
        return {}


async def save_email_config(db, config: Dict[str, Any]) -> None:
    """Upsert the singleton email-config doc. Caller is responsible for
    sanitising / validating fields before passing them in."""
    if db is None:
        return
    config = dict(config)  # don't mutate caller's dict
    config["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db["admin_settings"].update_one(
        {"_id": EMAIL_CONFIG_DOC_ID},
        {"$set": config},
        upsert=True,
    )
