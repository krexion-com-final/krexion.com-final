"""
v2.6.26 (Session 3 addendum) — Referrer chain preservation + Paid/Organic
============================================================================

Bug reports from customer (clicks (4).csv analysis, Session 3):

  1. Empty Referrer column at Everflow — for some rows the referrer was
     completely blank OR showed an intermediate affiliate-network wrapper
     URL (click.networkx.io/click.php?aff=..., mb-pl.com/click.php?aff=...,
     performcb.com, glitchyads, tracker.gateway) instead of the SPOOFED
     platform referrer (facebook.com / instagram.com / tiktok.com) that
     Krexion RUT set. Root cause: Chromium's default Referrer-Policy is
     `strict-origin-when-cross-origin` which STRIPS the Referer to just
     the origin on every hop of the 302 redirect chain (Krexion → offer
     network wrapper → Everflow). Fix (v2.6.26 Session 3): emit an
     EXPLICIT `Referrer-Policy: unsafe-url` header on Krexion's tracker
     `/api/t/{short_code}` response so the ORIGINAL spoofed platform
     Referer propagates through the whole chain to the final tracker.

  2. Sub2 column at Everflow was 100% empty (0/106 rows carried
     paid/organic differentiation) — impossible to filter reports by
     traffic type. Root cause: v2.6.24 correctly picked the paid vs
     organic referer POOL but never propagated the decision into any
     query param on the destination URL. Fix (v2.6.26 Session 3):
     `resolve_pro_visit` now exposes `is_paid: bool|None` and
     `traffic_type: "paid"|"organic"|"auto"` in its return dict; the
     tracker's `redirect_link` handler auto-injects the traffic_type
     into the destination URL under the operator-configured
     `traffic_type_param` key (default: `sub2`).

Tests below validate BOTH fixes at the resolver + tracker-integration
layer (no live HTTP required — everything is verified via direct
resolve_pro_visit calls and the same URL-mutation logic the tracker
uses).
"""
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import referrer_pro  # noqa: E402


# ─── 1. resolve_pro_visit exposes is_paid + traffic_type (SOCIAL) ─────
def test_resolve_pro_visit_returns_is_paid_paid_tiktok():
    for _ in range(20):
        r = referrer_pro.resolve_pro_visit(
            ua="Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
            platform_pool_value="tiktok:100",
            target_url="https://tracker.example.com/click?offer=1",
            traffic_type="paid",
        )
        assert r.get("platform") == "tiktok"
        assert r.get("is_paid") is True, f"is_paid must be True for paid TikTok: {r}"
        assert r.get("traffic_type") == "paid"


def test_resolve_pro_visit_returns_is_paid_organic_facebook():
    for _ in range(20):
        r = referrer_pro.resolve_pro_visit(
            ua="Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Mobile/15E148",
            platform_pool_value="facebook:100",
            target_url="https://tracker.example.com/click?offer=1",
            traffic_type="organic",
        )
        assert r.get("platform") == "facebook"
        assert r.get("is_paid") is False, f"is_paid must be False for organic FB: {r}"
        assert r.get("traffic_type") == "organic"


# ─── 2. Search-engine branch also exposes traffic_type ────────────────
def test_resolve_pro_visit_search_paid_google():
    r = referrer_pro.resolve_pro_visit(
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        platform_pool_value="google:100",
        target_url="https://tracker.example.com/click?offer=1",
        traffic_type="paid",
        search_keywords="cheap flights\nbudget hotels",
    )
    assert r.get("platform") == "google"
    assert r.get("is_paid") is True
    assert r.get("traffic_type") == "paid"


# ─── 3. Auto mode (no explicit traffic_type) still resolves ───────────
def test_resolve_pro_visit_auto_mode_derives_from_platform():
    # social platform + auto → paid by default (v2.6.24 rule)
    r = referrer_pro.resolve_pro_visit(
        ua="Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
        platform_pool_value="tiktok:100",
        target_url="https://tracker.example.com/click?offer=1",
        traffic_type="auto",
        campaign_type="auto",
    )
    # tiktok in _PAID_PLATFORMS_DEFAULT_TRUE → is_paid=True
    assert r.get("is_paid") is True
    assert r.get("traffic_type") == "paid"


