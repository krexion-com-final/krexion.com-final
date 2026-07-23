"""Iteration 20 — extra verification for v2.6.27 fixes.

Focused on the exact acceptance criteria from the review request:
 - TikTok Android UA contains FB_IAB TikTokAndroid bracket in canonical shape
 - _fbav_3part normaliser correctness
 - Facebook Android/iOS UA FBAV 3-part + FBAN slug presence
 - coerce_ua_for_platform idempotency + cross-platform strip
 - _build_fallbacks iframe_path forwarding + sanitisation
"""
import re
import sys
import pathlib

# Ensure backend on path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import server
import referrer_pro
import visual_recorder


TIKTOK_ANDROID_BRACKET_RE = re.compile(
    r"\[FB_IAB/;FBAN/TikTokAndroid;FBAV/\d+\.\d+\.\d+;IABMV/1;FBBV/\d+;FBOP/19;\]"
)


DEV = {"and_ver": "14", "model": "SM-S928B", "build": "UP1A.231005.007", "sdk": "34"}


class TestTikTokAndroidBracket:
    def test_ua_tiktok_android_contains_bracket_30_iterations(self):
        vers = ["44.7.0", "43.5.0", "42.7.0"]
        for v in vers:
            for _ in range(10):
                ua = server._ua_tiktok_android(DEV, v)
                assert TIKTOK_ANDROID_BRACKET_RE.search(ua), f"missing bracket in: {ua}"
                # v2.6.26 markers still present
                assert f"TikTok/{v}" in ua, f"missing TikTok/{{ver}} slug: {ua}"
                assert re.search(r"musical_ly_\d+", ua), f"missing musical_ly marker: {ua}"
                assert "com.zhiliaoapp.musically/" in ua, f"missing musically pkg: {ua}"

    def test_build_inapp_ua_suffix_tiktok_20_iters(self):
        android_base = (
            "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        for _ in range(25):
            out = referrer_pro.build_inapp_ua_suffix("tiktok", android_base)
            assert out.startswith("TikTok/"), f"does not start with TikTok/: {out!r}"
            assert TIKTOK_ANDROID_BRACKET_RE.search(out), f"missing bracket: {out!r}"


class TestFbav3Part:
    def test_cases(self):
        f = server._fbav_3part
        assert f("557.0") == "557.0.0"
        assert f("550.0.0.45.102") == "550.0.0"
        assert f("461.0.0") == "461.0.0"
        assert f("") == "0.0.0"
        assert f("1") == "1.0.0"
        assert f("1.2") == "1.2.0"


class TestFacebookUAs:
    def test_fb_android_2part_input(self):
        ua = server._ua_facebook_android(DEV, "557.0", "128.0.6613.127")
        assert "FBAV/557.0.0;" in ua
        assert "FB_IAB/FB4A;" in ua
        assert "FBAN/FB4A;" in ua
        assert re.search(r"FBBV/\d+", ua)

    def test_fb_android_5part_input(self):
        ua = server._ua_facebook_android(DEV, "550.0.0.45.102", "128.0.6613.127")
        assert "FBAV/550.0.0;" in ua
        assert "FB_IAB/FB4A;" in ua
        assert "FBAN/FB4A;" in ua

    def test_fb_ios_normalisation(self):
        ios_dev = {"brand": "iPhone", "ios": "17_5", "model": "iPhone15,3", "scale": "3"}
        ua = server._ua_facebook_ios(ios_dev, "461.0.0.30.100")
        assert "FBAV/461.0.0;" in ua
        assert "FBAN/FBIOS;" in ua
        assert re.search(r"FBSN/iOS;FBSV/\d", ua)


class TestCoerceIdempotency:
    def test_coerce_tiktok_preserves_own_signature(self):
        ua = server._ua_tiktok_android(DEV, "44.7.0")
        out = referrer_pro.coerce_ua_for_platform(ua, "tiktok")
        assert "FBAN/TikTokAndroid" in out
        assert "TikTok/" in out
        assert re.search(r"musical_ly_\d+", out)

    def test_coerce_fb_preserves_fb_signature(self):
        ua = server._ua_facebook_android(DEV, "557.0", "128.0.6613.127")
        out = referrer_pro.coerce_ua_for_platform(ua, "facebook")
        assert "FB_IAB/FB4A" in out
        assert "FBAN/FB4A" in out
        assert re.search(r"FBAV/\d+\.\d+\.\d+", out)


class TestCoerceCrossPlatform:
    def test_strip_tiktok_when_coercing_away(self):
        ua = server._ua_tiktok_android(DEV, "44.7.0")
        for target in ["facebook", "instagram", "snapchat", "twitter", "google", "youtube"]:
            out = referrer_pro.coerce_ua_for_platform(ua, target)
            assert "FBAN/TikTokAndroid" not in out, f"[{target}] TikTokAndroid bracket leaked: {out}"
            assert "TikTok/" not in out, f"[{target}] TikTok/ leaked: {out}"
            assert not re.search(r"musical_ly_\d+", out), f"[{target}] musical_ly leaked: {out}"
            assert "BytedanceWebview" not in out
            assert "com.zhiliaoapp.musically" not in out

    def test_fb_to_tiktok_strips_fb_slugs(self):
        ua = server._ua_facebook_android(DEV, "557.0", "128.0.6613.127")
        out = referrer_pro.coerce_ua_for_platform(ua, "tiktok")
        assert "FB_IAB/FB4A" not in out, f"FB4A leaked: {out}"
        assert "FBAN/FB4A" not in out, f"FBAN/FB4A leaked: {out}"
        assert "TikTok/" in out
        assert re.search(r"musical_ly_\d+", out)
        assert "FBAN/TikTokAndroid" in out


class TestBuildFallbacksIframePath:
    def _call(self, info):
        # _build_fallbacks is module-level in visual_recorder
        return visual_recorder._build_fallbacks(info)

    def test_empty_list_omitted(self):
        fb = self._call({"iframe_path": []})
        assert "iframe_path" not in fb

    def test_populated_list_included(self):
        paths = ["iframe#a", "iframe.b"]
        fb = self._call({"iframe_path": paths})
        assert fb.get("iframe_path") == paths

    def test_junk_entries_filtered(self):
        fb = self._call({"iframe_path": ["iframe#a", None, 42, "x" * 5000, "iframe.b"]})
        got = fb.get("iframe_path", [])
        # Legit entries preserved
        assert "iframe#a" in got
        assert "iframe.b" in got
        # Junk stripped
        assert None not in got
        assert 42 not in got
        assert all(isinstance(x, str) and len(x) <= 5000 for x in got)

    def test_non_list_ignored(self):
        fb = self._call({"iframe_path": "iframe#a"})
        assert "iframe_path" not in fb


class TestUserAgentsLibParse:
    """Sanity: `user_agents` sees FBAN=TikTokAndroid bracket; family may say Facebook
    (generic FB_IAB rule) — this is EXPECTED per Everflow more-specific FBAN match."""

    def test_parse_no_exception(self):
        try:
            from user_agents import parse
        except Exception:
            import pytest
            pytest.skip("user_agents not installed")
        ua = server._ua_tiktok_android(DEV, "44.7.0")
        p = parse(ua)
        # Do NOT assert family == TikTok — see docstring; assert it parses cleanly + is mobile
        assert p.is_mobile or p.is_tablet
