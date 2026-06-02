"""
Krexion — Website Content (CMS) module
=======================================
Lets admins edit ALL public-website text from the admin panel — hero
heading, tagline, stats, feature cards, FAQ items, footer text, etc.
No code change or redeploy needed: the public HomePage / DownloadPage /
GuidePage fetch live content via GET /api/site-content.

Storage model
-------------
Single Mongo doc in `site_content` (`_id` == "default"):
{
  "_id": "default",
  "hero": { "badge": str, "h1_top": str, "h1_bottom": str,
            "subtitle": str, "cta_label": str, "cta_secondary_label": str },
  "stats": [ { "value": str, "label": str }, ... 4 items ... ],
  "features_intro": { "eyebrow": str, "title": str, "subtitle": str },
  "features": [ { "icon": str, "title": str, "desc": str }, ... ],
  "pricing_intro": { "eyebrow": str, "title": str, "subtitle": str },
  "faq_intro": { "eyebrow": str, "title": str, "subtitle": str },
  "faqs": [ { "q": str, "a": str }, ... ],
  "footer": { "tagline": str, "copyright": str },
  "nav": { "pricing_label": str, "features_label": str, "faq_label": str,
           "guide_label": str, "login_label": str, "cta_label": str },
  "updated_at": ISO str, "updated_by": str
}

If the doc doesn't exist yet, the GET endpoint returns the built-in
DEFAULT_SITE_CONTENT (matches today's hard-coded HomePage values 1:1).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Mongo handle + admin dep are injected by server.py (avoids circular import).
_db = None
_get_current_admin = None


site_content_router = APIRouter()


DEFAULT_SITE_CONTENT: Dict[str, Any] = {
    "hero": {
        "badge": "Cloud + Self-host • Pay with USDT • Links live 24/7",
        "h1_top": "Real traffic.",
        "h1_bottom": "Real conversions.",
        "subtitle": (
            "Manage your tracking, links and campaigns from anywhere in the world. "
            "Your krexion.com links stay live 24/7 — even when your PC is off."
        ),
        "cta_label": "See plans",
        "cta_secondary_label": "How it works",
    },
    "stats": [
        {"value": "10M+", "label": "Clicks delivered"},
        {"value": "120+", "label": "Countries supported"},
        {"value": "99.9%", "label": "Uptime"},
        {"value": "<30 min", "label": "License delivery"},
    ],
    "features_intro": {
        "eyebrow": "Built for scale",
        "title": "Everything you need to run traffic at scale",
        "subtitle": (
            "From single landing-page tests to multi-thousand-PC campaigns — "
            "one platform, fully self-hosted under your license."
        ),
    },
    # `icon` is a lucide-react component name. Frontend maps the string
    # to an actual icon (Globe, Activity, Layers, Cpu, Shield, MailCheck,
    # Zap, Lock, Sparkles, Check). Falls back to Sparkles if unknown.
    "features": [
        {
            "icon": "Globe",
            "title": "Cloud Dashboard — Login Anywhere",
            "desc": "Manage links, clicks and campaigns from any browser, any device. Your dashboard lives at krexion.com, not stuck on one PC.",
        },
        {
            "icon": "Activity",
            "title": "Always-On Tracking Links",
            "desc": "Every link you generate runs at krexion.com/r/xxx — clicks keep flowing even when your computer is off, sleeping, or unplugged.",
        },
        {
            "icon": "Layers",
            "title": "Massive Proxy Pool",
            "desc": "Plug in residential, ISP or mobile proxies. Built-in checker validates them at scale across parallel batches.",
        },
        {
            "icon": "Cpu",
            "title": "CPI Job Orchestrator",
            "desc": "Run Cost-Per-Install campaigns across distributed worker devices with smart routing and per-device fingerprinting.",
        },
        {
            "icon": "Shield",
            "title": "Form Filler + Real User Traffic",
            "desc": "Auto-fill landing pages and emulate genuine human patterns through real Chrome — not headless bots.",
        },
        {
            "icon": "MailCheck",
            "title": "Email Validation Suite",
            "desc": "Verify deliverability, separate cleaned lists, and feed only valid leads into your campaigns.",
        },
    ],
    "pricing_intro": {
        "eyebrow": "Pricing",
        "title": "Simple, transparent pricing",
        "subtitle": "Pay with USDT (TRC-20) — no card, no subscription, no surprises. Pick a plan, pay once, your license + login are emailed within 30 minutes.",
    },
    "faq_intro": {
        "eyebrow": "FAQ",
        "title": "Frequently asked questions",
        "subtitle": "Everything you need to know about how krexion.com works.",
    },
    "faqs": [
        {"q": "Do I need to install anything?",
         "a": "No — Krexion runs fully online at krexion.com. Login, generate links, view clicks, manage campaigns from any browser. The optional desktop installer is only for heavy features like Real User Traffic and Form Filler."},
        {"q": "Will my links die if I turn off my computer?",
         "a": "Never. All your links live on the krexion.com cloud — they keep tracking clicks 24/7 regardless of whether your PC is on, off, sleeping, or in a different country."},
        {"q": "How does payment work?",
         "a": "We accept USDT (TRC-20) only. Pick a plan, send USDT to the wallet shown at checkout, paste your TxID, and your license + login credentials are delivered to your email within 30 minutes."},
        {"q": "Do I need a credit card or bank?",
         "a": "No. Everything runs on crypto — no subscriptions, no recurring charges, no bank required. Pay only for the months you use."},
        {"q": "How many PCs can I activate?",
         "a": "Cloud dashboard works on unlimited devices. For the optional desktop install: Starter 1 PC, Pro 3 PCs, Business 10 PCs, Trial 1 PC."},
        {"q": "Can I get a refund?",
         "a": "Yes — if your license is not delivered within 24 hours of TxID submission and on-chain confirmation, we refund in full. Otherwise sales are final."},
    ],
    "footer": {
        "tagline": "Real traffic. Real conversions. Self-hosted under your license.",
        "copyright": "© 2026 Krexion. All rights reserved.",
    },
    "nav": {
        "features_label": "Features",
        "pricing_label": "Pricing",
        "download_label": "Download",
        "guide_label": "Guide",
        "faq_label": "FAQ",
        "login_label": "Login",
        "cta_label": "Get started",
    },
}


class FeatureItem(BaseModel):
    icon: str = "Sparkles"
    title: str = ""
    desc: str = ""


class FaqItem(BaseModel):
    q: str = ""
    a: str = ""


class StatItem(BaseModel):
    value: str = ""
    label: str = ""


class SiteContentUpdate(BaseModel):
    """Free-form update body. Each top-level section is optional so the
    admin can patch just one section (e.g. only hero) without resending
    the entire document.

    Unknown keys are stored as-is (forward-compat). Extra type validation
    on the well-known shapes prevents the obvious mistakes (forgetting
    the `value` field on a stat, etc.)."""
    hero: Optional[Dict[str, Any]] = None
    stats: Optional[List[StatItem]] = None
    features_intro: Optional[Dict[str, Any]] = None
    features: Optional[List[FeatureItem]] = None
    pricing_intro: Optional[Dict[str, Any]] = None
    faq_intro: Optional[Dict[str, Any]] = None
    faqs: Optional[List[FaqItem]] = None
    footer: Optional[Dict[str, Any]] = None
    nav: Optional[Dict[str, Any]] = None


def _merge(existing: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow merge — for sections that are dicts we shallow-merge,
    list/scalar fields are replaced wholesale (admin sends the full new
    list each time which keeps the form simple)."""
    out = dict(existing) if existing else {}
    for k, v in patch.items():
        if v is None:
            continue
        if k in ("hero", "features_intro", "pricing_intro", "faq_intro", "footer", "nav") \
                and isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


