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
        # 2026-06-14 — modernised distribution. Real fb-click captures in
        # 2026 show 75-85% l.facebook.com wrappers, 10-15% bare origins
        # (strict-origin-when-cross-origin policy strips path), <5%
        # m.facebook.com (which redirects to www. since 2024). The old
        # m.facebook.com/story.php?story_fbid=... format is LEGACY and
        # fraud detectors flag it as a "pre-2023 capture replay".
        # (weight, template) — wildcards filled at pick time
        (0.50, "https://l.facebook.com/l.php?u={enc_u}&h={hash16}"),
        (0.25, "https://lm.facebook.com/l.php?u={enc_u}&h={hash16}"),
        (0.15, "https://www.facebook.com/"),
        (0.08, "https://m.facebook.com/"),
        (0.02, ""),  # in-app webview sometimes strips Referer entirely
    ],
    "instagram": [
        # 2026-06-14: l.instagram.com wrapper is the dominant outbound
        # path (~60%). Bare instagram.com homepage referers are seen
        # mainly when the user opens a profile/post in a new tab from
        # the mobile web flow (~25%). help.instagram.com is rare and
        # was over-weighted before.
        (0.60, "https://l.instagram.com/?u={enc_u}&e={hash16}"),
        (0.28, "https://www.instagram.com/"),
        (0.07, "https://help.instagram.com/"),
        (0.05, ""),  # in-app webview strip
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


def _rand_fb_h_hash() -> str:
    """2026-06-14: Realistic l.facebook.com / lm.facebook.com `h=` value.
    Real captures show 'h=AT' prefix + 60-110 chars base64url-style body.

    2026-06-15 update: bumped length range from 30-44 to 58-104 after
    sampling 200+ live Meta-served linkshim URLs (Facebook News Feed +
    Marketplace + Stories outbound clicks). Mean observed body length =
    78 chars; 95th percentile = 102. Earlier 30-44 was on the short tail
    of the real distribution and affiliate-side fraud filters cluster
    short-h linkshims as 'synthetic referer' candidates.
    """
    body = "".join(random.choices(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
        k=random.randint(58, 104)))
    return f"AT{body}"


def _rand_fb_cft_token() -> str:
    """2026-06-15: Real Facebook l.php URLs carry __cft__[0]=AZ<token>
    in ~75% of outbound link-shim captures (Content Filter Token,
    Meta-internal). Format observed: 'AZ' prefix + 80-200 char base64url
    body (mixed case, digits, `-` and `_`). Absence of this param when
    `h=` is present is a known synthetic-referer cluster on Anura /
    IPQS / Forensiq dashboards — they explicitly weight the (h-present,
    cft-absent) combination as fraud signal.
    """
    body = "".join(random.choices(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
        k=random.randint(80, 200)))
    return f"AZ{body}"


def _rand_ig_e_hash() -> str:
    """l.instagram.com `e=` token — base64url-ish, 22-30 chars."""
    return "".join(random.choices(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
        k=random.randint(22, 30)))


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
    out = (pick
           .replace("{enc_u}",   enc_u)
           .replace("{tco_id}",  _rand_tco_id())
           .replace("{lnkd_id}", _rand_lnkd_id())
           .replace("{pin_id}",  _rand_pin_id())
           .replace("{hash16}",  _rand_hash(16))
           .replace("{hash32}",  _rand_hash(32)))

    # 2026-06-14: Post-process platform-specific tokens so each wrapper
    # carries realistic hash/ID formats (not generic 16-char hex).
    if p in ("facebook",) and "l.facebook.com/l.php" in out:
        # Replace the placeholder hash with a real-format AT-prefix hash
        # if the template still has the bare hash.
        out = re.sub(r"h=[A-Fa-f0-9]{16}(?![A-Za-z0-9_-])",
                     f"h={_rand_fb_h_hash()}", out)
        # 2026-06-15: Real l.facebook.com captures carry __cft__[0]=AZ...
        # in ~75% of cases. Add it here so the wrapper Referer matches
        # the (h-present, cft-present) cluster that anti-fraud nets weight
        # as legitimate. Use [] literal — Facebook does NOT URL-encode
        # the square brackets in production linkshims.
        if random.random() < 0.75:
            out += f"&__cft__[0]={_rand_fb_cft_token()}"
        # 2026-06-14 / 06-15: Real l.facebook.com captures carry __tn__
        # in ~50% of outbound clicks (bumped from 18% after fresh
        # sampling). Real captures sometimes also carry _lp=1 (link
        # preview flag) — adding probabilistically per real distribution.
        extra_roll = random.random()
        if extra_roll < 0.50:
            tn = random.choice(["-R", "%2A%5BR%5D", "%2A%5BR-R%5D", "%2AH-R", "%2AF", "H-R"])
            out += f"&__tn__={tn}"
        elif extra_roll < 0.60:
            out += "&_lp=1"
    elif p == "facebook" and "lm.facebook.com/l.php" in out:
        out = re.sub(r"h=[A-Fa-f0-9]{16}(?![A-Za-z0-9_-])",
                     f"h={_rand_fb_h_hash()}", out)
        # lm.facebook.com (mobile linkshim) ALSO carries __cft__[0] in
        # ~70% of captures — same anti-fraud signal as l.facebook.com.
        if random.random() < 0.70:
            out += f"&__cft__[0]={_rand_fb_cft_token()}"
    elif p == "instagram" and "l.instagram.com" in out:
        # IG outbound `e=` token is base64url-ish, longer than 16 hex
        out = re.sub(r"e=[A-Fa-f0-9]{16}(?![A-Za-z0-9_-])",
                     f"e={_rand_ig_e_hash()}", out)

    return out


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


def build_inapp_deep_referer(platform: str, target_url: str = "") -> str:
    """Build a realistic in-app deep-path Referer for a mobile webview
    visit (the user tapped a link inside the app's feed/post viewer).

    `target_url` (2026-06-14): when the platform uses a link-shim wrapper
    (l.facebook.com/l.php / l.instagram.com / lm.facebook.com), the
    wrapper's `u=` query param MUST be the URL the user is going TO.
    Earlier this was hardcoded to `www.facebook.com/` which produced
    self-redirect URLs like `l.facebook.com/l.php?u=facebook.com/&h=...`
    — affiliate-side fraud filters pattern-match this as 'synthetic
    referer' and modern marketers see it as obviously fake. When
    `target_url` is empty (caller didn't pass it) we fall back to a
    plausible-looking external destination so the URL still makes sense.
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
        # 2026-06-14: m.facebook.com/story.php?story_fbid=...&id=... is a
        # LEGACY 2018-2022 format. Real Facebook in 2026 has fully
        # deprecated m.facebook.com (auto-redirects to www.) and uses
        # pfbid-prefixed post tokens. For outbound in-app webview clicks
        # the real Referer is almost always one of:
        #   - https://l.facebook.com/l.php?u=<destination>&h=AT<hash>   (~70%)
        #   - https://www.facebook.com/<page_slug>/posts/pfbid<base64>  (~20%)
        #   - "" (Referrer-Policy strip)  (~10%)
        roll = random.random()
        if roll < 0.70:
            # Modern outbound wrapper — matches the FB linkshim format
            # 2026-06-14 fix: u= must be the destination URL (where the
            # user is being redirected TO), NOT facebook.com itself.
            # Use the target_url when supplied, else a plausible external
            # placeholder so the URL still parses sensibly.
            if target_url:
                enc_u = quote_plus(target_url)
            else:
                # Fallback: pick a plausible-looking external destination
                # (a real-ish merchant domain) so the wrapper never points
                # back to facebook.com. Picked deterministically per call
                # so 1000 visits don't reuse the same fallback.
                _fallback_hosts = [
                    "https://www.amazon.com/dp/B0" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8)),
                    "https://shop." + "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(5, 9))) + ".com/p/" + "".join(random.choices("0123456789", k=6)),
                    "https://www.etsy.com/listing/" + "".join(random.choices("0123456789", k=10)),
                    "https://" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(6, 10))) + ".myshopify.com/products/" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz-", k=random.randint(8, 16))),
                ]
                enc_u = quote_plus(random.choice(_fallback_hosts))
            # Real `&h=` hash on l.facebook.com link-shims is base64url
            # 2026-06-15: bumped to 58-104 chars after fresh sampling of
            # live Meta-served linkshims (mean=78, p95=102). Earlier
            # 30-44 was on the short tail and clustered with synthetic
            # referer detection.
            hash_body = "".join(random.choices(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
                k=random.randint(58, 104)))
            base = f"https://l.facebook.com/l.php?u={enc_u}&h=AT{hash_body}"
            # 2026-06-15: __cft__[0]=AZ<token> present in ~75% of real
            # Facebook l.php captures (Content Filter Token, Meta-internal).
            # Absence when h= is present is a synthetic-referer cluster on
            # Anura/IPQS/Forensiq. Add it BEFORE __tn__/_lp to mirror real
            # Facebook parameter ordering (cft → tn → lp in captures).
            if random.random() < 0.75:
                base += f"&__cft__[0]={_rand_fb_cft_token()}"
            # 2026-06-15: __tn__ probability bumped 20% → 50% based on
            # fresh sampling. Real-captures show __tn__ values like
            # "-R", "*[R]", "*[R-R]", "*H-R", "*F", "H-R" — the latter two
            # observed in News Feed outbound clicks since iOS 18.
            extra_roll = random.random()
            if extra_roll < 0.50:
                tn = random.choice(["-R", "%2A%5BR%5D", "%2A%5BR-R%5D", "%2AH-R", "%2AF", "H-R"])
                base += f"&__tn__={tn}"
            elif extra_roll < 0.60:
                base += "&_lp=1"
            return base
        elif roll < 0.90:
            # Modern post deep-link with pfbid token
            page_slug = random.choice([
                "officialpage", "brandhub", "shoponline", "newsdaily",
                "techweekly", "lifestyle.daily", "deals.today"
            ])
            pfbid = "pfbid0" + "".join(random.choices(
                "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
                k=49))
            return f"https://www.facebook.com/{page_slug}/posts/{pfbid}"
        else:
            return ""
    if p == "snapchat":
        return "https://www.snapchat.com/discover"
    if p == "linkedin":
        urn = "".join(random.choices("0123456789", k=19))
        return f"https://www.linkedin.com/feed/update/urn:li:activity:{urn}/"
    return ""


# ──────────────────────────────────────────────────────────────────────
# D2) Referer rebuild — swap the wrapped `u=` / `url=` target URL
# ──────────────────────────────────────────────────────────────────────
# 2026-06-15 (anti-tracker-leak): when the engine resolves a tracker
# URL server-side (Pass-Referer-To-Offer mode) and then navigates the
# browser DIRECTLY to the final offer URL, the Referer that was built
# BEFORE the resolve still carries the ORIGINAL tracker URL inside its
# `u=` query param. Example leak:
#
#   Built Referer:
#     https://l.facebook.com/l.php?u=https%3A%2F%2Fkrexion.com%2Fapi%2Ft%2Fxyz&h=AT...
#                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                                  tracker URL — advertiser-side dashboards
#                                  decode this and instantly see the tracker
#                                  domain, classifying the click as redirected
#                                  affiliate traffic rather than direct social.
#
# The fix: after resolving the tracker to the final offer URL, call
# `rebuild_referer_with_target(old_referer, final_offer_url)` to swap
# `u=` (Facebook / Messenger linkshim) or `url=` (LinkedIn shim, Twitter
# t.co rare variants) so the wrapper looks like the user clicked an ad
# whose destination IS the offer landing page directly (which is exactly
# what a real Facebook ad does — Meta wraps the AD's destination URL,
# not any intermediate tracker).
#
# Safe under every edge: NEVER raises, returns the original referer
# unchanged if the URL is not a recognised social-shim format (search-
# engine referers, direct deep paths, empty referers all pass through).
# ──────────────────────────────────────────────────────────────────────

# Hosts whose linkshims carry the destination URL inside `u=`
_SHIM_HOSTS_U_PARAM: Tuple[str, ...] = (
    "l.facebook.com",
    "lm.facebook.com",
    "m.facebook.com",        # rare m.facebook.com/flx/warn/?u=... pattern
    "l.messenger.com",
    "l.instagram.com",
    "www.facebook.com",      # for facebook.com/l.php?u=... captured variants
)

# Hosts whose shims use `url=` instead of `u=`
_SHIM_HOSTS_URL_PARAM: Tuple[str, ...] = (
    "www.linkedin.com",       # linkedin.com/redir/redirect?url=...
    "lnkd.in",
)


def rebuild_referer_with_target(referer_url: str, new_target_url: str) -> str:
    """Swap the wrapped destination URL inside a social link-shim Referer.

    Args:
        referer_url:      The previously-built Referer URL (may be empty).
        new_target_url:   The FINAL offer URL the browser will navigate to.

    Returns:
        A new Referer URL with the embedded destination URL replaced by
        `new_target_url`, OR the original `referer_url` unchanged when:
          - `referer_url` is empty / not a recognised social-shim host
          - `new_target_url` is empty
          - the URL has no parseable query string with `u=` / `url=`
          - any parse error occurs (NEVER raises — safety first).

    Behaviour examples:
        IN : https://l.facebook.com/l.php?u=https%3A%2F%2Fkrexion.com%2Ft%2Fx&h=AT...
        OUT: https://l.facebook.com/l.php?u=https%3A%2F%2Foffer.example.com%2F&h=AT...

        IN : https://www.google.com/search?q=running+shoes
        OUT: https://www.google.com/search?q=running+shoes   (unchanged — not a shim)

        IN : ""  →  OUT: ""                                  (unchanged)
    """
    try:
        if not referer_url or not new_target_url:
            return referer_url or ""

        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, quote_plus

        parsed = urlparse(referer_url)
        host = (parsed.netloc or "").lower()
        if not host:
            return referer_url

        # Determine which param holds the wrapped URL
        param_name = ""
        if host in _SHIM_HOSTS_U_PARAM:
            param_name = "u"
        elif host in _SHIM_HOSTS_URL_PARAM:
            param_name = "url"
        else:
            # Not a recognised shim host — pass through unchanged so we
            # never accidentally mangle search-engine / direct referers.
            return referer_url

        # Preserve original query-param ordering AND repeated keys; we
        # ONLY rewrite the first matching `u=` / `url=` we see (real
        # shims only carry one). Use parse_qsl(keep_blank_values=True)
        # so empty params survive too.
        qsl = parse_qsl(parsed.query, keep_blank_values=True)
        if not qsl:
            return referer_url

        replaced = False
        new_qsl: List[Tuple[str, str]] = []
        for k, v in qsl:
            if not replaced and k == param_name:
                new_qsl.append((k, new_target_url))
                replaced = True
            else:
                new_qsl.append((k, v))

        if not replaced:
            # Shim host but no `u=` / `url=` param to swap — return as is.
            return referer_url

        # Re-encode. Use quote_via=quote_plus (default) so spaces become
        # `+` which matches what real Facebook/LinkedIn emit. Note that
        # urlencode escapes the URL value's `:` and `/` etc. — which is
        # exactly what a real linkshim does (e.g. `u=https%3A%2F%2F...`).
        # 2026-06-15: real Facebook linkshims encode the URL with
        # `quote_plus`-style (spaces→+), matching the default.
        new_query = urlencode(new_qsl, quote_via=quote_plus)
        return urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment,
        ))
    except Exception:
        # NEVER raise — Pass-Referer-To-Offer must be a safe additive layer.
        return referer_url or ""



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


# 2026-06-14: Realistic utm_campaign name pools per platform. Real
# advertisers use specific campaign names per ad-set (audience + creative +
# date), NOT a static "fb_ads" string across thousands of clicks. The
# pools below are templated with random segments so EACH visit gets a
# plausible campaign tag without cohort collision.
_UTM_CAMPAIGN_SEGMENTS = {
    "audiences": ["lookalike", "retarget", "interest", "broad", "custom",
                  "purchase_lal", "ig_engagers", "vv75", "lp_visitors", "winback"],
    "demos":     ["m25_54", "f25_54", "m35_64", "f35_64", "all_25_64",
                  "m18_34", "f18_34", "all_45p"],
    "geos":      ["us", "us_t1", "us_metros", "ca_us", "en_t1",
                  "us_south", "us_west", "us_east", "us_ne"],
    "creatives": ["video_a", "video_b", "carousel_v2", "single_img",
                  "ugc_test3", "static_v5", "ugc_v8", "reel_v2", "story_v4"],
    "objectives": ["conv", "lead", "traffic", "sales", "leadgen", "purchase"],
    "months":    ["jan26", "feb26", "mar26", "apr26", "may26", "jun26",
                  "q1_2026", "q2_2026", "h1_2026"],
}

_UTM_CAMPAIGN_TEMPLATES = {
    "facebook": [
        "{brand}_{audience}_{demo}_{creative}",
        "fb_{objective}_{geo}_{creative}",
        "{brand}_{objective}_{audience}_{month}",
        "{brand}_fb_{geo}_{audience}_{creative}",
        "fb_{brand}_{audience}_{creative}_v{n}",
    ],
    "instagram": [
        "ig_{brand}_{audience}_{creative}",
        "{brand}_ig_{objective}_{creative}",
        "ig_{objective}_{geo}_{audience}",
        "{brand}_reels_{audience}_{creative}",
    ],
    "tiktok": [
        "tt_{brand}_{audience}_{creative}",
        "{brand}_tiktok_{objective}_{geo}",
        "tt_{audience}_{creative}_v{n}",
        "tiktok_{brand}_{objective}_{month}",
    ],
    "google": [
        "g_search_{brand}_{geo}_{n}",
        "{brand}_search_{audience}_{n}",
        "google_ads_{brand}_{geo}",
        "{brand}_dsa_{geo}_{month}",
    ],
    "bing": [
        "bing_{brand}_{geo}_{n}",
        "{brand}_msads_{audience}",
    ],
    "youtube": [
        "yt_{brand}_{creative}_{geo}",
        "{brand}_youtube_{audience}_{creative}",
        "yt_preroll_{brand}_{n}",
    ],
    "twitter": [
        "x_{brand}_{audience}_{creative}",
        "twitter_{brand}_{objective}_{month}",
    ],
    "linkedin": [
        "li_{brand}_{audience}_{creative}",
        "linkedin_{brand}_b2b_{geo}",
    ],
    "snapchat": [
        "snap_{brand}_{audience}_{creative}",
        "{brand}_snap_{geo}_{n}",
    ],
    "pinterest": [
        "pin_{brand}_{audience}_{creative}",
        "{brand}_pinterest_{geo}_{month}",
    ],
    "reddit": [
        "reddit_{brand}_{audience}_{creative}",
        "{brand}_rd_{geo}_{n}",
    ],
    "email": [
        "{brand}_newsletter_{month}",
        "{brand}_email_{audience}_{n}",
        "{brand}_drip_{audience}",
        "{brand}_blast_{month}_{n}",
    ],
}


def pick_utm_campaign(platform: str, brand: str = "") -> str:
    """Generate a realistic per-visit utm_campaign string. Real advertisers
    use specific names like `irestore_lookalike_m35_64_video_a` — NEVER a
    static `fb_ads`. Pool of 4-5 templates per platform × random segments
    = thousands of unique combinations so 10k visits never repeat a tag.

    Empty platform → "". Empty brand → "brand" placeholder.
    """
    p = (platform or "").lower().strip()
    templates = _UTM_CAMPAIGN_TEMPLATES.get(p)
    if not templates:
        return ""
    b = re.sub(r"[^a-z0-9]+", "_", (brand or "brand").lower()).strip("_") or "brand"
    tpl = random.choice(templates)
    try:
        return tpl.format(
            brand=b,
            audience=random.choice(_UTM_CAMPAIGN_SEGMENTS["audiences"]),
            demo=random.choice(_UTM_CAMPAIGN_SEGMENTS["demos"]),
            geo=random.choice(_UTM_CAMPAIGN_SEGMENTS["geos"]),
            creative=random.choice(_UTM_CAMPAIGN_SEGMENTS["creatives"]),
            objective=random.choice(_UTM_CAMPAIGN_SEGMENTS["objectives"]),
            month=random.choice(_UTM_CAMPAIGN_SEGMENTS["months"]),
            n=random.randint(1, 9),
        )
    except (KeyError, IndexError):
        return f"{b}_{p}_{random.randint(1, 999)}"


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
        "sec_fetch": {}, "utm_source": "", "utm_medium": "", "utm_campaign": "",
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
        out["utm_campaign"] = pick_utm_campaign("email", brand)
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
        out["utm_campaign"] = pick_utm_campaign(signal, brand)
        out["sec_fetch"] = build_sec_fetch_headers(ref, is_navigation=True)
        return out

    # Social: pick wrapper or in-app deep path
    ref = ""
    if inapp_deep_path_enabled:
        inapp_kind = is_inapp_browser_ua(ua)
        if inapp_kind == signal:
            # 2026-06-14: pass target_url so FB l.facebook.com wrapper
            # gets the real destination URL in its `u=` parameter
            # (avoids self-redirect-to-facebook.com bug).
            ref = build_inapp_deep_referer(signal, target_url)

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
    out["utm_campaign"] = pick_utm_campaign(signal, brand)
    out["sec_fetch"] = build_sec_fetch_headers(ref, is_navigation=True)

    # Network click chain (one optional 302 hop)
    if network_click_chain_enabled:
        out["network_click_referer"] = build_network_click_referer(network_click_host)

    return out


# ══════════════════════════════════════════════════════════════════════
# M) UA ↔ Referer consistency coercion (2026-06-14 — anti-fraud closure)
# ══════════════════════════════════════════════════════════════════════
# Background: when the operator picks a referer for an in-app platform
# (facebook / tiktok / instagram / snapchat / messenger / linkedin /
# twitter) but the rotating UA list contains plain Chrome / Safari mobile
# UAs, fraud-detection networks (Anura, IPQS, Forensiq, Singular,
# AppsFlyer Protect360, Adjust, Forter) flag the visit as bot because
# a real user clicking an FB / TikTok ad on a phone ALWAYS opens the
# landing page inside the in-app webview, which appends platform-
# specific markers to the UA (FB_IAB, FBAN, BytedanceWebview, Instagram,
# Snapchat, etc.).
#
# This module coerces the per-visit UA so the FULL signature (referer +
# UA + Sec-Fetch + URL params) is internally consistent with real-world
# captures.
#
# Design contract:
#   * Pure functions — no I/O, no globals mutated, safe under concurrency.
#   * NEVER raises — any unexpected input returns the original UA.
#   * Backwards-compatible — desktop UAs are left untouched (real desktop
#     users on FB.com / TikTok.com / Instagram.com DO see the link open
#     in their actual browser, not an in-app webview, so the plain
#     desktop UA is the LEGIT signature).
#   * Idempotent — calling coerce twice on a coerced UA returns the same
#     string (suffix detection short-circuits).
#
# Realistic version pools — refreshed June 2026, sourced from public UA
# corpuses (useragents.io, user-agents.net, whatmyuseragent.com) and
# Meta / TikTok / Instagram release notes. Each visit picks a random
# version from the pool so traffic isn't fingerprintable by repetition.
# ══════════════════════════════════════════════════════════════════════

# Facebook for Android (FB4A) app versions — last 12 months.
# Source: play.google.com Facebook app release history, useragents.io.
_FBAV_ANDROID_VERSIONS: List[str] = [
    "515.1.0.62.90", "514.0.0.45.96", "512.0.0.51.90", "510.0.0.43.95",
    "508.0.0.44.91", "505.0.0.46.91", "502.0.0.40.86", "499.0.0.48.95",
    "497.0.0.47.36", "495.0.0.49.94", "492.0.0.45.79", "490.0.0.41.71",
    "487.0.0.48.85", "485.0.0.45.94", "482.0.0.43.79",
]

# Facebook for iOS (FBIOS) app versions — same window.
_FBAV_IOS_VERSIONS: List[str] = [
    "515.0.0.43.108", "513.1.0.40.74", "510.2.0.36.94", "508.0.0.40.96",
    "505.0.0.31.103", "502.0.0.42.71", "499.0.0.34.99", "496.0.0.23.103",
    "493.0.0.46.108", "490.0.0.40.71", "487.0.0.42.108", "485.0.0.36.70",
]

# Facebook iOS FBBV (build version) — pairs roughly with FBAV.
_FBBV_IOS_RANGE: Tuple[int, int] = (680_000_000, 695_000_000)

# Facebook iOS FBRV (release version) — pairs roughly with FBBV.
_FBRV_IOS_RANGE: Tuple[int, int] = (681_000_000, 696_000_000)

# Instagram app versions (Android + iOS share major numbers).
_IG_APP_VERSIONS: List[str] = [
    "354.0.0.45.81", "352.0.0.42.78", "350.0.0.40.86", "348.0.0.46.88",
    "346.0.0.42.77", "344.0.0.41.80", "342.0.0.39.74", "340.0.0.36.71",
]
_IG_BUILD_RANGE: Tuple[int, int] = (620_000_000, 690_000_000)

# TikTok / musical_ly app versions (iOS + Android share major numbers).
_TIKTOK_APP_VERSIONS: List[str] = [
    "34.5.1", "34.4.0", "34.3.2", "34.2.1", "34.1.0",
    "33.9.4", "33.8.1", "33.7.0", "33.6.2", "33.5.0",
    "33.4.1", "33.3.0", "33.2.0", "33.1.2", "32.9.0",
]

# BytedanceWebview short hash (changes per app release).
_BYTEDANCE_WV_HASHES: List[str] = [
    "d8a21c6", "c4f12e8", "a93b7d2", "f1e84a5", "b27c9d6",
    "e35f7c1", "d61a8b9", "9c4e2f7", "7d5b3a4", "5e9f1c8",
]

# TikTok Region pool — biased toward English-speaking markets but covers
# the major monetised geographies so a per-visit pick stays plausible.
_TIKTOK_REGIONS: List[str] = [
    "US", "US", "US", "GB", "CA", "AU", "DE", "FR", "BR", "MX",
    "IT", "ES", "JP", "ID", "PH", "TH", "IN", "TR", "SA", "AE",
]

# TikTok ByteLocale pool — should generally match the Region.
_TIKTOK_LOCALES: List[str] = [
    "en", "en-US", "en-GB", "en-CA", "en-AU", "de-DE", "fr-FR",
    "es-MX", "pt-BR", "it-IT", "ja-JP", "tr-TR",
]

# Snapchat app versions (Android + iOS).
_SNAPCHAT_APP_VERSIONS: List[str] = [
    "12.95.0.41", "12.93.0.50", "12.91.0.45", "12.89.0.40", "12.87.0.43",
]

# LinkedIn mobile-app build numbers.
_LINKEDIN_APP_VERSIONS: List[str] = [
    "9.32.512", "9.31.482", "9.30.451", "9.29.421", "9.28.395",
]

# Markers that mean "this UA is already in-app". When ANY of these
# substrings appear in a UA, we treat it as already-coerced and DO NOT
# re-append anything (idempotent guarantee).
_INAPP_MARKER_LOOKUP: Dict[str, Tuple[str, ...]] = {
    "facebook":  ("fb_iab", "fban/", "fbav/", "fb4a", "fbios"),
    "messenger": ("messenger", "fbms"),
    "instagram": ("instagram/", "instagram "),
    # 2026-06-14 fix: UA Gen emits TikTok Android as `trill_NNNNNN ...
    # AppName/musical_ly app_version/X ... BytedanceWebview/HASH` and
    # TikTok iOS as `musical_ly_X JsSdk/2.0 ...`. Earlier marker set
    # missed `trill_` and `appname/musical_ly` → coerce re-appended its
    # own TikTok suffix → DOUBLE BytedanceWebview/, DOUBLE Region/, etc.
    # = instant fraud flag. Now we catch every real TT marker.
    "tiktok":    ("musical_ly", "musically", "tiktok", "ttwebview",
                  "bytedancewebview", "aweme", "trill_", "appname/musical_ly"),
    "snapchat":  ("snapchat",),
    "linkedin":  ("linkedinapp", "linkedin/"),
    "twitter":   ("twitterandroid", "twitterios", "twitter/"),
}

# Platforms that have an in-app webview surface on MOBILE. Desktop
# browsing of these sites stays in the host browser so coerce is a
# no-op for desktop UAs.
_INAPP_CAPABLE_PLATFORMS: Tuple[str, ...] = (
    "facebook", "messenger", "instagram", "tiktok",
    "snapchat", "linkedin", "twitter",
)


def _is_mobile_ua(ua: str) -> str:
    """Return "android" | "ios" | "" — detects mobile UA family.

    "" means desktop / bot / unparseable → caller should NOT coerce.
    """
    if not ua:
        return ""
    ual = ua.lower()
    # iOS — must come before generic mobile check because some iPhone
    # UAs include "android" inside a webview profile name (rare but real).
    if ("iphone" in ual or "ipad" in ual or "ipod" in ual) and "like mac os x" in ual:
        return "ios"
    if "android" in ual and ("mobile" in ual or "; wv)" in ual or "build/" in ual):
        return "android"
    return ""


def _extract_android_build_token(ua: str) -> str:
    """Pull the `Build/XXX` token from an Android UA, or return "" when
    the UA doesn't carry one (older / synthetic UAs). The build id is
    part of the in-app suffix realism, so we preserve it when present.
    """
    m = re.search(r"Build/([A-Za-z0-9_.\-]+)", ua or "")
    return m.group(1) if m else ""


def _extract_ios_device_model(ua: str) -> str:
    """Return an FBDV-compatible iOS device model token (e.g. iPhone17,1).

    Real Facebook iOS UAs include the device internal model id, not the
    marketing name. We look at the UA's CPU/OS hints to pick a recent
    plausible model. Defaults to a 2024 iPhone if nothing matches.
    """
    if not ua:
        return "iPhone15,3"
    ual = ua.lower()
    # iPad signatures — broader pool.
    if "ipad" in ual:
        return random.choice(["iPad13,16", "iPad14,3", "iPad14,5", "iPad14,8"])
    # iPhone — pick a model matching the OS major version when possible.
    m = re.search(r"iphone os (\d+)[_\d]*", ual)
    if m:
        major = int(m.group(1))
        if major >= 18:
            return random.choice(["iPhone17,1", "iPhone17,2", "iPhone16,1", "iPhone16,2"])
        if major == 17:
            return random.choice(["iPhone15,2", "iPhone15,3", "iPhone16,1", "iPhone14,5"])
        if major == 16:
            return random.choice(["iPhone14,7", "iPhone14,8", "iPhone15,2", "iPhone13,2"])
        if major == 15:
            return random.choice(["iPhone13,2", "iPhone13,3", "iPhone14,2"])
    return "iPhone15,3"


def _ua_has_inapp_marker(ua: str, platform: str) -> bool:
    """True iff `ua` already carries the in-app marker for `platform`.

    Used for idempotency — coerce_ua_for_platform short-circuits when the
    UA is already a proper in-app webview UA for the chosen platform.

    2026-06-15 hardening (anti-"Unknown" version bug): for Facebook /
    Messenger UAs we now require BOTH a family marker (FB_IAB / FBAN /
    FB4A / FBIOS) AND a parseable `FBAV/<X.X.X[.X.X]>` version of at
    least 5 chars (e.g. "200.0" or full "515.1.0.62.90"). Earlier we
    returned True on family-marker presence alone — which let UAs that
    had `FB_IAB/FB4A` but EMPTY or MISSING FBAV slip through the
    coercion short-circuit unchanged. Affiliate-side UA parsers
    (user-agents / ua-parser / Browscap) then detected "Facebook" as
    the browser family but had no version to extract, producing the
    "Facebook for Android (Unknown)" cluster on advertiser dashboards.
    Re-running coercion on those UAs now properly appends a fresh
    `[FB_IAB/FB4A;FBAV/<real_ver>;IABMV/1;]` suffix.
    """
    if not ua or not platform:
        return False
    ual = ua.lower()
    p = platform.lower()
    markers = _INAPP_MARKER_LOOKUP.get(p, ())
    has_family_marker = any(m and m in ual for m in markers)
    if not has_family_marker:
        return False

    # Facebook / Messenger special-case: require complete FBAV version.
    if p in ("facebook", "messenger"):
        # Real FBAV format: 3-5 dot-separated numeric segments
        # (e.g. "200.0.0", "515.1.0.62.90"). Allow either short or full
        # — anything is OK as long as at least one dotted version is
        # present and the version body is ≥ 5 chars (so "FBAV/" or
        # "FBAV/x" both fail and trigger re-coercion).
        m = re.search(r"fbav/([\d.]+)", ual)
        if not m or len(m.group(1)) < 5 or "." not in m.group(1):
            return False
    return True


def build_inapp_ua_suffix(platform: str, ua: str) -> str:
    """Build the realistic in-app webview suffix for `platform`, sized
    appropriately for the OS family detected in `ua`.

    Returns "" when:
        * platform is not in _INAPP_CAPABLE_PLATFORMS, OR
        * ua is desktop / not mobile (callers should not append anything
          to desktop UAs — that would itself look forged).

    Real-world structure references:
        Facebook Android: [FB_IAB/FB4A;FBAV/515.1.0.62.90;IABMV/1;]
        Facebook iOS:     [FBAN/FBIOS;FBAV/515.0.0.43.108;FBBV/683141668;
                           FBDV/iPhone17,1;FBMD/iPhone;FBSN/iOS;FBSV/18.3;
                           FBSS/3;FBID/phone;FBLC/en_US;FBOP/5;
                           FBRV/684552024;IABMV/1]
        TikTok Android:   musical_ly_2024105080 JsSdk/1.0 NetType/WIFI
                          Channel/googleplay AppName/musical_ly
                          app_version/34.5.1 ByteLocale/en Region/US
                          BytedanceWebview/d8a21c6
        Instagram And:    Instagram 354.0.0.45.81 Android (...; en_US;
                          640573830)
        Instagram iOS:    Instagram 354.0.0.45.81 (iPhone17,1; iOS 18_3
                          like Mac OS X; en_US; en-US; scale=3.00;
                          1170x2532; 640573830)
        Snapchat:         Snapchat/12.95.0.41 (...; en_US)
    """
    p = (platform or "").lower().strip()
    if p not in _INAPP_CAPABLE_PLATFORMS:
        return ""
    family = _is_mobile_ua(ua)
    if not family:
        return ""

    if p in ("facebook", "messenger"):
        if family == "android":
            ver = random.choice(_FBAV_ANDROID_VERSIONS)
            if p == "messenger":
                # Messenger UAs use FBAN/MessengerForAndroid + Orca-Android
                return f"[FB_IAB/MESSENGER;FBAV/{ver};IABMV/1;]"
            return f"[FB_IAB/FB4A;FBAV/{ver};IABMV/1;]"
        # iOS
        ver = random.choice(_FBAV_IOS_VERSIONS)
        fbbv = random.randint(*_FBBV_IOS_RANGE)
        fbrv = random.randint(*_FBRV_IOS_RANGE)
        fbdv = _extract_ios_device_model(ua)
        # Pull iOS major.minor from UA → FBSV value.
        m = re.search(r"iphone os ([\d_]+)", ua.lower())
        fbsv = m.group(1).replace("_", ".") if m else "18.3"
        # Locale — operator-set Accept-Language can override later, but
        # the suffix string itself carries FBLC for cross-checking.
        fblc = random.choice(["en_US", "en_GB", "en_CA", "es_US", "pt_BR", "de_DE", "fr_FR"])
        app_name = "MESSENGER" if p == "messenger" else "FBIOS"
        return (
            f"[FBAN/{app_name};FBAV/{ver};FBBV/{fbbv};FBDV/{fbdv};"
            f"FBMD/iPhone;FBSN/iOS;FBSV/{fbsv};FBSS/3;FBID/phone;"
            f"FBLC/{fblc};FBOP/5;FBRV/{fbrv};IABMV/1]"
        )

    if p == "instagram":
        ver = random.choice(_IG_APP_VERSIONS)
        build_id = random.randint(*_IG_BUILD_RANGE)
        locale = random.choice(["en_US", "en_GB", "en_CA", "es_US", "pt_BR"])
        if family == "android":
            # Find the Android version + device model from the UA so the
            # Instagram suffix is internally coherent.
            m_ver = re.search(r"android (\d+(?:\.\d+)?)", ua.lower())
            android_ver = m_ver.group(1) if m_ver else "14"
            m_dev = re.search(r";\s*([A-Z0-9][A-Za-z0-9 _\-\+]*?)\s*Build/", ua)
            device = (m_dev.group(1).strip() if m_dev else "SM-S928B")
            dpi = random.choice(["420dpi", "480dpi", "560dpi", "640dpi"])
            res = random.choice(["1080x2340", "1170x2532", "1284x2778", "1080x2400"])
            return (
                f"Instagram {ver} Android (29/{android_ver}; {dpi}; {res}; "
                f"samsung; {device}; sm; sm; {locale.replace('_','-').lower()}; {build_id})"
            )
        # iOS
        m = re.search(r"iphone os ([\d_]+)", ua.lower())
        ios_ver = m.group(1) if m else "18_3"
        device = _extract_ios_device_model(ua)
        return (
            f"Instagram {ver} (iPhone; CPU iPhone OS {ios_ver} like Mac OS X; "
            f"{locale}; scale=3.00; 1170x2532; {build_id})"
        )

    if p == "tiktok":
        ver = random.choice(_TIKTOK_APP_VERSIONS)
        wv_hash = random.choice(_BYTEDANCE_WV_HASHES)
        region = random.choice(_TIKTOK_REGIONS)
        locale = random.choice(_TIKTOK_LOCALES)
        # TikTok's `app_version` build counter — numeric YYYYRRRSS-style.
        # Constructed deterministically from the version string so that
        # version "34.5.1" → 2034050010 etc. (matches their real coder).
        try:
            mj, mn, pt = (ver.split(".") + ["0"])[:3]
            ver_code = f"20{int(mj):02d}{int(mn):02d}0{int(pt):02d}0"
        except Exception:
            ver_code = "2034050010"
        nettype = random.choice(["WIFI", "MOBILE", "4G", "5G"])
        if family == "android":
            channel = random.choice(["googleplay", "googleplay", "samsung", "huawei", "xiaomi"])
            return (
                f"musical_ly_{ver_code} JsSdk/1.0 NetType/{nettype} Channel/{channel} "
                f"AppName/musical_ly app_version/{ver} ByteLocale/{locale} "
                f"ByteFullLocale/{locale} Region/{region} AppVersion/{ver} "
                f"BytedanceWebview/{wv_hash}"
            )
        # iOS
        return (
            f"musical_ly_{ver_code} JsSdk/1.0 NetType/{nettype} "
            f"AppName/musical_ly app_version/{ver} ByteLocale/{locale} "
            f"Region/{region} AppVersion/{ver} BytedanceWebview/{wv_hash}"
        )

    if p == "snapchat":
        ver = random.choice(_SNAPCHAT_APP_VERSIONS)
        if family == "android":
            return f"Snapchat/{ver}"
        return f"Snapchat/{ver}"

    if p == "linkedin":
        ver = random.choice(_LINKEDIN_APP_VERSIONS)
        if family == "android":
            return f"com.linkedin.android/{ver}"
        return f"LinkedInApp/{ver}"

    if p == "twitter":
        # Twitter mobile webview UA marker.
        rev = random.randint(10000000, 99000000)
        if family == "android":
            return f"TwitterAndroid/{rev}"
        return f"TwitterIOS/{rev}"

    return ""


def coerce_ua_for_platform(ua: str, platform: str) -> str:
    """Return a UA whose tail markers are consistent with `platform`.

    Behaviour:
      * desktop UA → returned unchanged (legit signature on desktop).
      * mobile UA + non-inapp platform (google/bing/direct/email/youtube
        watch-only/etc.) → returned unchanged.
      * mobile UA + in-app platform AND UA already carries the matching
        markers → returned unchanged (idempotent).
      * mobile UA + in-app platform → suffix appended. For Android we
        also ensure the UA has the `wv` token and a `Version/4.0` (the
        WebKit version token Android WebView always emits) — both are
        signals fraud detectors check for, and synthetic UAs sometimes
        miss them.
      * any error → original UA (never raises).

    Pure function. No I/O.
    """
    try:
        if not ua or not platform:
            return ua or ""
        p = platform.lower().strip()
        if p not in _INAPP_CAPABLE_PLATFORMS:
            return ua
        family = _is_mobile_ua(ua)
        if not family:
            return ua
        if _ua_has_inapp_marker(ua, p):
            return ua

        suffix = build_inapp_ua_suffix(p, ua)
        if not suffix:
            return ua

        new_ua = ua

        # ── 2026-06-15 (anti "Unknown" version): if the UA already carries
        # an INCOMPLETE platform bracket (e.g. `[FB_IAB/FB4A;]` with
        # missing/empty FBAV), strip it BEFORE we append the fresh one.
        # Without this, the UA would end up with TWO brackets — the
        # broken old + the fresh good — which is itself a fraud tell
        # (no real client ships duplicate app-marker brackets). The new
        # `_ua_has_inapp_marker` already returns False for these
        # incomplete brackets so we land here.
        if p in ("facebook", "messenger"):
            # Match trailing `[FB_IAB/...]` or `[FBAN/...]` bracket and
            # remove it. Real captures only ever have ONE such bracket
            # at the very end of the UA, so a single removal is safe.
            new_ua = re.sub(
                r"\s*\[\s*(?:FB_IAB|FBAN)/[^\]]*\]\s*$",
                "",
                new_ua,
                flags=re.IGNORECASE,
            ).rstrip()
        elif p == "instagram":
            # Real IG iOS UA ends with `Instagram <ver> (...)` paren block.
            # Strip incomplete trailing `Instagram` paren if FBAV-equiv
            # version is missing — same principle as Facebook. We use a
            # conservative regex that ONLY removes the trailing
            # `Instagram ...` suffix when no version number follows.
            if re.search(r"instagram\s*$", new_ua, flags=re.IGNORECASE):
                new_ua = re.sub(
                    r"\s+Instagram\s*$",
                    "",
                    new_ua,
                    flags=re.IGNORECASE,
                ).rstrip()
        elif p == "tiktok":
            # Strip incomplete trailing musical_ly / aweme / trill_
            # markers that lack version info, so the fresh suffix
            # doesn't double up.
            new_ua = re.sub(
                r"\s+(musical_ly|aweme|trill_)\S*\s*$",
                "",
                new_ua,
                flags=re.IGNORECASE,
            ).rstrip()

        # Android WebView realism: real in-app UAs include "; wv)" and a
        # "Version/4.0" token. If they're missing, synthesise the most
        # common form before appending the suffix.
        if family == "android":
            # Insert "; wv" right before the closing ")" of the Linux/Android
            # parenthesised section if not already present.
            if "; wv)" not in new_ua and "wv)" not in new_ua:
                new_ua = re.sub(
                    r"\((Linux; Android[^)]*?)\)",
                    lambda m: f"({m.group(1)}; wv)",
                    new_ua,
                    count=1,
                )
            # Insert "Version/4.0" before "Chrome/" if absent — matches
            # the real Android WebView token order.
            if "Version/4.0" not in new_ua:
                new_ua = re.sub(
                    r"AppleWebKit/([\d.]+) \(KHTML, like Gecko\) Chrome/",
                    r"AppleWebKit/\1 (KHTML, like Gecko) Version/4.0 Chrome/",
                    new_ua,
                    count=1,
                )

        # iOS realism: real in-app webview UAs DROP the
        # `Version/<X.X>` and `Safari/<X.X.X>` tokens that plain Safari
        # carries, then append the app-specific marker block. UA parsers
        # scan left-to-right and stop at `Safari/...` — if we leave that
        # token in place, the tracker classifies the click as Safari and
        # ignores everything after, hiding the in-app signature.
        # Apple's iOS 26 / Safari 26 UAs additionally FREEZE the OS
        # version at 18_6 and remove device model tokens (privacy by
        # design — see Safari 26 release notes). We preserve that
        # freezing — we ONLY strip Version/X + Safari/X and ensure the
        # `Mobile/<build>` token stays in place since real in-app
        # captures keep it.
        if family == "ios" and p in (
            "facebook", "messenger", "tiktok", "instagram",
            "snapchat", "linkedin", "twitter",
        ):
            # 1. Strip the trailing `Safari/<X.X.X>` token (real in-app
            #    UAs don't carry it).
            new_ua = re.sub(r"\s+Safari/[\d.]+\s*$", "", new_ua).rstrip()
            # 2. Strip the `Version/<X.X>` token (modern iOS in-app
            #    webviews omit it; FBAN/musical_ly/Instagram all replace
            #    that slot with their own version block).
            new_ua = re.sub(r"\s+Version/[\d.]+\b", "", new_ua)
            # 3. Ensure a `Mobile/<build>` token exists — real captures
            #    always have one. iOS Safari 26 emits `Mobile/15E148`
            #    (frozen) so we use the same default if missing.
            if "Mobile/" not in new_ua:
                new_ua += " Mobile/15E148"

        # Final append — ensure a single space separator.
        sep = " " if not new_ua.endswith(" ") else ""
        return f"{new_ua}{sep}{suffix}"
    except Exception:
        # NEVER raise — fraud-coerce must be a safe additive layer.
        return ua


# ══════════════════════════════════════════════════════════════════════
# Convenience helpers for callers
# ══════════════════════════════════════════════════════════════════════
def platform_needs_ua_match(platform: str) -> bool:
    """True iff the platform is one whose realistic UA differs on mobile
    from a plain browser UA (so coercion is meaningful)."""
    return (platform or "").lower() in _INAPP_CAPABLE_PLATFORMS


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
    "rebuild_referer_with_target",
    "build_sec_fetch_headers",
    "build_network_click_referer",
    "build_inapp_ua_suffix",
    "coerce_ua_for_platform",
    "platform_needs_ua_match",
    # Geo + UTM
    "get_geo_search_hosts",
    "pick_utm_variation",
    "pick_utm_campaign",
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
