"""
Krexion — License & Subscription Module
========================================

A self-contained FastAPI router that handles:

* Public license endpoints (called by the desktop installer + the
  locally-running app on each customer's PC):
    GET  /api/license/config             — current pricing / trial / rules
    POST /api/license/start-trial        — create a trial license
    POST /api/license/activate           — bind license to a machine
    POST /api/license/validate           — heartbeat / status check
    POST /api/license/checkout           — create Stripe Checkout
    GET  /api/license/status/{sid}       — poll Stripe payment status
    POST /api/webhook/stripe             — Stripe webhook

* Admin endpoints (require existing admin JWT):
    GET  /api/admin/license/config       — view config
    PUT  /api/admin/license/config       — edit pricing/rules globally
    GET  /api/admin/license/list         — list all licenses
    POST /api/admin/license/revoke/{key} — revoke a license
    POST /api/admin/license/extend/{key} — manually extend N days

Storage: three MongoDB collections inside the MAIN database
(not per-user — this is global SaaS state):
    license_config            — single document, the live ruleset
    licenses                  — one row per customer
    payment_transactions      — one row per checkout (Stripe playbook req)
"""

from __future__ import annotations

import os
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Depends, status
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
license_router = APIRouter(prefix="/api", tags=["license"])

# ─── State injected from server.py via _bind() ────────────────────────
_db: Any = None
_get_current_admin: Any = None
_send_email: Any = None  # optional email helper (notifications.py)


def _bind(*, main_db, get_current_admin, send_email=None) -> None:
    """Wire up dependencies. Called once from server.py."""
    global _db, _get_current_admin, _send_email
    _db = main_db
    _get_current_admin = get_current_admin
    _send_email = send_email


# ─── Helpers ──────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _as_aware(dt: Any) -> Optional[datetime]:
    """Normalize a possibly-naive datetime (e.g. from Mongo BSON) to UTC.
    Accepts datetime, ISO string, or None. Returns tz-aware UTC datetime."""
    if not dt:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt if isinstance(dt, datetime) else None


def _gen_license_key() -> str:
    """Format: KRX-XXXX-XXXX-XXXX-XXXX (19 chars + 4 dashes)."""
    raw = uuid.uuid4().hex.upper()[:16]
    return "KRX-" + "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def _default_config() -> Dict[str, Any]:
    return {
        "id": "global",
        "product_name": "Krexion",
        "monthly_price": 29.0,
        "currency": "usd",
        "trial_days": 7,
        "max_pcs_per_license": 1,
        "enabled": True,
        # Manual purchase flow — installer shows these to customers
        # instead of a Stripe checkout button. Aap admin panel se
        # globally edit kar sakte hain.
        "admin_contact_email": "admin@krexion.local",
        "admin_contact_message": (
            "To purchase a license, please email the admin with your name, "
            "company (optional), and preferred payment method (crypto / "
            "bank transfer / etc.). The admin will reply with a license "
            "key once payment is received."
        ),
        "checkout_success_url_suffix": "/license/success",
        "checkout_cancel_url_suffix": "/license/cancel",
        "updated_at": _now().isoformat(),
    }


async def get_config() -> Dict[str, Any]:
    """Read the single config document; seed default if missing.
    Also back-fills any newly-added fields from _default_config() so
    older databases automatically pick up new keys (e.g. admin_contact_*)
    without an explicit migration."""
    defaults = _default_config()
    cfg = await _db.license_config.find_one({"id": "global"}, {"_id": 0})
    if not cfg:
        await _db.license_config.insert_one(defaults.copy())
        return defaults
    # Back-fill any keys missing from older config docs
    missing = {k: v for k, v in defaults.items() if k not in cfg}
    if missing:
        await _db.license_config.update_one({"id": "global"}, {"$set": missing})
        cfg.update(missing)
    return cfg


def _get_machine_label(license_doc: Dict[str, Any]) -> str:
    """Human label for emails / admin UI."""
    mid = license_doc.get("machine_id")
    return mid[:8] + "…" if mid else "(unbound)"


