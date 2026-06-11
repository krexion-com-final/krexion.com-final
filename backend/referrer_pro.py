"""
Krexion — Referrer Pro Module (2026-06-11 additive)
====================================================

Adds professional realism layers on top of the legacy
`_resolve_visit_referer()` in real_user_traffic.py:

  A) Geo-localized search Referers (proxy country → google.de / .fr / …)
  B) Multi-engine search modes (Bing / Yahoo / DDG / Yandex / YouTube)
  C) Social link-wrapper Referers (l.facebook.com / t.co / lnkd.in / …)
  D) Mobile in-app browser deep paths
  E) Sec-Fetch-* header family auto-sync per Referer type
  G) UTM source/medium variation pools
  J) fbclid / gclid embedded-timestamp realism
  K) Search-engine Referer-Policy auto-strip (path → origin)
  L) Network click-redirect chain
  +
  WEIGHTED platform-pool resolver (user-defined % per platform)
  WEIGHTED email-ESP resolver  (user-defined % per ESP / webmail / empty)

100% additive — every helper here returns safe defaults on bad input.
The original resolver is the FINAL fallback when ANY thing goes wrong.

NOTE: This module deliberately has NO imports from real_user_traffic /
server.py so there is zero circular-import risk and it can be loaded
even if those files are being hot-reloaded.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger("referrer_pro")


# ──────────────────────────────────────────────────────────────────────
# A) Geo-localized search engine TLDs
# ──────────────────────────────────────────────────────────────────────
# Country-code (ISO-2 lowercase) → (google host, bing market, yahoo host)
# Used when the operator picks a search mode AND the proxy exit-country
# is known. Falls back to .com when country is unknown / unsupported.
_GEO_SEARCH_HOSTS: Dict[str, Dict[str, str]] = {
    "us": {"google": "www.google.com",      "bing_cc": "US", "yahoo": "search.yahoo.com"},
    "gb": {"google": "www.google.co.uk",    "bing_cc": "GB", "yahoo": "uk.search.yahoo.com"},
    "uk": {"google": "www.google.co.uk",    "bing_cc": "GB", "yahoo": "uk.search.yahoo.com"},
    "de": {"google": "www.google.de",       "bing_cc": "DE", "yahoo": "de.search.yahoo.com"},
    "fr": {"google": "www.google.fr",       "bing_cc": "FR", "yahoo": "fr.search.yahoo.com"},
    "es": {"google": "www.google.es",       "bing_cc": "ES", "yahoo": "es.search.yahoo.com"},
    "it": {"google": "www.google.it",       "bing_cc": "IT", "yahoo": "it.search.yahoo.com"},
    "nl": {"google": "www.google.nl",       "bing_cc": "NL", "yahoo": "nl.search.yahoo.com"},
    "be": {"google": "www.google.be",       "bing_cc": "BE", "yahoo": "search.yahoo.com"},
    "ch": {"google": "www.google.ch",       "bing_cc": "CH", "yahoo": "ch.search.yahoo.com"},
    "at": {"google": "www.google.at",       "bing_cc": "AT", "yahoo": "at.search.yahoo.com"},
    "se": {"google": "www.google.se",       "bing_cc": "SE", "yahoo": "se.search.yahoo.com"},
    "no": {"google": "www.google.no",       "bing_cc": "NO", "yahoo": "no.search.yahoo.com"},
    "dk": {"google": "www.google.dk",       "bing_cc": "DK", "yahoo": "dk.search.yahoo.com"},
    "fi": {"google": "www.google.fi",       "bing_cc": "FI", "yahoo": "fi.search.yahoo.com"},
    "pl": {"google": "www.google.pl",       "bing_cc": "PL", "yahoo": "pl.search.yahoo.com"},
    "pt": {"google": "www.google.pt",       "bing_cc": "PT", "yahoo": "pt.search.yahoo.com"},
    "ie": {"google": "www.google.ie",       "bing_cc": "IE", "yahoo": "ie.search.yahoo.com"},
    "ca": {"google": "www.google.ca",       "bing_cc": "CA", "yahoo": "ca.search.yahoo.com"},
    "au": {"google": "www.google.com.au",   "bing_cc": "AU", "yahoo": "au.search.yahoo.com"},
    "nz": {"google": "www.google.co.nz",    "bing_cc": "NZ", "yahoo": "nz.search.yahoo.com"},
    "in": {"google": "www.google.co.in",    "bing_cc": "IN", "yahoo": "in.search.yahoo.com"},
    "pk": {"google": "www.google.com.pk",   "bing_cc": "PK", "yahoo": "search.yahoo.com"},
    "bd": {"google": "www.google.com.bd",   "bing_cc": "BD", "yahoo": "search.yahoo.com"},
    "lk": {"google": "www.google.lk",       "bing_cc": "LK", "yahoo": "search.yahoo.com"},
    "br": {"google": "www.google.com.br",   "bing_cc": "BR", "yahoo": "br.search.yahoo.com"},
    "mx": {"google": "www.google.com.mx",   "bing_cc": "MX", "yahoo": "mx.search.yahoo.com"},
    "ar": {"google": "www.google.com.ar",   "bing_cc": "AR", "yahoo": "ar.search.yahoo.com"},
    "cl": {"google": "www.google.cl",       "bing_cc": "CL", "yahoo": "cl.search.yahoo.com"},
    "co": {"google": "www.google.com.co",   "bing_cc": "CO", "yahoo": "co.search.yahoo.com"},
    "pe": {"google": "www.google.com.pe",   "bing_cc": "PE", "yahoo": "search.yahoo.com"},
    "ru": {"google": "www.google.ru",       "bing_cc": "RU", "yahoo": "search.yahoo.com"},
    "ua": {"google": "www.google.com.ua",   "bing_cc": "UA", "yahoo": "search.yahoo.com"},
    "tr": {"google": "www.google.com.tr",   "bing_cc": "TR", "yahoo": "tr.search.yahoo.com"},
    "ae": {"google": "www.google.ae",       "bing_cc": "AE", "yahoo": "maktoob.search.yahoo.com"},
    "sa": {"google": "www.google.com.sa",   "bing_cc": "SA", "yahoo": "search.yahoo.com"},
    "eg": {"google": "www.google.com.eg",   "bing_cc": "EG", "yahoo": "search.yahoo.com"},
    "za": {"google": "www.google.co.za",    "bing_cc": "ZA", "yahoo": "za.search.yahoo.com"},
    "ng": {"google": "www.google.com.ng",   "bing_cc": "NG", "yahoo": "search.yahoo.com"},
    "ke": {"google": "www.google.co.ke",    "bing_cc": "KE", "yahoo": "search.yahoo.com"},
    "jp": {"google": "www.google.co.jp",    "bing_cc": "JP", "yahoo": "search.yahoo.co.jp"},
    "kr": {"google": "www.google.co.kr",    "bing_cc": "KR", "yahoo": "search.yahoo.com"},
    "sg": {"google": "www.google.com.sg",   "bing_cc": "SG", "yahoo": "sg.search.yahoo.com"},
    "my": {"google": "www.google.com.my",   "bing_cc": "MY", "yahoo": "malaysia.search.yahoo.com"},
    "id": {"google": "www.google.co.id",    "bing_cc": "ID", "yahoo": "id.search.yahoo.com"},
    "ph": {"google": "www.google.com.ph",   "bing_cc": "PH", "yahoo": "ph.search.yahoo.com"},
    "th": {"google": "www.google.co.th",    "bing_cc": "TH", "yahoo": "search.yahoo.com"},
    "vn": {"google": "www.google.com.vn",   "bing_cc": "VN", "yahoo": "search.yahoo.com"},
    "hk": {"google": "www.google.com.hk",   "bing_cc": "HK", "yahoo": "hk.search.yahoo.com"},
    "tw": {"google": "www.google.com.tw",   "bing_cc": "TW", "yahoo": "tw.search.yahoo.com"},
    "il": {"google": "www.google.co.il",    "bing_cc": "IL", "yahoo": "search.yahoo.com"},
}


def get_geo_search_hosts(country: Optional[str]) -> Dict[str, str]:
    """Return geo-matched search hosts for proxy exit country (ISO-2).
    Falls back to US (.com) when country is empty / unknown."""
    cc = (country or "").strip().lower()[:2]
    return _GEO_SEARCH_HOSTS.get(cc, _GEO_SEARCH_HOSTS["us"])


# ──────────────────────────────────────────────────────────────────────
# B) Multi-engine search SERP URL builders
# ──────────────────────────────────────────────────────────────────────
def build_search_referer(engine: str, keyword: str, country: Optional[str] = None,
                          strip_path: bool = False) -> str:
    """Build a realistic SERP Referer URL for the given engine + keyword.

    `strip_path=True` returns just the origin (e.g. "https://www.google.com/")
    — matches the modern `Referrer-Policy: strict-origin-when-cross-origin`
    behaviour of real Google / Bing / DDG / Yandex (gap K).
    """
    engine = (engine or "google").lower().strip()
    kw = (keyword or "").strip()
    hosts = get_geo_search_hosts(country)

    if engine == "google":
        host = hosts["google"]
        if strip_path or not kw:
            return f"https://{host}/"
        return f"https://{host}/search?q={quote_plus(kw)}"

    if engine == "bing":
        cc = hosts.get("bing_cc", "US")
        if strip_path or not kw:
            return "https://www.bing.com/"
        return f"https://www.bing.com/search?q={quote_plus(kw)}&cc={cc}&form=QBLH"

    if engine == "yahoo":
        host = hosts["yahoo"]
        if strip_path or not kw:
            return f"https://{host}/"
        return f"https://{host}/search?p={quote_plus(kw)}"

    if engine == "duckduckgo" or engine == "ddg":
        if strip_path or not kw:
            return "https://duckduckgo.com/"
        return f"https://duckduckgo.com/?q={quote_plus(kw)}&t=h_&ia=web"

    if engine == "yandex":
        if strip_path or not kw:
            return "https://yandex.com/"
        return f"https://yandex.com/search/?text={quote_plus(kw)}"

    if engine == "youtube":
        if strip_path or not kw:
            return "https://www.youtube.com/"
        return f"https://www.youtube.com/results?search_query={quote_plus(kw)}"

    if engine == "baidu":
        if strip_path or not kw:
            return "https://www.baidu.com/"
        return f"https://www.baidu.com/s?wd={quote_plus(kw)}"

    if engine == "naver":
        if strip_path or not kw:
            return "https://search.naver.com/"
        return f"https://search.naver.com/search.naver?query={quote_plus(kw)}"

    # Unknown engine → safe fallback
    host = hosts["google"]
    if strip_path or not kw:
        return f"https://{host}/"
    return f"https://{host}/search?q={quote_plus(kw)}"


# ──────────────────────────────────────────────────────────────────────
# C) Social link-wrapper Referers (most realistic)
# ──────────────────────────────────────────────────────────────────────
# Real users almost always come via the platform's link shortener /
# outbound wrapper, NOT the bare homepage. Anti-fraud trackers know
# this distribution — pure "https://www.facebook.com/" Referer on
# bulk affiliate clicks looks bot-y.
_SOCIAL_WRAPPER_REFERERS: Dict[str, List[Tuple[float, str]]] = {
    "facebook": [
        # (weight, template) — wildcards filled at pick time
        (0.45, "https://l.facebook.com/l.php?u={enc_u}&h={hash16}"),
        (0.30, "https://lm.facebook.com/l.php?u={enc_u}&h={hash16}"),
        (0.15, "https://www.facebook.com/"),
        (0.10, "https://m.facebook.com/"),
    ],
    "instagram": [
        (0.55, "https://l.instagram.com/?u={enc_u}&e={hash16}"),
        (0.25, "https://www.instagram.com/"),
        (0.20, "https://help.instagram.com/"),
    ],
    "tiktok": [
        (0.55, "https://www.tiktok.com/link/v2?aid=1988&lang=en&u={enc_u}"),
        (0.25, "https://www.tiktok.com/"),
        (0.20, "https://m.tiktok.com/"),
    ],
    "twitter": [
        (0.85, "https://t.co/{tco_id}"),
        (0.15, "https://twitter.com/"),
    ],
    "x": [
        (0.85, "https://t.co/{tco_id}"),
        (0.15, "https://x.com/"),
    ],
    "linkedin": [
        (0.65, "https://lnkd.in/{lnkd_id}"),
        (0.25, "https://www.linkedin.com/"),
        (0.10, "https://www.linkedin.com/feed/"),
    ],
    "reddit": [
        (0.55, "https://out.reddit.com/?url={enc_u}&token={hash32}"),
        (0.25, "https://www.reddit.com/"),
        (0.20, "https://old.reddit.com/"),
    ],
    "youtube": [
        (0.55, "https://www.youtube.com/redirect?event=video_description&redir_token={hash32}&q={enc_u}"),
        (0.30, "https://www.youtube.com/"),
        (0.15, "https://m.youtube.com/"),
    ],
    "snapchat": [
        (0.70, "https://www.snapchat.com/"),
        (0.30, "https://l.snapchat.com/?u={enc_u}"),
    ],
    "pinterest": [
        (0.60, "https://www.pinterest.com/"),
        (0.40, "https://www.pinterest.com/pin/{pin_id}/"),
    ],
    "whatsapp": [
        (0.95, ""),  # WhatsApp clicks generally arrive with NO referer
        (0.05, "https://api.whatsapp.com/"),
    ],
    "telegram": [
        (0.85, ""),  # Telegram clicks: same
        (0.15, "https://t.me/"),
    ],
    "discord": [
        (0.85, ""),  # Discord clicks: same
        (0.15, "https://discord.com/"),
    ],
}


_TCO_CHARSET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _rand_tco_id() -> str:
    return "".join(random.choices(_TCO_CHARSET, k=10))


def _rand_lnkd_id() -> str:
    # LinkedIn /lnkd.in/ has 8-char base36 IDs
    return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=8))


def _rand_pin_id() -> str:
    # Pinterest pin IDs are large integers (~17-18 digits)
    return str(random.randint(10**17, 10**18 - 1))


def _rand_hash(n: int) -> str:
    return "".join(random.choices("0123456789abcdef", k=n))


def build_social_wrapper_referer(platform: str, target_url: str) -> str:
    """Return a realistic outbound-wrapper Referer URL for the given
    social platform. Falls back to bare homepage when unknown.
    """
    p = (platform or "").lower().strip()
    if p == "x":
        p = "x"
    pool = _SOCIAL_WRAPPER_REFERERS.get(p)
    if not pool:
        return ""

    # Weighted choice
    roll = random.random()
    total = 0.0
    pick = pool[-1][1]
    for w, tpl in pool:
        total += w
        if roll <= total:
            pick = tpl
            break

    if not pick:
        return ""

    enc_u = quote_plus(target_url or "")
    return (pick
            .replace("{enc_u}",   enc_u)
            .replace("{tco_id}",  _rand_tco_id())
            .replace("{lnkd_id}", _rand_lnkd_id())
            .replace("{pin_id}",  _rand_pin_id())
            .replace("{hash16}",  _rand_hash(16))
            .replace("{hash32}",  _rand_hash(32)))


# ──────────────────────────────────────────────────────────────────────
# D) Mobile in-app browser deep paths (additive: only used when UA is
# an in-app webview — Instagram, Facebook, TikTok, Snapchat, etc.)
# ──────────────────────────────────────────────────────────────────────
def is_inapp_browser_ua(ua: str) -> str:
    """Returns the in-app browser short-name when the UA is one, else ""."""
    if not ua:
        return ""
    ual = ua.lower()
    if "instagram" in ual:
        return "instagram"
    if "fbav" in ual or "fban" in ual or "fb_iab" in ual:
        return "facebook"
    if "tiktok" in ual or "musical_ly" in ual or "trill" in ual:
        return "tiktok"
    if "snapchat" in ual:
        return "snapchat"
    if "linkedinapp" in ual:
        return "linkedin"
    if "twitter" in ual and "android" in ual:
        return "twitter"
    return ""


def build_inapp_deep_referer(platform: str) -> str:
    """Build a realistic in-app deep-path Referer for a mobile webview
    visit (the user tapped a link inside the app's feed/post viewer).
    """
    p = (platform or "").lower()
    if p == "tiktok":
        vid_id = str(random.randint(7000000000000000000, 7999999999999999999))
        user_id = "user" + "".join(random.choices("0123456789", k=random.randint(6, 10)))
        return f"https://www.tiktok.com/@{user_id}/video/{vid_id}"
    if p == "instagram":
        post_id = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", k=11))
        return f"https://www.instagram.com/p/{post_id}/"
    if p == "facebook":
        page_id = str(random.randint(10**14, 10**15 - 1))
        post_id = str(random.randint(10**14, 10**15 - 1))
        return f"https://m.facebook.com/story.php?story_fbid={post_id}&id={page_id}"
    if p == "snapchat":
        return "https://www.snapchat.com/discover"
    if p == "linkedin":
        urn = "".join(random.choices("0123456789", k=19))
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{urn}/"
    return ""


# ──────────────────────────────────────────────────────────────────────
# E) Sec-Fetch-* header family — synced to Referer kind
# ──────────────────────────────────────────────────────────────────────
def build_sec_fetch_headers(referer_url: str, is_navigation: bool = True) -> Dict[str, str]:
    """Modern Chrome sends `Sec-Fetch-*` headers on every top-level nav.
    Trackers cross-check these against the Referer host:
      - Bookmark / typed URL  → Site: none, User: ?1, Mode: navigate
      - Cross-site click      → Site: cross-site, User: ?1, Mode: navigate
      - Same-origin click     → Site: same-origin, Mode: navigate

    Returns a dict that the engine merges into extra_http_headers.
    """
    headers: Dict[str, str] = {
        "Sec-Fetch-Mode": "navigate" if is_navigation else "no-cors",
        "Sec-Fetch-Dest": "document" if is_navigation else "empty",
        "Sec-Fetch-User": "?1",
    }
    if not referer_url:
        headers["Sec-Fetch-Site"] = "none"
    else:
        # Cross-site is the realistic case for affiliate offer landing
        # arriving from a search engine / social wrapper.
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


# ──────────────────────────────────────────────────────────────────────
# G) UTM source/medium variation pool — multiple realistic spellings
# ──────────────────────────────────────────────────────────────────────
# Real marketers use inconsistent UTM values across campaigns. Single
# fixed value across 1000+ visits is the bot-tell. Per-platform pool
# below is sampled randomly each visit.
_UTM_VARIATIONS: Dict[str, Dict[str, List[str]]] = {
    "facebook": {
        "source": ["facebook", "fb", "facebook_ads", "meta", "fb_ads"],
        "medium": ["paid_social", "social", "cpc", "feed", "social-cpc"],
    },
    "instagram": {
        "source": ["instagram", "ig", "instagram_ads", "meta_ig"],
        "medium": ["paid_social", "social", "stories", "feed", "reels"],
    },
    "tiktok": {
        "source": ["tiktok", "tt", "tiktok_ads", "tiktok_for_business"],
        "medium": ["paid_social", "social", "cpc", "video"],
    },
    "google": {
        "source": ["google", "google_ads", "adwords", "googleads"],
        "medium": ["cpc", "ppc", "paid_search", "search"],
    },
    "bing": {
        "source": ["bing", "microsoft", "msads"],
        "medium": ["cpc", "ppc", "paid_search"],
    },
    "youtube": {
        "source": ["youtube", "yt", "youtube_ads"],
        "medium": ["video", "paid_video", "cpv"],
    },
    "twitter": {
        "source": ["twitter", "x", "twitter_ads"],
        "medium": ["paid_social", "social", "cpc"],
    },
    "linkedin": {
        "source": ["linkedin", "linkedin_ads", "li"],
        "medium": ["paid_social", "social", "cpc", "sponsored"],
    },
    "pinterest": {
        "source": ["pinterest", "pin", "pinterest_ads"],
        "medium": ["paid_social", "social", "promoted_pin"],
    },
    "snapchat": {
        "source": ["snapchat", "snap", "snapchat_ads"],
        "medium": ["paid_social", "social"],
    },
    "reddit": {
        "source": ["reddit", "reddit_ads"],
        "medium": ["paid_social", "social", "cpc"],
    },
    "email": {
        "source": ["newsletter", "email", "broadcast"],
        "medium": ["email"],
    },
}


def pick_utm_variation(platform: str, brand: str = "") -> Tuple[str, str]:
    """Returns (utm_source, utm_medium) sampled from the platform's
    realistic variation pool. Empty platform → ("","")."""
    p = (platform or "").lower().strip()
    cfg = _UTM_VARIATIONS.get(p)
    if not cfg:
        return "", ""
    src = random.choice(cfg["source"])
    med = random.choice(cfg["medium"])
    if brand and p == "email":
        # Brand-aware: marketer's own newsletter source
        b = re.sub(r"[^a-z0-9]+", "_", brand.lower()).strip("_") or src
        src = f"{b}_newsletter"
    return src, med


# ──────────────────────────────────────────────────────────────────────
# J) fbclid / gclid embedded-timestamp realism
# ──────────────────────────────────────────────────────────────────────
# Real fbclid is base64url(<ms_timestamp>:<payload>). Real users coming
# from "today's ad" all have similar timestamps. Bulk RUT with random
# fbclid timestamps spread across last 1-7 days looks more organic.
def fbclid_with_realistic_timestamp(spread_days: int = 7) -> str:
    """Generate an fbclid whose embedded timestamp falls within the
    last `spread_days` days (heavier weighting on last 24h)."""
    # 70% within last 24h, 20% within 1-3 days, 10% within 3-7 days
    roll = random.random()
    now_ms = int(time.time() * 1000)
    if roll < 0.70:
        offset = random.randint(0, 24 * 3600 * 1000)
    elif roll < 0.90:
        offset = random.randint(24 * 3600 * 1000, 3 * 24 * 3600 * 1000)
    else:
        offset = random.randint(3 * 24 * 3600 * 1000,
                                max(3 * 24 * 3600 * 1000 + 1, spread_days * 24 * 3600 * 1000))
    ts = now_ms - offset
    # fbclid format: IwY2xjawF<base64url payload spanning ts + rand>
    payload = f"{ts}:{_rand_hash(32)}:{_rand_hash(16)}".encode()
    b64 = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    # Real fbclid starts with "IwY2xjawF" / "IwAR" / "IwY2xjawE"
    prefix = random.choice(["IwY2xjawF", "IwY2xjawE", "IwY2xjawG"])
    return prefix + b64[:max(60, 96 - len(prefix))]


def gclid_with_realistic_timestamp(spread_days: int = 7) -> str:
    """Real gclid is opaque but the same Google account's ads produce
    a clustered timestamp distribution. We mimic by using realistic
    length + Google's actual 3-prefix character set."""
    prefix = random.choice(["Cj0KCQ", "EAIaIQ", "Cj4KCQ", "CjwKCAi"])
    # Append base64url payload that includes a recent timestamp seed
    now_s = int(time.time())
    roll = random.random()
    if roll < 0.70:
        offset = random.randint(0, 86400)
    elif roll < 0.90:
        offset = random.randint(86400, 3 * 86400)
    else:
        offset = random.randint(3 * 86400, max(3 * 86400 + 1, spread_days * 86400))
    seed = now_s - offset
    body = base64.urlsafe_b64encode(f"{seed}{_rand_hash(20)}".encode()).decode().rstrip("=")
    return prefix + body[:60]


# ──────────────────────────────────────────────────────────────────────
# L) Network click-redirect chain (one optional 302 hop)
# ──────────────────────────────────────────────────────────────────────
_NETWORK_CLICK_HOSTS: Tuple[str, ...] = (
    "trk.affiliatenetwork.com",
    "click.mb01.com",
    "go.linksynergy.com",
    "click.linksynergy.com",
    "track.mb-pl.com",
    "tracker.gateway.com",
    "go.maxbcb.com",
    "afftrk.com",
    "tracking.glitchyads.com",
    "track.performcb.com",
    "go.performcb.com",
    "click.networkx.io",
)


def build_network_click_referer(network_host: Optional[str] = None) -> str:
    """Build a realistic affiliate-network 302-redirector Referer.
    Used as the Referer for the FINAL landing-page hit when
    `network_click_chain_enabled=True` on a job.
    """
    host = (network_host or random.choice(_NETWORK_CLICK_HOSTS)).strip()
    aff_id = random.randint(10000, 999999)
    offer_id = random.randint(1000, 99999)
    sub_id = "".join(random.choices("abcdef0123456789", k=16))
    return f"https://{host}/click.php?aff={aff_id}&offer={offer_id}&sub={sub_id}"


# ──────────────────────────────────────────────────────────────────────
# WEIGHTED platform-pool resolver
# ──────────────────────────────────────────────────────────────────────
# Accepts BOTH:
#   - Legacy comma-list "facebook,tiktok,instagram"  (equal weights)
#   - JSON dict          '{"facebook":40,"tiktok":30,"google":30}'
#
# The JSON path lets the UI ship a multi-select + per-platform %
# sliders. Engine auto-normalises whatever the user submits.
VALID_PLATFORM_KEYS = {
    "facebook", "instagram", "tiktok", "youtube", "twitter", "x",
    "snapchat", "pinterest", "reddit", "linkedin", "whatsapp",
    "telegram", "discord", "google", "bing", "duckduckgo", "yahoo",
    "yandex", "email",
}


def parse_weighted_pool(value: str) -> List[Tuple[str, float]]:
    """Parse a platform-pool field into [(platform, weight), …].

    Tolerates:
      - JSON object: {"facebook": 40, "tiktok": 30, …}
      - JSON array : [{"key":"facebook","weight":40}, …]
      - Comma-list : "facebook,tiktok,instagram"   (equal weight 1.0 each)

    Returns [] when nothing parseable. Caller picks weighted-random or
    falls back to legacy behaviour.
    """
    if not value:
        return []
    v = value.strip()
    out: List[Tuple[str, float]] = []
    try:
        if v.startswith("{") or v.startswith("["):
            data = json.loads(v)
            if isinstance(data, dict):
                for k, w in data.items():
                    key = str(k).strip().lower()
                    if key in VALID_PLATFORM_KEYS:
                        try:
                            wf = float(w)
                            if wf > 0:
                                out.append((key, wf))
                        except (TypeError, ValueError):
                            continue
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        key = str(item.get("key", "")).strip().lower()
                        w = item.get("weight", item.get("value", 0))
                        if key in VALID_PLATFORM_KEYS:
                            try:
                                wf = float(w)
                                if wf > 0:
                                    out.append((key, wf))
                            except (TypeError, ValueError):
                                continue
            return out
    except (json.JSONDecodeError, ValueError):
        pass

    # Legacy comma-list — equal weight
    for part in v.split(","):
        key = part.strip().lower()
        if key in VALID_PLATFORM_KEYS:
            out.append((key, 1.0))
    return out


def pick_weighted(pool: List[Tuple[str, float]]) -> str:
    """Weighted-random pick from [(key, weight), …]."""
    if not pool:
        return ""
    total = sum(max(0.0, w) for _, w in pool)
    if total <= 0:
        return random.choice([k for k, _ in pool])
    roll = random.random() * total
    acc = 0.0
    for key, w in pool:
        acc += max(0.0, w)
        if roll <= acc:
            return key
    return pool[-1][0]


# ──────────────────────────────────────────────────────────────────────
# WEIGHTED email-ESP resolver
# ──────────────────────────────────────────────────────────────────────
# Replaces the hard-coded 35/30/20/15 split. Customer can configure:
#   - Empty / native-mail-client %  (key "empty")
#   - Gmail webmail %               (key "gmail")
#   - Outlook webmail %             (key "outlook")
#   - Yahoo Mail webmail %          (key "yahoo")
#   - ProtonMail webmail %          (key "proton")
#   - Per-ESP weights:
#       mailchimp, sendgrid, klaviyo, hubspot, activecampaign,
#       convertkit, constantcontact, mailerlite, brevo, aweber,
#       drip, iterable, marketo, pardot
VALID_EMAIL_KEYS = {
    "empty", "gmail", "outlook", "yahoo", "proton",
    "mailchimp", "sendgrid", "klaviyo", "hubspot", "activecampaign",
    "convertkit", "constantcontact", "mailerlite", "brevo", "aweber",
    "drip", "iterable", "marketo", "pardot",
}

# Extended ESP click-tracking hosts (mirrors real-world redirector domains)
EXTENDED_ESP_HOSTS: Dict[str, List[str]] = {
    "mailchimp":       ["https://us21.list-manage.com/", "https://us2.list-manage.com/",
                        "https://us10.list-manage.com/", "https://us6.list-manage.com/",
                        "https://email.mailchimp.com/", "https://mailchi.mp/"],
    "sendgrid":        ["https://email.sendgrid.com/", "https://u17.sendgrid.com/",
                        "https://u4334.sendgrid.com/", "https://email.sendgrid.net/"],
    "klaviyo":         ["https://email.klaviyomail.com/", "https://trk.klaviyomail.com/",
                        "https://e.klaviyo.com/"],
    "hubspot":         ["https://hs-links.com/", "https://email.hubspot.net/",
                        "https://hs-sites.com/", "https://t.hubspotemail.net/"],
    "activecampaign":  ["https://activehosted.com/", "https://t.activehosted.com/",
                        "https://email.activecampaign.com/"],
    "convertkit":      ["https://email.convertkit.com/", "https://cl.convertkit-mail.com/",
                        "https://pages.convertkit.com/"],
    "constantcontact": ["https://r20.rs6.net/", "https://ccprod.constantcontact.com/",
                        "https://t.constantcontact.com/"],
    "mailerlite":      ["https://email.mailerlite.com/", "https://t.mailerlite.com/",
                        "https://click.mailerlite.com/"],
    "brevo":           ["https://email.brevo.com/", "https://r.brevo.com/",
                        "https://email.sendinblue.com/"],
    "aweber":          ["https://email.aweber.com/", "https://send.aweber.com/"],
    "drip":            ["https://email.drip.com/", "https://t.drip.com/"],
    "iterable":        ["https://links.iterable.com/", "https://email.iterable.com/"],
    "marketo":         ["https://email.marketo.com/", "https://go.marketo.com/"],
    "pardot":          ["https://email.pardot.com/", "https://go.pardot.com/"],
}

WEBMAIL_REFERERS: Dict[str, str] = {
    "gmail":   "https://mail.google.com/",
    "outlook": "https://outlook.live.com/",
    "yahoo":   "https://mail.yahoo.com/",
    "proton":  "https://mail.proton.me/",
}

# Default 2025-26 distribution (used when user does NOT configure weights)
DEFAULT_EMAIL_WEIGHTS: Dict[str, float] = {
    "empty": 35.0,
    "gmail": 20.0,
    "outlook": 15.0,
    "mailchimp": 8.0,
    "klaviyo": 5.0,
    "sendgrid": 4.0,
    "hubspot": 3.0,
    "activecampaign": 2.0,
    "convertkit": 2.0,
    "constantcontact": 2.0,
    "mailerlite": 1.5,
    "brevo": 1.0,
    "aweber": 0.5,
    "drip": 0.5,
    "iterable": 0.3,
    "marketo": 0.1,
    "pardot": 0.1,
}


def parse_email_weights(value: str) -> Dict[str, float]:
    """Parse the email-pool weight field. Accepts:
      - JSON dict: '{"empty":40, "gmail":20, "mailchimp":15, ...}'
      - Empty / invalid → DEFAULT_EMAIL_WEIGHTS
    """
    if not value:
        return dict(DEFAULT_EMAIL_WEIGHTS)
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            cleaned: Dict[str, float] = {}
            for k, w in data.items():
                key = str(k).strip().lower()
                if key in VALID_EMAIL_KEYS:
                    try:
                        wf = float(w)
                        if wf > 0:
                            cleaned[key] = wf
                    except (TypeError, ValueError):
                        continue
            if cleaned:
                return cleaned
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return dict(DEFAULT_EMAIL_WEIGHTS)


def resolve_email_visit_weighted(weights: Dict[str, float]) -> Tuple[str, str, str]:
    """Email-source resolver using user-defined per-bucket weights.
    Returns (referer_url, "email", esp_key_or_empty).
    """
    if not weights:
        weights = dict(DEFAULT_EMAIL_WEIGHTS)
    items = list(weights.items())
    total = sum(max(0.0, w) for _, w in items)
    if total <= 0:
        return "", "email", ""

    roll = random.random() * total
    acc = 0.0
    chosen = items[-1][0]
    for k, w in items:
        acc += max(0.0, w)
        if roll <= acc:
            chosen = k
            break

    if chosen == "empty":
        return "", "email", ""
    if chosen in WEBMAIL_REFERERS:
        return WEBMAIL_REFERERS[chosen], "email", ""
    # Otherwise it's an ESP click-tracking host
    hosts = EXTENDED_ESP_HOSTS.get(chosen) or [""]
    return random.choice(hosts), "email", chosen


# ──────────────────────────────────────────────────────────────────────
# I) Time-of-day platform pacing weights (placeholder helper)
# ──────────────────────────────────────────────────────────────────────
# Returns a multiplier for the current local hour (0-23) per platform.
# Pacing engine in real_user_traffic.py can sample weighted ETA shifts.
_HOUR_WEIGHTS: Dict[str, List[float]] = {
    # 0  1  2  3  4  5   6   7   8   9   10  11  12  13  14  15  16  17  18  19  20  21  22  23
    "facebook":  [0.4,0.3,0.2,0.2,0.2,0.3,0.4,0.6,0.8,0.9,1.0,1.1,1.3,1.2,1.0,0.9,0.9,1.0,1.2,1.4,1.5,1.4,1.0,0.6],
    "instagram": [0.5,0.4,0.3,0.2,0.2,0.3,0.4,0.6,0.8,0.9,1.0,1.1,1.2,1.1,1.0,1.0,1.1,1.2,1.4,1.6,1.7,1.5,1.1,0.7],
    "tiktok":    [0.4,0.4,0.3,0.2,0.2,0.2,0.3,0.4,0.6,0.7,0.8,0.9,1.0,1.0,0.9,0.9,1.0,1.2,1.5,1.8,2.0,1.9,1.5,0.9],
    "linkedin":  [0.1,0.1,0.1,0.1,0.1,0.2,0.4,0.8,1.4,1.7,1.8,1.7,1.4,1.5,1.6,1.5,1.3,1.0,0.6,0.4,0.3,0.2,0.2,0.1],
    "google":    [0.5,0.4,0.3,0.3,0.3,0.4,0.6,0.9,1.2,1.4,1.5,1.5,1.4,1.4,1.4,1.3,1.2,1.1,1.0,0.9,0.8,0.7,0.6,0.5],
    "youtube":   [0.5,0.4,0.3,0.3,0.3,0.3,0.4,0.6,0.8,0.9,1.0,1.1,1.2,1.2,1.1,1.1,1.2,1.3,1.5,1.7,1.8,1.6,1.2,0.7],
    "email":     [0.3,0.2,0.2,0.2,0.2,0.3,0.5,0.8,1.2,1.5,1.6,1.4,1.2,1.3,1.4,1.3,1.1,1.0,0.9,1.0,1.2,1.0,0.7,0.4],
}


def time_of_day_weight(platform: str, hour: Optional[int] = None) -> float:
    """Return realism multiplier (0.1-2.0) for the platform at this hour.
    Pacing engine can multiply its base inter-arrival rate by this so
    TikTok traffic peaks evening, LinkedIn peaks business hours, etc.
    Falls back to 1.0 for unknown platforms.
    """
    p = (platform or "").lower()
    if p not in _HOUR_WEIGHTS:
        return 1.0
    if hour is None:
        hour = datetime.now(timezone.utc).hour
    try:
        return float(_HOUR_WEIGHTS[p][int(hour) % 24])
    except (IndexError, ValueError):
        return 1.0


# ──────────────────────────────────────────────────────────────────────
# Top-level resolver: pro-mode (weighted) referrer pick
# ──────────────────────────────────────────────────────────────────────
def resolve_pro_visit(
    *,
    ua: str = "",
    platform_pool_value: str = "",
    email_weights_value: str = "",
    brand: str = "",
    target_url: str = "",
    country: Optional[str] = None,
    search_engine: str = "google",
    search_keywords: str = "",
    social_wrapper_enabled: bool = True,
    inapp_deep_path_enabled: bool = True,
    strip_search_path: bool = True,
    network_click_chain_enabled: bool = False,
    network_click_host: Optional[str] = None,
) -> Dict[str, Any]:
    """Top-level pro-mode resolver — returns a dict with everything the
    engine needs for ONE visit:
        {
          "referer": "...",
          "platform": "...",
          "esp": "...",
          "sec_fetch": {...},
          "utm_source": "...",
          "utm_medium": "...",
          "network_click_referer": "..." (when chain enabled),
        }
    """
    out: Dict[str, Any] = {
        "referer": "", "platform": "", "esp": "",
        "sec_fetch": {}, "utm_source": "", "utm_medium": "",
        "network_click_referer": "",
    }

    pool = parse_weighted_pool(platform_pool_value)
    if not pool:
        return out

    chosen = pick_weighted(pool)
    if not chosen:
        return out

    # Normalise "x" → "twitter" for downstream signal matching
    signal = "twitter" if chosen == "x" else chosen

    # Email path: use weighted ESP/webmail resolver
    if chosen == "email":
        weights = parse_email_weights(email_weights_value)
        ref, plat, esp = resolve_email_visit_weighted(weights)
        out["referer"] = ref
        out["platform"] = plat
        out["esp"] = esp
        out["utm_source"], out["utm_medium"] = pick_utm_variation("email", brand)
        out["sec_fetch"] = build_sec_fetch_headers(ref, is_navigation=True)
        return out

    # Search engines (google / bing / yahoo / duckduckgo / yandex / youtube / baidu / naver)
    if chosen in ("google", "bing", "duckduckgo", "yahoo", "yandex"):
        # If pool entry maps to search, use the user's chosen search engine
        kws = [ln.strip() for ln in (search_keywords or "").splitlines() if ln.strip()]
        kw = random.choice(kws) if kws else ""
        # Use chosen as the actual engine — not the search_engine override —
        # so per-visit rotation across engines works inside the same pool.
        eng = chosen if chosen != "duckduckgo" else "duckduckgo"
        ref = build_search_referer(eng, kw, country=country, strip_path=strip_search_path)
        out["referer"] = ref
        out["platform"] = signal
        out["utm_source"], out["utm_medium"] = pick_utm_variation(signal, brand)
        out["sec_fetch"] = build_sec_fetch_headers(ref, is_navigation=True)
        return out

    # Social: pick wrapper or in-app deep path
    ref = ""
    if inapp_deep_path_enabled:
        inapp_kind = is_inapp_browser_ua(ua)
        if inapp_kind == signal:
            ref = build_inapp_deep_referer(signal)

    if not ref and social_wrapper_enabled:
        ref = build_social_wrapper_referer(signal, target_url)

    if not ref:
        # Final fallback: bare homepage
        from urllib.parse import urlparse as _up
        # Pool-level homepage — kept inline to avoid coupling
        homepages = {
            "facebook":   "https://www.facebook.com/",
            "instagram":  "https://www.instagram.com/",
            "tiktok":     "https://www.tiktok.com/",
            "youtube":    "https://www.youtube.com/",
            "twitter":    "https://twitter.com/",
            "snapchat":   "https://www.snapchat.com/",
            "pinterest":  "https://www.pinterest.com/",
            "reddit":     "https://www.reddit.com/",
            "linkedin":   "https://www.linkedin.com/",
            "whatsapp":   "",
            "telegram":   "",
            "discord":    "",
        }
        ref = homepages.get(signal, "")

    out["referer"] = ref
    out["platform"] = signal
    out["utm_source"], out["utm_medium"] = pick_utm_variation(signal, brand)
    out["sec_fetch"] = build_sec_fetch_headers(ref, is_navigation=True)

    # Network click chain (one optional 302 hop)
    if network_click_chain_enabled:
        out["network_click_referer"] = build_network_click_referer(network_click_host)

    return out


__all__ = [
    # Resolvers
    "resolve_pro_visit",
    "resolve_email_visit_weighted",
    "parse_weighted_pool",
    "parse_email_weights",
    "pick_weighted",
    # Builders
    "build_search_referer",
    "build_social_wrapper_referer",
    "build_inapp_deep_referer",
    "build_sec_fetch_headers",
    "build_network_click_referer",
    # Geo + UTM
    "get_geo_search_hosts",
    "pick_utm_variation",
    "time_of_day_weight",
    # IDs
    "fbclid_with_realistic_timestamp",
    "gclid_with_realistic_timestamp",
    "is_inapp_browser_ua",
    # Constants
    "VALID_PLATFORM_KEYS",
    "VALID_EMAIL_KEYS",
    "DEFAULT_EMAIL_WEIGHTS",
    "EXTENDED_ESP_HOSTS",
    "WEBMAIL_REFERERS",
]