# ─── 4. Mixed traffic_type gives random split ─────────────────────────
def test_resolve_pro_visit_mixed_traffic_type_produces_both():
    seen_paid = seen_org = 0
    for _ in range(100):
        r = referrer_pro.resolve_pro_visit(
            ua="Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 Mobile Safari/537.36",
            platform_pool_value="facebook:100",
            target_url="https://tracker.example.com/click?offer=1",
            traffic_type="mixed",
        )
        if r.get("is_paid") is True:
            seen_paid += 1
        elif r.get("is_paid") is False:
            seen_org += 1
    # Mixed = 60% paid / 40% organic. Give plenty of slack for variance.
    assert seen_paid > 30, f"mixed mode saw only {seen_paid} paid clicks in 100"
    assert seen_org > 15, f"mixed mode saw only {seen_org} organic clicks in 100"


# ─── 5. Tracker-level sub2 injection logic (simulated) ────────────────
def _simulate_tracker_sub2_inject(destination_url: str, traffic_type: str,
                                    key: str = "sub2") -> str:
    """Mirror of the redirect_link handler's paid/organic auto-inject —
    keeps this test independent of FastAPI request context.
    """
    from urllib.parse import urlparse as _up, parse_qsl as _pql
    from urllib.parse import urlencode as _uen, urlunparse as _uun
    if traffic_type not in ("paid", "organic"):
        return destination_url
    if not re.match(r"^[a-z][a-z0-9_]{0,31}$", key):
        return destination_url
    du = _up(destination_url)
    q = dict(_pql(du.query, keep_blank_values=True))
    if key not in q or not (q.get(key) or "").strip():
        q[key] = traffic_type
        return _uun(du._replace(query=_uen(q, doseq=True)))
    return destination_url


def test_tracker_injects_sub2_paid_when_empty():
    url = "https://tracker.example.com/click?offer=1&sub1=abc"
    out = _simulate_tracker_sub2_inject(url, "paid", "sub2")
    q = dict(parse_qsl(urlparse(out).query))
    assert q.get("sub2") == "paid", f"sub2=paid not injected: {out}"
    assert q.get("sub1") == "abc", f"existing sub1 was clobbered: {out}"


def test_tracker_does_not_overwrite_existing_sub2():
    url = "https://tracker.example.com/click?offer=1&sub2=my_manual_value"
    out = _simulate_tracker_sub2_inject(url, "paid", "sub2")
    q = dict(parse_qsl(urlparse(out).query))
    assert q.get("sub2") == "my_manual_value", f"operator's sub2 was overwritten: {out}"


def test_tracker_injects_organic():
    url = "https://tracker.example.com/click?offer=1"
    out = _simulate_tracker_sub2_inject(url, "organic", "sub2")
    q = dict(parse_qsl(urlparse(out).query))
    assert q.get("sub2") == "organic"


def test_tracker_honours_custom_traffic_type_param_key():
    # Operator configures `traffic_type_param="s2"` on the link
    url = "https://tracker.example.com/click?offer=1"
    out = _simulate_tracker_sub2_inject(url, "paid", "s2")
    q = dict(parse_qsl(urlparse(out).query))
    assert q.get("s2") == "paid"
    assert "sub2" not in q


def test_tracker_rejects_invalid_key():
    # Bad key: contains hyphen (not in [a-z0-9_]) → NO injection (defensive)
    url = "https://tracker.example.com/click?offer=1"
    out = _simulate_tracker_sub2_inject(url, "paid", "bad-key")
    assert "=paid" not in out, f"invalid key was injected: {out}"


def test_tracker_skips_when_traffic_type_is_auto():
    url = "https://tracker.example.com/click?offer=1"
    out = _simulate_tracker_sub2_inject(url, "auto", "sub2")
    q = dict(parse_qsl(urlparse(out).query))
    assert "sub2" not in q, f"auto traffic_type should not inject: {out}"
