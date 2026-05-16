"""
Krexion — Crypto Payment Module
================================

Self-contained FastAPI router for USDT-TRC20 crypto payments with
**manual admin approval** + optional **on-chain auto-verification**.

Customer flow:
  1. Visits /pricing → picks a plan
  2. POST /api/crypto/orders/create   (returns wallet + amount + order_id)
  3. Sends USDT-TRC20 from their own wallet
  4. POST /api/crypto/orders/{id}/submit-txid   (provides TxID)
  5. GET  /api/crypto/orders/{id}                (polls status)

Admin flow:
  GET  /api/admin/crypto/orders                  (list, filterable)
  POST /api/admin/crypto/orders/{id}/approve     (issues license + email)
  POST /api/admin/crypto/orders/{id}/reject      (with reason)
  GET  /api/admin/crypto/wallets                 (list wallets)
  POST /api/admin/crypto/wallets                 (add wallet)
  PUT  /api/admin/crypto/wallets/{id}            (update / toggle)
  GET  /api/admin/crypto/plans                   (list plans)
  POST /api/admin/crypto/plans                   (add)
  PUT  /api/admin/crypto/plans/{id}              (update)
  DELETE /api/admin/crypto/plans/{id}            (delete)

Storage (main DB):
  crypto_plans     — pricing plans
  crypto_wallets   — admin's deposit addresses
  crypto_orders    — customer orders with status flow
"""

from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
crypto_router = APIRouter(prefix="/api", tags=["crypto-payment"])

# ─── Dependencies injected from server.py ─────────────────────────────
_db: Any = None
_get_current_admin: Any = None
_issue_license: Any = None  # callable(email, plan_id, days, source) -> license_key
_send_email: Any = None
_create_customer_account: Any = None  # callable(email, name) -> (password|None, created_bool)


def _bind(*, main_db, get_current_admin, issue_license=None, send_email=None, create_customer_account=None) -> None:
    global _db, _get_current_admin, _issue_license, _send_email, _create_customer_account
    _db = main_db
    _get_current_admin = get_current_admin
    _issue_license = issue_license
    _send_email = send_email
    _create_customer_account = create_customer_account


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


# ─── Models ───────────────────────────────────────────────────────────
class PlanCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    price_usdt: float = Field(..., gt=0)
    duration_days: int = Field(..., gt=0)
    description: str = ""
    features: List[str] = []
    is_popular: bool = False
    enabled: bool = True
    sort_order: int = 0


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price_usdt: Optional[float] = None
    duration_days: Optional[int] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    is_popular: Optional[bool] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class WalletCreate(BaseModel):
    network: str = Field(..., min_length=2, max_length=20)  # e.g. TRC20, BEP20, BTC
    currency: str = "USDT"
    address: str = Field(..., min_length=20, max_length=100)
    label: str = ""
    enabled: bool = True
    is_primary: bool = False


class WalletUpdate(BaseModel):
    address: Optional[str] = None
    label: Optional[str] = None
    enabled: Optional[bool] = None
    is_primary: Optional[bool] = None


class OrderCreate(BaseModel):
    plan_id: str
    customer_name: str = Field(..., min_length=2, max_length=100)
    customer_email: EmailStr
    network: str = "TRC20"


class TxIDSubmit(BaseModel):
    tx_id: str = Field(..., min_length=10, max_length=200)


class RejectRequest(BaseModel):
    reason: str = "Payment could not be verified."


