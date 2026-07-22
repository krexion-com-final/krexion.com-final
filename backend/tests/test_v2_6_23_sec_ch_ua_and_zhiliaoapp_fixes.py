"""v2.6.23 — Sec-CH-UA + userAgentData + com.zhiliaoapp.musically fixes"""
import sys, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest

from referrer_pro import is_non_chrome_inapp_ua, coerce_ua_for_platform


BASE_ANDROID = ("Mozilla/5.0 (Linux; Android 15; SM-S931B Build/AP3A.240905.015; wv) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                "Chrome/146.0.7432.116 Mobile Safari/537.36")

BASE_IOS = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Mobile/15E148 Safari/604.1")


# ── is_non_chrome_inapp_ua classifier ──────────────────────────

def test_non_chrome_inapp_detects_tiktok_android():
    tt = coerce_ua_for_platform(BASE_ANDROID, "tiktok")
    assert is_non_chrome_inapp_ua(tt) is True

def test_non_chrome_inapp_detects_tiktok_ios():
    tt = coerce_ua_for_platform(BASE_IOS, "tiktok")
    assert is_non_chrome_inapp_ua(tt) is True

def test_non_chrome_inapp_detects_ig_ios():
    ig = coerce_ua_for_platform(BASE_IOS, "instagram")
    assert is_non_chrome_inapp_ua(ig) is True

def test_non_chrome_inapp_false_for_fb_android():
    # FB Android IS Chrome WebView + FB_IAB bracket → keep chrome hints.
    fb = coerce_ua_for_platform(BASE_ANDROID, "facebook")
    assert is_non_chrome_inapp_ua(fb) is False

def test_non_chrome_inapp_false_for_ig_android():
    ig = coerce_ua_for_platform(BASE_ANDROID, "instagram")
    assert is_non_chrome_inapp_ua(ig) is False

def test_non_chrome_inapp_false_for_plain_chrome():
    assert is_non_chrome_inapp_ua(BASE_ANDROID) is False
    assert is_non_chrome_inapp_ua(BASE_IOS) is False


# ── com.zhiliaoapp.musically marker present in tiktok UAs ──────

def test_tiktok_android_contains_zhiliaoapp_marker():
    tt = coerce_ua_for_platform(BASE_ANDROID, "tiktok")
    assert "com.zhiliaoapp.musically/" in tt

def test_tiktok_ios_contains_zhiliaoapp_marker():
    tt = coerce_ua_for_platform(BASE_IOS, "tiktok")
    assert "com.zhiliaoapp.musically/" in tt


# ── Server-side UA generator matches new format ────────────────

def test_server_ua_tiktok_android_generator_has_zhiliaoapp():
    from server import _ua_tiktok_android, _ANDROID_DEVICES
    d = _ANDROID_DEVICES[0]
    ua = _ua_tiktok_android(d, "34.9.5")
    assert "com.zhiliaoapp.musically/" in ua
    assert "Cronet/" in ua
    assert "musical_ly_" in ua
    assert "Chrome/" not in ua
    assert "Mobile Safari" not in ua


# ── Client hint headers helper: non-chrome in-app UA suppresses Sec-CH-UA brand ──

def test_client_hint_headers_suppresses_sec_ch_ua_for_tiktok_android():
    from real_user_traffic import _build_client_hint_headers
    tt_ua = coerce_ua_for_platform(BASE_ANDROID, "tiktok")
    fp = {"os": "android", "is_mobile": True}
    h = _build_client_hint_headers(fp, tt_ua)
    # Sec-CH-UA should be empty (override Chromium default), and
    # Sec-CH-UA-Full-Version-List / Sec-CH-UA-Platform-Version should NOT be set
    assert h.get("Sec-CH-UA", None) == "", f"Expected empty Sec-CH-UA to override Chromium default, got {h.get('Sec-CH-UA')!r}"
    assert "Sec-CH-UA-Full-Version-List" not in h
    assert "Sec-CH-UA-Platform-Version" not in h
    # But Mobile + Platform low-entropy hints DO stay (real WebViews emit them)
    assert h.get("Sec-CH-UA-Mobile") == "?1"
    assert h.get("Sec-CH-UA-Platform") == '"Android"'

def test_client_hint_headers_normal_chrome_unchanged():
    from real_user_traffic import _build_client_hint_headers
    fp = {"os": "windows", "is_mobile": False}
    h = _build_client_hint_headers(fp, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7367.60 Safari/537.36")
    # Chrome desktop must emit brand list
    assert "Sec-CH-UA" in h
    assert "Google Chrome" in h["Sec-CH-UA"]

def test_client_hint_headers_tiktok_ios_no_brand_leak():
    from real_user_traffic import _build_client_hint_headers
    tt_ua = coerce_ua_for_platform(BASE_IOS, "tiktok")
    fp = {"os": "ios", "is_mobile": True}
    h = _build_client_hint_headers(fp, tt_ua)
    assert h.get("Sec-CH-UA") == ""
    assert h.get("Sec-CH-UA-Platform") == '"iOS"'
    assert h.get("Sec-CH-UA-Mobile") == "?1"


# ── Advertiser UA parser sees TikTok now (com.zhiliaoapp.musically trigger) ──

def test_ua_parser_libs_recognize_com_zhiliaoapp_musically():
    """When our UA carries `com.zhiliaoapp.musically/`, advertiser
    UA parsers that include a TikTok rule (Everflow / Voluum /
    RedTrack) can match on the package-name substring. This test
    confirms the marker is present in a stable position (space-
    separated, at the tail) so those rules trigger reliably."""
    tt_a = coerce_ua_for_platform(BASE_ANDROID, "tiktok")
    # Package-name substring must be present exactly (case-sensitive)
    assert re.search(r"\bcom\.zhiliaoapp\.musically/\d+", tt_a), (
        f"Missing com.zhiliaoapp.musically/<code> marker in Android TikTok UA: {tt_a}"
    )
    tt_i = coerce_ua_for_platform(BASE_IOS, "tiktok")
    assert re.search(r"\bcom\.zhiliaoapp\.musically/\d+", tt_i), (
        f"Missing marker in iOS TikTok UA: {tt_i}"
    )


# ── Regression: v2.6.22 fixes still hold ───────────────────────

def test_regression_tiktok_android_no_chrome_safari():
    tt = coerce_ua_for_platform(BASE_ANDROID, "tiktok")
    assert "Chrome/" not in tt
    assert "Mobile Safari" not in tt
    assert "Cronet/" in tt

def test_regression_tiktok_ios_no_trailing_safari():
    tt = coerce_ua_for_platform(BASE_IOS, "tiktok")
    assert not re.search(r"\bSafari/[\d.]+\s*$", tt)
    assert "Version/26.4" not in tt

def test_regression_facebook_target_keeps_chrome_webview():
    fb = coerce_ua_for_platform(BASE_ANDROID, "facebook")
    assert "FBAV/" in fb
    assert "Chrome/" in fb  # Real FB Android WebView keeps Chrome
    assert "musical_ly" not in fb