async def _load_doc() -> Dict[str, Any]:
    doc = await _db.site_content.find_one({"_id": "default"}, {"_id": 0})
    if not doc:
        return dict(DEFAULT_SITE_CONTENT)
    # Merge with defaults so any newly-added section (after a future
    # backend upgrade) is filled in even if the admin hasn't saved
    # over the doc yet. Prevents "missing key" surprises on the public
    # site after we add a section later.
    merged = dict(DEFAULT_SITE_CONTENT)
    for k, v in doc.items():
        merged[k] = v
    return merged


# ── Public endpoints ────────────────────────────────────────────────


@site_content_router.get("/site-content")
async def public_get_site_content():
    """Public read endpoint — used by HomePage to render content.
    Cached client-side; no auth required. Returns the merged effective
    document (DB overrides over defaults)."""
    return await _load_doc()


# ── Admin endpoints ─────────────────────────────────────────────────


@site_content_router.get("/admin/site-content")
async def admin_get_site_content(admin: dict = Depends(lambda: None)):  # patched at register time
    return await _load_doc()


@site_content_router.put("/admin/site-content")
async def admin_update_site_content(
    body: SiteContentUpdate,
    admin: dict = Depends(lambda: None),  # patched at register time
):
    """Patch one or more top-level sections. Empty / None sections are
    skipped so the admin can save just one tab at a time."""
    existing = await _db.site_content.find_one({"_id": "default"}, {"_id": 0}) or {}
    patch = body.model_dump(exclude_none=True)
    merged = _merge(existing, patch)
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    merged["updated_by"] = (admin or {}).get("email", "admin")
    await _db.site_content.update_one(
        {"_id": "default"}, {"$set": merged}, upsert=True
    )
    logger.info(
        f"[site-content] updated sections={list(patch.keys())} by={merged['updated_by']}"
    )
    # Return the fresh effective doc (with defaults applied) so the
    # admin UI can re-render immediately.
    return await _load_doc()


@site_content_router.post("/admin/site-content/reset")
async def admin_reset_site_content(admin: dict = Depends(lambda: None)):  # patched at register time
    """Reset back to the built-in defaults. Useful for the admin if a
    bad edit broke the public site."""
    await _db.site_content.delete_one({"_id": "default"})
    logger.info(f"[site-content] reset to defaults by={(admin or {}).get('email','admin')}")
    return await _load_doc()


def register_site_content_module(app, db, get_admin_dep, api_prefix: str = "/api"):
    """Wire the router into the FastAPI app. Called once from server.py
    at startup. We patch the admin Depends with the real
    `get_current_admin` from server.py instead of doing a circular
    import. The api_prefix is also injected so we match the
    DigitalOcean-strips-/api vs Emergent-keeps-/api convention used by
    the main api_router."""
    global _db, _get_current_admin
    _db = db
    _get_current_admin = get_admin_dep

    # Patch the admin dependency on the protected routes.
    for r in site_content_router.routes:
        if r.path.startswith("/admin/site-content"):
            for d in r.dependant.dependencies:
                if d.name == "admin":
                    d.call = get_admin_dep

    app.include_router(site_content_router, prefix=api_prefix)
    logger.info(
        f"Site Content (CMS) module loaded — {api_prefix}/site-content + {api_prefix}/admin/site-content/*"
    )