# ─── Default seeding ──────────────────────────────────────────────────
DEFAULT_PLANS = [
    {
        "id": "trial",
        "name": "Trial",
        "price_usdt": 3.0,
        "duration_days": 1,
        "description": "Try Krexion for 1 day. Perfect to test the system.",
        "features": [
            "1 day access",
            "Limited clicks (1,000)",
            "1 PC activation",
            "Email support",
        ],
        "is_popular": False,
        "enabled": True,
        "sort_order": 0,
    },
    {
        "id": "starter",
        "name": "Starter",
        "price_usdt": 50.0,
        "duration_days": 30,
        "description": "Perfect for solo affiliate marketers.",
        "features": [
            "10,000 clicks/month",
            "1 PC activation",
            "All core features",
            "Email support",
        ],
        "is_popular": False,
        "enabled": True,
        "sort_order": 1,
    },
    {
        "id": "pro",
        "name": "Pro",
        "price_usdt": 80.0,
        "duration_days": 30,
        "description": "Most popular — for serious marketers and small teams.",
        "features": [
            "100,000 clicks/month",
            "3 PC activations",
            "Form Filler + RUT",
            "Priority support",
            "Advanced analytics",
        ],
        "is_popular": True,
        "enabled": True,
        "sort_order": 2,
    },
    {
        "id": "business",
        "name": "Business",
        "price_usdt": 200.0,
        "duration_days": 30,
        "description": "For agencies and high-volume operators.",
        "features": [
            "Unlimited clicks",
            "10 PC activations",
            "All features + white-label",
            "Priority chat support",
            "Custom branding",
            "Sub-user accounts",
        ],
        "is_popular": False,
        "enabled": True,
        "sort_order": 3,
    },
]


async def seed_defaults():
    """Seed default plans + primary wallet if collections are empty."""
    if _db is None:
        return
    # Plans
    if await _db.crypto_plans.count_documents({}) == 0:
        now_iso = _now().isoformat()
        for p in DEFAULT_PLANS:
            doc = {**p, "created_at": now_iso, "updated_at": now_iso}
            await _db.crypto_plans.insert_one(doc)
        logger.info(f"Seeded {len(DEFAULT_PLANS)} default plans")

    # Primary USDT-TRC20 wallet from env
    if await _db.crypto_wallets.count_documents({}) == 0:
        addr = os.environ.get("USDT_WALLET_TRC20", "").strip()
        if addr:
            await _db.crypto_wallets.insert_one({
                "id": "primary-usdt-trc20",
                "network": "TRC20",
                "currency": "USDT",
                "address": addr,
                "label": "Primary USDT-TRC20 (auto-seeded from env)",
                "enabled": True,
                "is_primary": True,
                "created_at": _now().isoformat(),
                "updated_at": _now().isoformat(),
            })
            logger.info(f"Seeded primary wallet: {addr[:6]}...{addr[-4:]}")


