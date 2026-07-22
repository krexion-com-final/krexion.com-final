"""
v2.6.26 — TikTok Android UA — advertiser browser detection fix
================================================================

Bug report source: customer's clicks (4).csv (Jan 2026)
Sample: 106 rows / 23 TikTok-referred Android clicks

Observation:
   iOS TikTok clicks     → Browser column correctly reads "TikTok for iOS"
   Android TikTok clicks → Browser column reads <empty> (100% failure rate)

Root cause:
   Our v2.6.22 Cronet-based TikTok Android UA only carried
   `musical_ly_<10digit_build>` as the TikTok identifier. Modern
   advertiser UA parsers (ua-parser-js, uap-core / ua-parser-cpp,
   Everflow / Voluum / RedTrack) use the regex `TikTok\/([\d.]+)`
   as the primary "TikTok" browser detection rule. Without an
   explicit `TikTok/{app_ver}` slug in the UA, they fall through
   to the generic Android rule and emit Browser="" on the report.

Fix (v2.6.26):
   Insert `TikTok/{app_ver}` immediately after Cronet's closing
   paren in BOTH generators:
     - server.py::_ua_tiktok_android
     - referrer_pro.py::build_inapp_ua_suffix (tiktok/android branch)
   Also extend `_FOREIGN_INAPP_STRIP_PATTERNS['tiktok']` to strip
   the leading `TikTok/{ver}` so coercing away from tiktok cleanly
   removes both markers.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server  # noqa: E402
import referrer_pro  # noqa: E402


# ─── 1. `_ua_tiktok_android` generator carries `TikTok/{ver}` ─────────
def test_ua_tiktok_android_carries_tiktok_slash_ver_marker():
    d = {
        "and_ver": "14", "model": "SM-S928B",
        "build": "UP1A.231005.007", "sdk": "34",
    }
    for _ in range(30):
        ua = server._ua_tiktok_android(d, "34.9.5")
        # Cronet base still present (v2.6.22 shape preserved)
        assert "Cronet/" in ua, f"Cronet base lost: {ua!r}"
        # v2.6.26 explicit TikTok marker
        assert re.search(r"\bTikTok/34\.9\.5\b", ua), (
            f"Missing TikTok/{{app_ver}} marker: {ua!r}"
        )
        # Legacy `musical_ly_` marker still present (fraud-scanner shape)
        assert re.search(r"\bmusical_ly_\d+\b", ua), (
            f"Missing musical_ly_ marker: {ua!r}"
        )
        # Position: TikTok/ must appear BEFORE musical_ly_ (real captures
        # and ua-parser rule priority both require this order)
        pos_tt = ua.find("TikTok/34.9.5")
        pos_ml = ua.find("musical_ly_")
        assert 0 <= pos_tt < pos_ml, (
            f"TikTok/ must precede musical_ly_: {ua!r}"
        )
        # No Chrome/ or Safari/ token leaked back in (v2.6.22 guarantee)
        assert "Chrome/" not in ua, f"Chrome/ leak: {ua!r}"
        assert "Mobile Safari/" not in ua, f"Safari leak: {ua!r}"


# ─── 2. `build_inapp_ua_suffix('tiktok', android_base)` carries it ────
def test_build_inapp_ua_suffix_tiktok_android_carries_tiktok_ver():
    base = "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007; wv)"
    for _ in range(30):
        suf = referrer_pro.build_inapp_ua_suffix("tiktok", base)
        assert suf, "Empty suffix"
        assert re.search(r"^TikTok/\d+\.\d+", suf), (
            f"Suffix must start with TikTok/{{ver}}: {suf!r}"
        )
        assert "musical_ly_" in suf, f"musical_ly_ missing: {suf!r}"
        assert "BytedanceWebview/" in suf, f"BytedanceWebview missing: {suf!r}"


# ─── 3. iOS suffix must NOT carry `TikTok/{ver}` (iOS uses AppId/1233) ─
def test_build_inapp_ua_suffix_tiktok_ios_unchanged():
    base = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
    for _ in range(20):
        suf = referrer_pro.build_inapp_ua_suffix("tiktok", base)
        assert suf, "Empty suffix"
        # iOS branch does NOT gain the TikTok/{ver} prefix (unchanged) — iOS
        # detection already works via `AppId/1233` in _ua_tiktok_ios and the
        # `musical_ly_` marker inside the WKWebView suffix.
        assert not suf.startswith("TikTok/"), (
            f"iOS suffix must NOT start with TikTok/: {suf!r}"
        )
        assert "musical_ly_" in suf


# ─── 4. Coerce-away strip: TikTok/{ver} removed when target != tiktok ─
def test_strip_foreign_tiktok_markers_removes_TikTok_slash_ver_too():
    ua = (
        "Mozilla/5.0 (Linux; U; Android 14; en_US; SM-S928B; "
        "Build/UP1A.231005.007; Cronet/58.0.2991.0) "
        "TikTok/34.5.1 musical_ly_2034050010 JsSdk/1.0 NetType/WIFI "
        "Channel/googleplay AppName/musical_ly app_version/34.5.1 "
        "ByteLocale/en_US Region/US BytedanceWebview/abc1234"
    )
    for target in ("facebook", "instagram", "snapchat", "twitter", "google", "youtube"):
        stripped = referrer_pro._strip_foreign_inapp_markers(ua, target)
        assert "TikTok/34.5.1" not in stripped, (
            f"TikTok/{{ver}} leaked into {target}-coerced UA: {stripped!r}"
        )
        assert "musical_ly_" not in stripped, (
            f"musical_ly_ leaked into {target}-coerced UA: {stripped!r}"
        )


# ─── 5. Idempotency: coerce back to tiktok preserves the new marker ───
def test_coerce_ua_for_platform_tiktok_preserves_TikTok_slash_ver():
    # Take a UA that already carries the new marker — coerce back to
    # tiktok should be a no-op (idempotency check via _ua_has_inapp_marker)
    ua_in = (
        "Mozilla/5.0 (Linux; U; Android 14; en_US; SM-S928B; "
        "Build/UP1A.231005.007; Cronet/58.0.2991.0) "
        "TikTok/34.9.5 musical_ly_2034090050 JsSdk/1.0 NetType/WIFI "
        "Channel/googleplay AppName/musical_ly app_version/34.9.5 "
        "ByteLocale/en_US Region/US BytedanceWebview/abc1234 "
        "com.zhiliaoapp.musically/2034090050"
    )
    out = referrer_pro.coerce_ua_for_platform(ua_in, "tiktok")
    # Marker preserved
    assert "TikTok/34.9.5" in out, f"marker lost by coerce: {out!r}"
    assert "musical_ly_" in out


# ─── 6. Non-Samsung brands still get TikTok/{ver} marker ──────────────
def test_ua_tiktok_android_non_samsung_brands_still_get_marker():
    """v2.6.26 fix must apply regardless of device brand — the bug in the
    original CSV showed Motorola / OnePlus / Xiaomi / Google Pixel /
    DOOGEE clicks all with empty Browser. All these should now get
    detected."""
    for brand_model in [
        ("Motorola", "motorola-edge-30-pro"),
        ("OnePlus",  "PJZ110"),
        ("Xiaomi",   "23049PCD8G"),
        ("Google",   "Pixel 8 Pro"),
        ("DOOGEE",   "S110"),
    ]:
        d = {
            "and_ver": "14", "model": brand_model[1],
            "build": "UP1A.231005.007", "sdk": "34",
        }
        ua = server._ua_tiktok_android(d, "34.5.1")
        assert re.search(r"\bTikTok/34\.5\.1\b", ua), (
            f"[{brand_model[0]}] Missing TikTok/ marker: {ua!r}"
        )
        assert re.search(r"\bmusical_ly_\d+\b", ua), (
            f"[{brand_model[0]}] Missing musical_ly_ marker: {ua!r}"
        )
        assert brand_model[1] in ua, (
            f"[{brand_model[0]}] Device model missing: {ua!r}"
        )
