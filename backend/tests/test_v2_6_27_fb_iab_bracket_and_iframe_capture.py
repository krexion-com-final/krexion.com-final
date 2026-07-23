"""
v2.6.27 — TikTok Android FB_IAB bracket + Facebook FBAV normalisation
======================================================================

Bug follow-up from customer's second CSV report (screenshots of Everflow
click details in Session 4):

  1. `Browser=Android (13.0)` on TikTok Android clicks — v2.6.26's
     `TikTok/{app_ver}` slug alone was NOT in advertiser UA parsers'
     rule DB (uap-core / user_agents lib still returned `family='Android'`
     for those UAs). Fix: append `[FB_IAB/;FBAN/TikTokAndroid;FBAV/{ver};
     IABMV/1;FBBV/{ml_build};FBOP/19;]` bracket — the FB_IAB format is
     the UNIVERSAL in-app-browser marker every major tracker (Everflow,
     Voluum, RedTrack, Binom) understands, and setting FBAN=TikTokAndroid
     triggers their "TikTok for Android" detection branch.

  2. `Facebook for iOS (Unknown)` + `Facebook for Android (Unknown)` —
     the browser was correctly detected as Facebook but the version
     column always said "Unknown". Root cause: our upstream
     `_APP_VERSIONS['facebook']` pool mixes 2-part (`557.0`) and 5-part
     (`550.0.0.45.102`) shapes; many parser DBs expect exactly `X.Y.Z`.
     Fix: new `_fbav_3part()` helper normalises the app_version to 3
     dot-separated groups before it lands in `FBAV/…`, and both
     `_ua_facebook_android` and `_ua_facebook_ios` now use it. Also
     added `FBAN/FB4A` slug to the Android bracket alongside the
     existing `FB_IAB/FB4A` (real modern 2024+ FB Android captures
     carry both).

Additional coerce-machinery updates:
  - `_FOREIGN_INAPP_STRIP_PATTERNS['fb_bracket']` TIGHTENED to match
    ONLY the Facebook-specific bracket shapes (`FB_IAB/FB4A` or
    `FBAN/FBIOS`) so the new `[FB_IAB/;FBAN/TikTokAndroid;…]` trailer
    isn't accidentally wiped when coercing to tiktok.
  - `_FOREIGN_INAPP_STRIP_PATTERNS['tiktok']` EXTENDED so the FB_IAB
    TikTokAndroid bracket is stripped when coercing away from tiktok.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server  # noqa: E402
import referrer_pro  # noqa: E402


# ─── 1. TikTok Android UA carries the FB_IAB TikTokAndroid bracket ────
def test_ua_tiktok_android_carries_fb_iab_tiktokandroid_bracket():
    d = {"and_ver": "14", "model": "SM-S928B",
         "build": "UP1A.231005.007", "sdk": "34"}
    for _ in range(30):
        ua = server._ua_tiktok_android(d, "44.7.0")
        assert re.search(r"\[FB_IAB/;FBAN/TikTokAndroid;FBAV/44\.7\.0;IABMV/1;FBBV/\d+;FBOP/19;\]", ua), (
            f"missing FB_IAB TikTokAndroid bracket: {ua!r}"
        )
        # v2.6.26 markers still preserved
        assert re.search(r"\bTikTok/44\.7\.0\b", ua)
        assert re.search(r"\bmusical_ly_\d+\b", ua)
        assert "com.zhiliaoapp.musically/" in ua
        # No Chrome/Safari leak from v2.6.22 guarantee still holds
        assert "Chrome/" not in ua
        assert "Mobile Safari/" not in ua


def test_build_inapp_ua_suffix_tiktok_android_carries_fb_iab_bracket():
    base = "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007; wv)"
    for _ in range(20):
        suf = referrer_pro.build_inapp_ua_suffix("tiktok", base)
        assert re.search(r"\[FB_IAB/;FBAN/TikTokAndroid;FBAV/\d+\.\d+\.\d+;IABMV/1;FBBV/\d+;FBOP/19;\]", suf), (
            f"suffix missing FB_IAB TikTokAndroid bracket: {suf!r}"
        )
        assert suf.startswith("TikTok/")


# ─── 2. Facebook FBAV is normalised to 3-part `X.Y.Z` ────────────────
def test_fbav_3part_helper():
    assert server._fbav_3part("557.0") == "557.0.0"
    assert server._fbav_3part("550.0.0.45.102") == "550.0.0"
    assert server._fbav_3part("461.0.0") == "461.0.0"
    assert server._fbav_3part("") == "0.0.0"
    assert server._fbav_3part("1") == "1.0.0"
    assert server._fbav_3part("1.2") == "1.2.0"


def test_ua_facebook_android_fbav_is_3part_and_fban_present():
    d = {"and_ver": "14", "model": "SM-S928B",
         "build": "UP1A.231005.007", "sdk": "34"}
    # Test with 5-part input version → should render as 3-part in UA
    ua = server._ua_facebook_android(d, "550.0.0.45.102", "128.0.6613.127")
    assert "FBAV/550.0.0;" in ua, f"FBAV must be 3-part: {ua!r}"
    assert "FBAN/FB4A;" in ua, f"FBAN/FB4A slug missing: {ua!r}"
    assert "FB_IAB/FB4A;" in ua, f"FB_IAB/FB4A slug missing (real-capture parity): {ua!r}"

    # Test with 2-part input version → should also render as 3-part
    ua2 = server._ua_facebook_android(d, "557.0", "128.0.6613.127")
    assert "FBAV/557.0.0;" in ua2, f"FBAV must be 3-part: {ua2!r}"


def test_ua_facebook_ios_fbav_is_3part():
    d = {"ios": "18_3", "brand": "iPhone", "model": "iPhone15,3",
         "build": "22D63", "sdk": "18", "scale": "3.0"}
    ua = server._ua_facebook_ios(d, "461.0.0.51.107")
    assert "FBAV/461.0.0;" in ua, f"FBAV must be 3-part: {ua!r}"
    assert "FBAN/FBIOS;" in ua  # existing marker preserved
    # 2-part input → 3-part output
    ua2 = server._ua_facebook_ios(d, "551.0")
    assert "FBAV/551.0.0;" in ua2


# ─── 3. Strip regex tightening — non-FB brackets stay when target=tiktok
def test_coerce_to_tiktok_preserves_tiktokandroid_bracket():
    """The TIGHTENED `fb_bracket` regex must NOT strip our own
    TikTokAndroid FB_IAB bracket when coercing to tiktok — that was
    the bug in v2.6.27 pre-tightening: uap-core saw TikTok bracket as
    Facebook (fb_bracket bucket matched it) → coerce wiped it → parser
    fell back to `Browser=Android`."""
    ua = (
        "Mozilla/5.0 (Linux; U; Android 14; en_US; SM-S928B; "
        "Build/UP1A.231005.007; Cronet/58.0.2991.0) "
        "TikTok/44.7.0 musical_ly_4470000000 JsSdk/1.0 NetType/WIFI "
        "Channel/googleplay AppName/musical_ly app_version/44.7.0 "
        "ByteLocale/en_US Region/US BytedanceWebview/abc1234 "
        "ttwebview/05080411 com.zhiliaoapp.musically/4470000000 "
        "[FB_IAB/;FBAN/TikTokAndroid;FBAV/44.7.0;IABMV/1;FBBV/4470000000;FBOP/19;]"
    )
    back = referrer_pro.coerce_ua_for_platform(ua, "tiktok")
    assert "FBAN/TikTokAndroid" in back, (
        f"TikTokAndroid bracket was wiped by coerce: {back!r}"
    )
    assert "TikTok/44.7.0" in back
    assert "musical_ly_" in back


def test_coerce_away_from_tiktok_strips_the_new_bracket():
    """Cross-platform coerce (TT → FB / IG / etc.) must strip both the
    v2.6.26 `TikTok/{ver}` slug AND the v2.6.27 FB_IAB TikTokAndroid
    trailer."""
    ua = (
        "Mozilla/5.0 (Linux; U; Android 14; en_US; SM-S928B; "
        "Build/UP1A.231005.007; Cronet/58.0.2991.0) "
        "TikTok/44.7.0 musical_ly_4470000000 JsSdk/1.0 NetType/WIFI "
        "Channel/googleplay AppName/musical_ly app_version/44.7.0 "
        "ByteLocale/en_US Region/US BytedanceWebview/abc1234 "
        "ttwebview/05080411 com.zhiliaoapp.musically/4470000000 "
        "[FB_IAB/;FBAN/TikTokAndroid;FBAV/44.7.0;IABMV/1;FBBV/4470000000;FBOP/19;]"
    )
    for target in ("facebook", "instagram", "snapchat", "twitter", "google", "youtube"):
        stripped = referrer_pro._strip_foreign_inapp_markers(ua, target)
        assert "FBAN/TikTokAndroid" not in stripped, (
            f"[{target}] TikTokAndroid bracket leaked: {stripped!r}"
        )
        assert "TikTok/44.7.0" not in stripped, (
            f"[{target}] TikTok/{{ver}} slug leaked: {stripped!r}"
        )
        assert "musical_ly_" not in stripped
        assert "BytedanceWebview" not in stripped
        assert "com.zhiliaoapp" not in stripped


def test_coerce_fb_to_fb_preserves_fb_bracket():
    """Existing behaviour must not regress: coercing an FB Android UA
    to `facebook` platform must PRESERVE the FB_IAB/FB4A bracket
    (that's how FB IAB clicks self-identify)."""
    ua = (
        "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 "
        "Mobile Safari/537.36 "
        "[FB_IAB/FB4A;FBAN/FB4A;FBAV/550.0.0;IABMV/1;FBBV/620000000;FBOP/19;]"
    )
    out = referrer_pro.coerce_ua_for_platform(ua, "facebook")
    assert "[FB_IAB/FB4A;" in out
    assert "FBAN/FB4A;" in out
    assert "FBAV/550.0.0;" in out


def test_coerce_fb_to_tiktok_strips_fb_bracket_and_adds_tt_markers():
    """When operator's UA pool has a FB-signed UA but the target
    platform is TikTok, coerce must STRIP the FB bracket AND ADD both
    the v2.6.26 TikTok/{ver} slug AND the v2.6.27 FB_IAB TikTokAndroid
    trailer."""
    ua = (
        "Mozilla/5.0 (Linux; Android 14; SM-S928B Build/UP1A.231005.007; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.127 "
        "Mobile Safari/537.36 "
        "[FB_IAB/FB4A;FBAN/FB4A;FBAV/550.0.0;IABMV/1;FBBV/620000000;FBOP/19;]"
    )
    out = referrer_pro.coerce_ua_for_platform(ua, "tiktok")
    assert "[FB_IAB/FB4A;" not in out, f"FB bracket leaked: {out!r}"
    assert "FBAN/FB4A" not in out or "FBAN/TikTokAndroid" in out, out
    # New TT markers
    assert "musical_ly_" in out
    assert "FBAN/TikTokAndroid" in out


# ─── 4. Visual Recorder — iframe_path capture surface exists ─────────
def test_visual_recorder_captures_iframe_path_field():
    """Smoke-test: the rich element-capture JS now yields an
    `iframe_path` key (empty list for top-level clicks, list of iframe
    selectors for popup drilling). The Python helper `_build_fallbacks`
    forwards it into `step.fallbacks.iframe_path` for the replay engine.
    """
    from visual_recorder import _build_fallbacks

    # Top-level click → no iframe_path in fallbacks
    fb1 = _build_fallbacks({
        "xpath_stable": "//*[@id='login']",
        "xpath_abs": "/html/body/div[1]/button",
        "text": "Login",
        "tag": "button",
        "nth_of_type": 1,
        "iframe_path": [],
    })
    assert "iframe_path" not in fb1

    # Iframe-drilled click → iframe_path preserved
    fb2 = _build_fallbacks({
        "xpath_stable": "//*[@id='submit']",
        "text": "Submit",
        "iframe_path": ["iframe#exit-intent-modal", "iframe.nested"],
    })
    assert fb2.get("iframe_path") == ["iframe#exit-intent-modal", "iframe.nested"]

    # Junk iframe_path values are filtered out
    fb3 = _build_fallbacks({
        "iframe_path": [None, "iframe#ok", 42, "iframe#also-ok"],
    })
    assert fb3.get("iframe_path") == ["iframe#ok", "iframe#also-ok"]

    # Non-list value ignored
    fb4 = _build_fallbacks({"iframe_path": "iframe#not-a-list"})
    assert "iframe_path" not in fb4