# ─── Public endpoints ─────────────────────────────────────────────────
@crypto_router.get("/crypto/plans")
async def list_plans_public():
    """Public list of enabled pricing plans."""
    plans = await _db.crypto_plans.find({"enabled": True}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    return {"plans": plans}


@crypto_router.get("/crypto/wallets/active")
async def get_active_wallets():
    """Public — wallets customers can pay to."""
    wallets = await _db.crypto_wallets.find({"enabled": True}, {"_id": 0}).to_list(20)
    return {"wallets": wallets}


@crypto_router.post("/crypto/orders/create")
async def create_order(body: OrderCreate):
    """Customer creates an order — returns payment details."""
    plan = await _db.crypto_plans.find_one({"id": body.plan_id, "enabled": True}, {"_id": 0})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found or disabled")

    # Pick active wallet matching network (TRC20 by default)
    wallet = await _db.crypto_wallets.find_one(
        {"network": body.network.upper(), "enabled": True},
        {"_id": 0},
        sort=[("is_primary", -1)],
    )
    if not wallet:
        raise HTTPException(status_code=503, detail=f"No active {body.network} wallet configured")

    order_id = "ORD-" + uuid.uuid4().hex[:12].upper()
    expires_at = _now() + timedelta(minutes=30)

    doc = {
        "id": order_id,
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "amount_usdt": plan["price_usdt"],
        "duration_days": plan["duration_days"],
        "customer_name": body.customer_name.strip(),
        "customer_email": body.customer_email.lower().strip(),
        "network": body.network.upper(),
        "wallet_address": wallet["address"],
        "wallet_currency": wallet["currency"],
        "tx_id": None,
        "status": "pending",  # pending | submitted | approved | rejected | expired
        "license_key": None,
        "admin_note": None,
        "reject_reason": None,
        "created_at": _now().isoformat(),
        "expires_at": expires_at.isoformat(),
        "submitted_at": None,
        "approved_at": None,
        "rejected_at": None,
    }
    await _db.crypto_orders.insert_one(doc)

    # Welcome email (non-blocking, best-effort)
    if _send_email:
        try:
            await _send_email(
                kind="welcome",
                customer_email=doc["customer_email"],
                customer_name=doc["customer_name"],
                order_id=order_id,
                plan_name=doc["plan_name"],
            )
        except Exception:
            pass

    return _serialize_order(doc)


@crypto_router.get("/crypto/orders/{order_id}")
async def get_order_status(order_id: str):
    """Customer polls their order status."""
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Auto-expire pending orders
    if order["status"] == "pending":
        try:
            exp = datetime.fromisoformat(order["expires_at"])
            if _now() > exp:
                await _db.crypto_orders.update_one(
                    {"id": order_id},
                    {"$set": {"status": "expired"}}
                )
                order["status"] = "expired"
        except Exception:
            pass

    return _serialize_order(order)


@crypto_router.post("/crypto/orders/{order_id}/submit-txid")
async def submit_txid(order_id: str, body: TxIDSubmit):
    """Customer submits TxID after sending payment."""
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] not in ("pending", "submitted"):
        raise HTTPException(status_code=400, detail=f"Order is {order['status']}, cannot submit TxID")

    # Check duplicate TxID across orders
    dup = await _db.crypto_orders.find_one(
        {"tx_id": body.tx_id.strip(), "id": {"$ne": order_id}},
        {"_id": 0, "id": 1}
    )
    if dup:
        raise HTTPException(status_code=409, detail="This TxID is already used by another order")

    await _db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "tx_id": body.tx_id.strip(),
            "status": "submitted",
            "submitted_at": _now().isoformat(),
        }}
    )
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    return _serialize_order(order)


# ─── Tronscan on-chain verifier (optional helper for admin) ───────────
async def verify_tron_tx(tx_id: str, expected_to: str, expected_amount: float) -> Dict[str, Any]:
    """Check Tron blockchain for a USDT-TRC20 transfer.
    Returns {ok: bool, reason: str, actual_amount, confirmations, ...}."""
    url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={tx_id}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"ok": False, "reason": f"Tronscan returned {r.status_code}"}
            data = r.json()
    except Exception as e:
        return {"ok": False, "reason": f"Tronscan unreachable: {e}"}

    # Look for TRC20 transfer to expected_to
    transfers = data.get("trc20TransferInfo", []) or data.get("tokenTransferInfo")
    if isinstance(transfers, dict):
        transfers = [transfers]
    transfers = transfers or []
    for t in transfers:
        to_addr = (t.get("to_address") or "").strip()
        amount_str = t.get("amount_str") or str(t.get("amount", 0))
        decimals = int(t.get("decimals", 6))
        try:
            actual = int(amount_str) / (10 ** decimals)
        except Exception:
            actual = 0
        symbol = t.get("symbol") or t.get("name") or ""
        if to_addr == expected_to and "USDT" in symbol.upper():
            if actual + 0.001 >= expected_amount:  # small tolerance
                confirms = data.get("confirmed", False)
                return {
                    "ok": True,
                    "reason": "Verified on-chain",
                    "actual_amount": actual,
                    "confirmed": confirms,
                    "to": to_addr,
                    "symbol": symbol,
                }
            else:
                return {
                    "ok": False,
                    "reason": f"Underpayment: expected {expected_amount} USDT, got {actual}",
                    "actual_amount": actual,
                }
    return {"ok": False, "reason": "No matching USDT transfer found in transaction"}


# ─── Admin endpoints ──────────────────────────────────────────────────
def _admin_dep():
    """Lazy resolver — _get_current_admin is set by _bind() at app startup."""
    async def _resolved(request: Request):
        if _get_current_admin is None:
            raise HTTPException(503, "Admin auth not wired yet.")
        return await _get_current_admin(request)
    return Depends(_resolved)