async def _maybe_notify(subject: str, body: str) -> None:
    """Fire-and-forget email to admin if helper is bound."""
    try:
        if _send_email:
            admin_email = os.environ.get("ADMIN_EMAIL") or "admin@krexion.local"
            await _send_email(to=admin_email, subject=subject, body=body)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"License notification email failed: {e}")


def _expired(lic: Dict[str, Any]) -> bool:
    """Return True if the license should be treated as expired right now."""
    now = _now()
    status_ = (lic.get("status") or "").lower()
    if status_ in ("revoked", "expired"):
        return True
    if status_ == "trial":
        ends = _as_aware(lic.get("trial_ends_at"))
        if ends and ends < now:
            return True
    if status_ == "active":
        ends = _as_aware(lic.get("subscription_ends_at"))
        if ends and ends < now:
            return True
    return False


def _public_license(lic: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internals before returning to client."""
    return {
        "license_key": lic.get("license_key"),
        "email": lic.get("email"),
        "status": lic.get("status"),
        "trial_ends_at": _iso(lic.get("trial_ends_at")),
        "subscription_ends_at": _iso(lic.get("subscription_ends_at")),
        "machine_id": lic.get("machine_id"),
        "activated_at": _iso(lic.get("activated_at")),
    }


# ─── Pydantic request models ──────────────────────────────────────────
class StartTrialRequest(BaseModel):
    email: EmailStr
    machine_id: Optional[str] = None


class ActivateRequest(BaseModel):
    license_key: str
    machine_id: str
    machine_label: Optional[str] = None


class ValidateRequest(BaseModel):
    license_key: str
    machine_id: str


class CheckoutRequest(BaseModel):
    license_key: str
    origin_url: str = Field(..., description="Frontend origin, e.g. https://app.example.com")


class ConfigUpdate(BaseModel):
    product_name: Optional[str] = None
    monthly_price: Optional[float] = Field(None, ge=0.5, le=10000.0)
    currency: Optional[str] = Field(None, pattern=r"^[a-z]{3}$")
    trial_days: Optional[int] = Field(None, ge=0, le=365)
    max_pcs_per_license: Optional[int] = Field(None, ge=1, le=1000)
    enabled: Optional[bool] = None
    admin_contact_email: Optional[EmailStr] = None
    admin_contact_message: Optional[str] = Field(None, max_length=2000)


# ═════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS (called by the installer + locally-running app)
# ═════════════════════════════════════════════════════════════════════

@license_router.get("/license/config")
async def license_config_public():
    """Current pricing / trial / rules. Cached client-side by installer."""
    cfg = await get_config()
    return {
        "product_name": cfg["product_name"],
        "monthly_price": cfg["monthly_price"],
        "currency": cfg["currency"],
        "trial_days": cfg["trial_days"],
        "max_pcs_per_license": cfg["max_pcs_per_license"],
        "enabled": cfg["enabled"],
        "admin_contact_email": cfg.get("admin_contact_email", ""),
        "admin_contact_message": cfg.get("admin_contact_message", ""),
    }


@license_router.post("/license/start-trial")
async def start_trial(body: StartTrialRequest):
    cfg = await get_config()
    if not cfg["enabled"]:
        raise HTTPException(403, "Licensing is currently disabled. Please contact the admin.")
    if cfg["trial_days"] <= 0:
        raise HTTPException(400, "Free trial is currently disabled. Please purchase a license.")

    # Prevent multi-trial abuse: one trial per email
    existing = await _db.licenses.find_one({"email": body.email.lower()}, {"_id": 0})
    if existing:
        return {"license_key": existing["license_key"], "reused": True, "message": "Existing license returned."}

    key = _gen_license_key()
    lic = {
        "license_key": key,
        "email": body.email.lower(),
        "status": "trial",
        "trial_ends_at": _now() + timedelta(days=cfg["trial_days"]),
        "subscription_ends_at": None,
        "machine_id": body.machine_id,
        "machine_label": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "activated_at": _now() if body.machine_id else None,
        "created_at": _now(),
        "last_validated_at": _now(),
    }
    await _db.licenses.insert_one(lic.copy())
    await _maybe_notify(
        subject=f"[Krexion] New trial: {body.email}",
        body=f"License key: {key}\nTrial ends: {_iso(lic['trial_ends_at'])}\nMachine: {_get_machine_label(lic)}",
    )
    return {"license_key": key, "reused": False, "trial_ends_at": _iso(lic["trial_ends_at"])}


@license_router.post("/license/activate")
async def activate(body: ActivateRequest):
    cfg = await get_config()
    if not cfg["enabled"]:
        raise HTTPException(403, "Licensing is currently disabled.")

    lic = await _db.licenses.find_one({"license_key": body.license_key}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "License key not found.")
    if lic.get("status") == "revoked":
        raise HTTPException(403, "This license has been revoked.")
    if _expired(lic):
        raise HTTPException(403, f"This license has expired ({lic.get('status')}).")

    # Machine binding — strict 1:1 by default
    bound_id = lic.get("machine_id")
    max_pcs = max(1, int(cfg.get("max_pcs_per_license", 1)))
    if max_pcs == 1:
        if bound_id and bound_id != body.machine_id:
            raise HTTPException(
                409,
                "This license is already activated on a different PC. "
                "Contact the seller to transfer it.",
            )
        update = {"machine_id": body.machine_id}
    else:
        # multi-PC: track in machines[] array, allow up to max_pcs
        machines = lic.get("machines") or []
        if body.machine_id not in machines:
            if len(machines) >= max_pcs:
                raise HTTPException(409, f"License already used on {max_pcs} PCs (the limit).")
            machines.append(body.machine_id)
        update = {"machine_id": body.machine_id, "machines": machines}

    update.update({
        "machine_label": body.machine_label,
        "activated_at": lic.get("activated_at") or _now(),
        "last_validated_at": _now(),
    })
    await _db.licenses.update_one({"license_key": body.license_key}, {"$set": update})
    lic.update(update)

    await _maybe_notify(
        subject=f"[Krexion] License activated: {lic['email']}",
        body=f"Key: {body.license_key}\nMachine: {body.machine_label or body.machine_id[:12]}\nStatus: {lic.get('status')}",
    )
    return {"ok": True, "license": _public_license(lic)}


@license_router.post("/license/validate")
async def validate(body: ValidateRequest):
    """Called by the locally-running Krexion app on startup +
    every N hours. Returns current authoritative status."""
    cfg = await get_config()
    if not cfg["enabled"]:
        return {"ok": True, "status": "active", "reason": "licensing_disabled"}

    lic = await _db.licenses.find_one({"license_key": body.license_key}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "License key not recognized.")

    max_pcs = max(1, int(cfg.get("max_pcs_per_license", 1)))
    if max_pcs == 1:
        bound = lic.get("machine_id")
        if bound and bound != body.machine_id:
            return {"ok": False, "status": "wrong_machine",
                    "reason": "License is bound to a different PC."}
    else:
        machines = lic.get("machines") or ([lic.get("machine_id")] if lic.get("machine_id") else [])
        if body.machine_id not in machines:
            return {"ok": False, "status": "wrong_machine",
                    "reason": "This PC is not registered on the license."}

    if lic.get("status") == "revoked":
        return {"ok": False, "status": "revoked", "reason": "License was revoked."}
    if _expired(lic):
        # mark it expired so admin UI shows it
        await _db.licenses.update_one(
            {"license_key": body.license_key},
            {"$set": {"status": "expired"}},
        )
        return {"ok": False, "status": "expired",
                "reason": "Subscription / trial period has ended.",
                "license": _public_license({**lic, "status": "expired"})}

    await _db.licenses.update_one(
        {"license_key": body.license_key},
        {"$set": {"last_validated_at": _now()}},
    )
    return {"ok": True, "status": lic.get("status"), "license": _public_license(lic)}


@license_router.post("/license/checkout")
async def checkout(body: CheckoutRequest, http_request: Request):
    """DEPRECATED — Stripe payment flow has been removed. Customers now
    contact the admin manually (crypto / bank transfer / etc.) and the
    admin issues a license key from the admin panel. Endpoint kept only
    so older installers don't crash hard; it returns a friendly 410."""
    raise HTTPException(
        status_code=410,
        detail="Online payments are disabled. Please email the admin to purchase a license."
    )


@license_router.get("/license/status/{session_id}")
async def license_status_deprecated(session_id: str):
    """DEPRECATED — see /license/checkout note."""
    raise HTTPException(status_code=410, detail="Online payments are disabled.")


@license_router.post("/webhook/stripe")
async def stripe_webhook_deprecated(request: Request):
    """DEPRECATED — see /license/checkout note. Always 200 so any stale
    Stripe-Dashboard webhook config doesn't loop and retry forever."""
    return {"received": True, "deprecated": True}


# ═════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS  (gated by existing get_current_admin)
# ═════════════════════════════════════════════════════════════════════

def _admin_dep():
    """Lazy resolver — _get_current_admin is set by _bind() at app startup."""
    async def _resolved(request: Request):
        if _get_current_admin is None:
            raise HTTPException(503, "Admin auth not wired yet.")
        return await _get_current_admin(request)
    return Depends(_resolved)


@license_router.get("/admin/license/config")
async def admin_get_config(admin: dict = _admin_dep()):
    return await get_config()


@license_router.put("/admin/license/config")
async def admin_update_config(patch: ConfigUpdate, admin: dict = _admin_dep()):
    cfg = await get_config()
    updates = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return cfg
    updates["updated_at"] = _now().isoformat()
    await _db.license_config.update_one(
        {"id": "global"}, {"$set": updates}, upsert=True,
    )
    return await get_config()


@license_router.get("/admin/license/list")
async def admin_list_licenses(
    skip: int = 0,
    limit: int = 200,
    q: Optional[str] = None,
    admin: dict = _admin_dep(),
):
    filt: Dict[str, Any] = {}
    if q:
        rx = re.escape(q)
        filt = {"$or": [
            {"license_key": {"$regex": rx, "$options": "i"}},
            {"email": {"$regex": rx, "$options": "i"}},
            {"machine_id": {"$regex": rx, "$options": "i"}},
        ]}
    total = await _db.licenses.count_documents(filt)
    rows: List[Dict[str, Any]] = []
    cursor = _db.licenses.find(filt, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    async for r in cursor:
        for k in ("trial_ends_at", "subscription_ends_at", "activated_at",
                  "created_at", "last_validated_at"):
            r[k] = _iso(r.get(k))
        rows.append(r)
    return {"total": total, "items": rows}


@license_router.post("/admin/license/revoke/{key}")
async def admin_revoke(key: str, admin: dict = _admin_dep()):
    r = await _db.licenses.update_one(
        {"license_key": key},
        {"$set": {"status": "revoked", "revoked_at": _now()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "License not found.")
    return {"ok": True}


@license_router.post("/admin/license/extend/{key}")
async def admin_extend(key: str, days: int = 31, admin: dict = _admin_dep()):
    if days < 1 or days > 3650:
        raise HTTPException(400, "days must be between 1 and 3650.")
    lic = await _db.licenses.find_one({"license_key": key}, {"_id": 0})
    if not lic:
        raise HTTPException(404, "License not found.")
    base = _as_aware(lic.get("subscription_ends_at"))
    if not base or base < _now():
        base = _now()
    new_end = base + timedelta(days=days)
    await _db.licenses.update_one(
        {"license_key": key},
        {"$set": {"status": "active", "subscription_ends_at": new_end}},
    )
    return {"ok": True, "subscription_ends_at": _iso(new_end)}


@license_router.delete("/admin/license/{key}")
async def admin_delete_license(key: str, admin: dict = _admin_dep()):
    """Permanently delete a license key from the database.
    Customer's local heartbeat will fail validation next cycle.
    Useful for cleaning up trial keys, revoked keys, mistakes, etc."""
    r = await _db.licenses.delete_one({"license_key": key})
    if r.deleted_count == 0:
        raise HTTPException(404, "License not found.")
    return {"ok": True, "deleted": key}


@license_router.post("/admin/license/bulk-delete")
async def admin_bulk_delete(payload: dict, admin: dict = _admin_dep()):
    """Bulk-delete licenses by filter.
    Body: {
      "status": "revoked" | "trial" | "active" | "expired" | "all",   (optional)
      "keys":   ["RFLW-...", "RFLW-..."],                              (optional, takes priority)
      "expired_only": true|false,                                       (optional)
      "unactivated_only": true|false                                    (optional - never bound to a machine)
    }
    Returns: { "ok": true, "deleted_count": N }
    """
    keys = payload.get("keys")
    status = payload.get("status")
    expired_only = bool(payload.get("expired_only"))
    unactivated_only = bool(payload.get("unactivated_only"))

    if keys and isinstance(keys, list) and len(keys) > 0:
        # Whitelist explicit keys (safest)
        r = await _db.licenses.delete_many({"license_key": {"$in": keys}})
        return {"ok": True, "deleted_count": r.deleted_count, "by": "keys"}

    query: Dict[str, Any] = {}
    if status and status != "all":
        # "expired" is a logical filter, not a stored status
        if status == "expired":
            expired_only = True
        else:
            query["status"] = status
    if expired_only:
        # subscription_ends_at < now OR trial_ends_at < now (and no active sub)
        query["$or"] = [
            {"subscription_ends_at": {"$lt": _now()}, "status": {"$ne": "active"}},
            {"trial_ends_at": {"$lt": _now()}, "status": "trial"},
        ]
    if unactivated_only:
        query["machine_id"] = None

    if not query:
        raise HTTPException(400, "Refusing bulk-delete with empty filter. Specify status / keys / expired_only / unactivated_only.")

    r = await _db.licenses.delete_many(query)
    return {"ok": True, "deleted_count": r.deleted_count, "by": "filter", "filter": query}


@license_router.post("/admin/license/cleanup")
async def admin_cleanup(admin: dict = _admin_dep()):
    """One-click cleanup: deletes all revoked + all expired licenses.
    Keeps active and unexpired trial licenses untouched."""
    # 1. Revoked
    r1 = await _db.licenses.delete_many({"status": "revoked"})
    # 2. Expired trials
    r2 = await _db.licenses.delete_many({
        "status": "trial",
        "trial_ends_at": {"$lt": _now()},
    })
    # 3. Expired active subscriptions (subscription_ends_at past)
    r3 = await _db.licenses.delete_many({
        "subscription_ends_at": {"$lt": _now()},
        "status": {"$in": ["active", "expired"]},
    })
    return {
        "ok": True,
        "deleted": {
            "revoked": r1.deleted_count,
            "expired_trials": r2.deleted_count,
            "expired_subscriptions": r3.deleted_count,
            "total": r1.deleted_count + r2.deleted_count + r3.deleted_count,
        },
    }


@license_router.post("/admin/license/issue")
async def admin_issue_license(
    email: EmailStr,
    days: int = 31,
    admin: dict = _admin_dep(),
):
    """Manually issue an active license without Stripe (e.g. comp / vendor)."""
    key = _gen_license_key()
    lic = {
        "license_key": key,
        "email": email.lower(),
        "status": "active",
        "subscription_ends_at": _now() + timedelta(days=days),
        "trial_ends_at": None,
        "machine_id": None,
        "machine_label": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "activated_at": None,
        "created_at": _now(),
        "last_validated_at": _now(),
        "issued_by_admin": True,
    }
    await _db.licenses.insert_one(lic.copy())
    return {"ok": True, "license_key": key, "subscription_ends_at": _iso(lic["subscription_ends_at"])}


@license_router.get("/admin/license/transactions")
async def admin_transactions(skip: int = 0, limit: int = 200, admin: dict = _admin_dep()):
    total = await _db.payment_transactions.count_documents({})
    rows = []
    cursor = _db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    async for r in cursor:
        for k in ("created_at", "updated_at"):
            r[k] = _iso(r.get(k))
        rows.append(r)
    return {"total": total, "items": rows}