@crypto_router.get("/admin/crypto/orders")
async def admin_list_orders(status: Optional[str] = None, limit: int = 100, admin: dict = _admin_dep()):
    q = {}
    if status:
        q["status"] = status
    cur = _db.crypto_orders.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = await cur.to_list(limit)
    return {"orders": [_serialize_order(o) for o in items], "count": len(items)}


@crypto_router.get("/admin/crypto/orders/{order_id}/verify-onchain")
async def admin_verify_onchain(order_id: str, admin: dict = _admin_dep()):
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if not order.get("tx_id"):
        raise HTTPException(status_code=400, detail="No TxID submitted yet")
    res = await verify_tron_tx(order["tx_id"], order["wallet_address"], order["amount_usdt"])
    return res


@crypto_router.post("/admin/crypto/orders/{order_id}/approve")
async def admin_approve_order(order_id: str, note: Optional[str] = None, admin: dict = _admin_dep()):
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] == "approved":
        raise HTTPException(status_code=400, detail="Order already approved")

    # Issue license via injected function (falls back to inline if not bound)
    license_key = None
    if _issue_license:
        try:
            license_key = await _issue_license(
                email=order["customer_email"],
                plan_id=order["plan_id"],
                days=int(order["duration_days"]),
                source="crypto-order",
                order_id=order_id,
            )
        except Exception as e:
            logger.error(f"License issue failed: {e}")

    if not license_key:
        # Inline fallback — generate and store directly in licenses collection
        raw = uuid.uuid4().hex.upper()[:16]
        license_key = "KRX-" + "-".join(raw[i : i + 4] for i in range(0, 16, 4))
        expires = _now() + timedelta(days=int(order["duration_days"]))
        await _db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "license_key": license_key,
            "email": order["customer_email"],
            "name": order["customer_name"],
            "plan_id": order["plan_id"],
            "plan_name": order["plan_name"],
            "status": "active",
            "issued_at": _now().isoformat(),
            "expires_at": expires.isoformat(),
            "machine_ids": [],
            "max_pcs": 1 if order["plan_id"] in ("trial", "starter") else (3 if order["plan_id"] == "pro" else 10),
            "source": "crypto-order",
            "order_id": order_id,
        })

    # Update order
    await _db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "approved",
            "license_key": license_key,
            "admin_note": note,
            "approved_at": _now().isoformat(),
        }}
    )

    # Auto-create customer account on krexion.com (so they can log in to portal)
    account_password = None
    account_was_created = False
    if _create_customer_account:
        try:
            account_password, account_was_created = await _create_customer_account(
                email=order["customer_email"],
                name=order["customer_name"],
            )
        except Exception as e:
            logger.warning(f"Auto-account creation failed: {e}")

    # Send email if helper available
    if _send_email:
        try:
            await _send_email(
                kind="license",
                customer_email=order["customer_email"],
                customer_name=order["customer_name"],
                plan_name=order["plan_name"],
                license_key=license_key,
                duration_days=int(order["duration_days"]),
                order_id=order_id,
                account_password=account_password,        # only set when newly created
                account_was_created=account_was_created,
            )
        except Exception as e:
            logger.warning(f"License email failed: {e}")

    updated = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    return _serialize_order(updated)


@crypto_router.post("/admin/crypto/orders/{order_id}/reject")
async def admin_reject_order(order_id: str, body: RejectRequest, admin: dict = _admin_dep()):
    order = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["status"] == "approved":
        raise HTTPException(status_code=400, detail="Cannot reject an approved order")

    await _db.crypto_orders.update_one(
        {"id": order_id},
        {"$set": {
            "status": "rejected",
            "reject_reason": body.reason,
            "rejected_at": _now().isoformat(),
        }}
    )

    if _send_email:
        try:
            await _send_email(
                kind="rejection",
                customer_email=order["customer_email"],
                customer_name=order["customer_name"],
                order_id=order_id,
                reason=body.reason,
            )
        except Exception:
            pass

    updated = await _db.crypto_orders.find_one({"id": order_id}, {"_id": 0})
    return _serialize_order(updated)


# ─── Wallets admin ────────────────────────────────────────────────────
@crypto_router.get("/admin/crypto/wallets")
async def admin_list_wallets(admin: dict = _admin_dep()):
    wallets = await _db.crypto_wallets.find({}, {"_id": 0}).to_list(100)
    return {"wallets": wallets}


@crypto_router.post("/admin/crypto/wallets")
async def admin_add_wallet(body: WalletCreate, admin: dict = _admin_dep()):
    wallet_id = str(uuid.uuid4())
    if body.is_primary:
        # Demote others to non-primary in same network
        await _db.crypto_wallets.update_many(
            {"network": body.network.upper()},
            {"$set": {"is_primary": False}}
        )
    doc = {
        "id": wallet_id,
        "network": body.network.upper(),
        "currency": body.currency.upper(),
        "address": body.address.strip(),
        "label": body.label.strip(),
        "enabled": body.enabled,
        "is_primary": body.is_primary,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await _db.crypto_wallets.insert_one(doc)
    return doc


@crypto_router.put("/admin/crypto/wallets/{wallet_id}")
async def admin_update_wallet(wallet_id: str, body: WalletUpdate, admin: dict = _admin_dep()):
    update = {k: v for k, v in body.dict(exclude_none=True).items()}
    if update.get("is_primary"):
        wallet = await _db.crypto_wallets.find_one({"id": wallet_id}, {"_id": 0})
        if wallet:
            await _db.crypto_wallets.update_many(
                {"network": wallet["network"], "id": {"$ne": wallet_id}},
                {"$set": {"is_primary": False}}
            )
    update["updated_at"] = _now().isoformat()
    res = await _db.crypto_wallets.update_one({"id": wallet_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Wallet not found")
    updated = await _db.crypto_wallets.find_one({"id": wallet_id}, {"_id": 0})
    return updated


@crypto_router.delete("/admin/crypto/wallets/{wallet_id}")
async def admin_delete_wallet(wallet_id: str, admin: dict = _admin_dep()):
    res = await _db.crypto_wallets.delete_one({"id": wallet_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"message": "Wallet deleted"}


# ─── Plans admin ──────────────────────────────────────────────────────
@crypto_router.get("/admin/crypto/plans")
async def admin_list_plans(admin: dict = _admin_dep()):
    plans = await _db.crypto_plans.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    return {"plans": plans}


@crypto_router.post("/admin/crypto/plans")
async def admin_add_plan(body: PlanCreate, admin: dict = _admin_dep()):
    plan_id = body.name.lower().replace(" ", "-")[:30]
    if await _db.crypto_plans.find_one({"id": plan_id}):
        raise HTTPException(status_code=409, detail="Plan with this name already exists")
    doc = {
        "id": plan_id,
        **body.dict(),
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await _db.crypto_plans.insert_one(doc)
    return doc


@crypto_router.put("/admin/crypto/plans/{plan_id}")
async def admin_update_plan(plan_id: str, body: PlanUpdate, admin: dict = _admin_dep()):
    update = {k: v for k, v in body.dict(exclude_none=True).items()}
    update["updated_at"] = _now().isoformat()
    res = await _db.crypto_plans.update_one({"id": plan_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return await _db.crypto_plans.find_one({"id": plan_id}, {"_id": 0})


@crypto_router.delete("/admin/crypto/plans/{plan_id}")
async def admin_delete_plan(plan_id: str, admin: dict = _admin_dep()):
    # Don't allow delete if there are orders referencing it
    cnt = await _db.crypto_orders.count_documents({"plan_id": plan_id})
    if cnt > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete — {cnt} orders use this plan. Disable instead.")
    res = await _db.crypto_plans.delete_one({"id": plan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"message": "Plan deleted"}


# ─── Helper: serializer ───────────────────────────────────────────────
def _serialize_order(o: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any potential ObjectId / private fields before returning."""
    if not o:
        return o
    o.pop("_id", None)
    return o
