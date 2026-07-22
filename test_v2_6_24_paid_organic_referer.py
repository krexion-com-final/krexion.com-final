#!/usr/bin/env python3
"""
v2.6.24 Backend Verification Test Suite - Paid vs Organic Referer Split
Tests the new paid/organic referer pool feature across all 12 platforms.

CRITICAL: This test directly imports from backend module to test resolve_pro_visit
with traffic_type="paid" and traffic_type="organic" for all platforms.
"""

import sys
sys.path.insert(0, "/app/backend")

import requests
import json
from collections import Counter
from typing import Dict, List, Tuple
import re

# Configuration
BACKEND_URL = "http://localhost:8001"
API_BASE = f"{BACKEND_URL}/api"
ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "Admin@Krexion2025"

# Test results tracking
test_results = []
auth_token = None

# Import backend modules
try:
    from referrer_pro import (
        resolve_pro_visit,
        build_paid_organic_referer,
        detect_is_paid,
        build_inapp_deep_referer
    )
    print("✅ Successfully imported referrer_pro functions")
except ImportError as e:
    print(f"❌ Failed to import referrer_pro: {e}")
    sys.exit(1)


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f"\n   {details}"
    print(result)
    test_results.append({"name": test_name, "passed": passed, "details": details})
    return passed


def authenticate() -> str:
    """Authenticate and get JWT token"""
    global auth_token
    try:
        response = requests.post(
            f"{API_BASE}/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            auth_token = data.get("access_token")
            print(f"✅ Authenticated as {ADMIN_EMAIL}")
            return auth_token
        else:
            print(f"❌ Auth failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Auth exception: {e}")
        return None


def register_and_authenticate_user() -> str:
    """Register a test user and authenticate"""
    import time
    import random
    
    test_email = f"testuser_{int(time.time())}_{random.randint(1000, 9999)}@test.local"
    test_password = "TestPass123!"
    
    try:
        # Register user
        response = requests.post(
            f"{API_BASE}/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "name": "Test User v2.6.24"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"⚠️  User registration failed: {response.status_code} - {response.text[:200]}")
            return None
        
        # Login
        response = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": test_email, "password": test_password},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            user_token = data.get("access_token")
            print(f"✅ Registered and authenticated test user: {test_email}")
            return user_token
        else:
            print(f"⚠️  User login failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"⚠️  User registration exception: {e}")
        return None


def get_headers() -> Dict[str, str]:
    """Get headers with auth token"""
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


# ============================================================================
# TEST A: HEALTH + VERSION
# ============================================================================

def test_a_health():
    """Test A: Health endpoint"""
    print("\n" + "="*80)
    print("TEST A: HEALTH + VERSION")
    print("="*80)
    
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        passed = response.status_code == 200
        data = response.json() if passed else {}
        mongo_connected = data.get("mongo_connected", False)
        
        details = f"Status: {response.status_code}, mongo_connected: {mongo_connected}"
        return log_test("GET /health", passed and mongo_connected, details)
    except Exception as e:
        return log_test("GET /health", False, f"Exception: {e}")


def test_a_version():
    """Test A: Version endpoint"""
    try:
        response = requests.get(f"{API_BASE}/system/version", timeout=5)
        passed = response.status_code == 200
        data = response.json() if passed else {}
        version = data.get("version", "")
        
        version_match = version == "2.6.24"
        details = f"Status: {response.status_code}, version: {version}"
        return log_test("GET /api/system/version", passed and version_match, details)
    except Exception as e:
        return log_test("GET /api/system/version", False, f"Exception: {e}")


def test_a_public_latest():
    """Test A: Public latest version endpoint"""
    try:
        response = requests.get(f"{API_BASE}/system/public-latest", timeout=5)
        passed = response.status_code == 200
        data = response.json() if passed else {}
        current = data.get("current", "")
        
        version_match = current == "2.6.24"
        details = f"Status: {response.status_code}, current: {current}"
        return log_test("GET /api/system/public-latest", passed and version_match, details)
    except Exception as e:
        return log_test("GET /api/system/public-latest", False, f"Exception: {e}")


# ============================================================================
# TEST B: ADMIN AUTH
# ============================================================================

def test_b_admin_login():
    """Test B: Admin authentication"""
    print("\n" + "="*80)
    print("TEST B: ADMIN AUTH")
    print("="*80)
    
    token = authenticate()
    passed = token is not None
    details = f"Token received: {bool(token)}"
    return log_test("POST /api/admin/login", passed, details)


# ============================================================================
# TEST C: NEW PAID/ORGANIC REFERER LOGIC (MOST IMPORTANT)
# ============================================================================

def analyze_referer_distribution(platform: str, mode: str, referers: List[str]) -> Dict:
    """Analyze referer distribution and check for red flags"""
    
    # Count referer patterns
    counter = Counter()
    red_flags = []
    
    for ref in referers:
        if not ref or ref == "(empty)":
            counter["empty"] += 1
        else:
            # Truncate for grouping
            short_ref = ref[:80]
            counter[short_ref] += 1
    
    # Platform-specific red flag checks
    if platform == "tiktok" and mode == "paid":
        # RED FLAG: TikTok paid should NEVER emit video URLs
        video_urls = [r for r in referers if "www.tiktok.com/@user" in r and "/video/" in r]
        if video_urls:
            red_flags.append(f"CRITICAL: TikTok PAID emitted {len(video_urls)} video URLs (bug not fixed!)")
    
    if platform == "facebook" and mode == "organic":
        # RED FLAG: Facebook organic should NOT have __cft__[0] or __tn__
        cft_urls = [r for r in referers if "__cft__[0]" in r or "__tn__" in r]
        if cft_urls:
            red_flags.append(f"FAILURE: Facebook ORGANIC has {len(cft_urls)} URLs with paid markers (__cft__[0] or __tn__)")
    
    if platform == "facebook" and mode == "paid":
        # Facebook paid SHOULD have __cft__[0] in most l.facebook.com URLs
        facebook_urls = [r for r in referers if "l.facebook.com/l.php" in r]
        cft_urls = [r for r in facebook_urls if "__cft__[0]" in r]
        if facebook_urls and len(cft_urls) < len(facebook_urls) * 0.5:
            red_flags.append(f"WARNING: Facebook PAID has only {len(cft_urls)}/{len(facebook_urls)} URLs with __cft__[0] (expected >50%)")
    
    if platform == "google" and mode == "paid":
        # Google paid should be dominated by doubleclick
        doubleclick_urls = [r for r in referers if "googleads.g.doubleclick.net" in r]
        if len(doubleclick_urls) < len(referers) * 0.5:
            red_flags.append(f"FAILURE: Google PAID has only {len(doubleclick_urls)}/{len(referers)} doubleclick URLs (expected >50%)")
    
    if platform == "google" and mode == "organic":
        # Google organic should be mostly origin-only google.com/
        origin_only = [r for r in referers if r and re.match(r"^https?://(?:www\.)?google\.[a-z]+/?$", r)]
        if len(origin_only) < len(referers) * 0.7:
            red_flags.append(f"WARNING: Google ORGANIC has only {len(origin_only)}/{len(referers)} origin-only URLs (expected >70%)")
    
    if platform in ["snapchat"]:
        # Snapchat should be mostly empty
        empty_count = counter.get("empty", 0)
        if empty_count < len(referers) * 0.7:
            red_flags.append(f"WARNING: {platform.upper()} has only {empty_count}/{len(referers)} empty referers (expected >70%)")
    
    # Calculate distribution percentages
    total = len(referers)
    distribution = {k: (v / total * 100) for k, v in counter.most_common(10)}
    
    return {
        "counter": counter,
        "distribution": distribution,
        "red_flags": red_flags,
        "total": total
    }


def test_c_paid_organic_referer_logic():
    """Test C: NEW Paid/Organic referer logic for all 12 platforms"""
    print("\n" + "="*80)
    print("TEST C: NEW PAID/ORGANIC REFERER LOGIC (MOST IMPORTANT)")
    print("="*80)
    
    platforms = [
        "tiktok", "facebook", "instagram", "twitter", "youtube", "linkedin",
        "snapchat", "pinterest", "reddit", "google", "bing", "messenger"
    ]
    
    all_passed = True
    all_red_flags = []
    
    for platform in platforms:
        print(f"\n{'─'*80}")
        print(f"Testing platform: {platform.upper()}")
        print(f"{'─'*80}")
        
        for mode in ["paid", "organic"]:
            print(f"\n  Mode: {mode.upper()}")
            
            try:
                refs = []
                for i in range(30):
                    result = resolve_pro_visit(
                        ua="Mozilla/5.0 (Linux; Android 14; SM-S928B; wv) AppleWebKit/537.36 musical_ly_2024",
                        platform_pool_value=f"{platform}:100",
                        target_url="https://offer.example.com/lp",
                        country="US",
                        traffic_type=mode,
                        campaign_type="auto",
                    )
                    referer = result.get("referer", "")
                    # Store full referer for analysis, truncate only for display
                    refs.append(referer if referer else "(empty)")
                
                # Analyze distribution
                analysis = analyze_referer_distribution(platform, mode, refs)
                
                # Print top 5 distribution
                print(f"    Top 5 referers:")
                for ref, pct in list(analysis["distribution"].items())[:5]:
                    # Truncate for display only
                    display_ref = ref[:80] if len(ref) > 80 else ref
                    print(f"      {pct:5.1f}% - {display_ref}")
                
                # Check for red flags
                if analysis["red_flags"]:
                    all_passed = False
                    for flag in analysis["red_flags"]:
                        print(f"    🚨 {flag}")
                        all_red_flags.append(f"{platform}/{mode}: {flag}")
                else:
                    print(f"    ✅ No red flags detected")
                
            except Exception as e:
                all_passed = False
                error_msg = f"{platform}/{mode}: Exception: {str(e)[:200]}"
                print(f"    ❌ {error_msg}")
                all_red_flags.append(error_msg)
    
    # Summary
    print(f"\n{'='*80}")
    print("PAID/ORGANIC REFERER LOGIC SUMMARY")
    print(f"{'='*80}")
    
    if all_red_flags:
        print(f"\n🚨 FOUND {len(all_red_flags)} RED FLAGS:")
        for flag in all_red_flags:
            print(f"  • {flag}")
    else:
        print("\n✅ ALL PLATFORMS PASSED - NO RED FLAGS DETECTED")
    
    details = f"Tested {len(platforms)} platforms × 2 modes × 30 samples = {len(platforms) * 2 * 30} total calls"
    if all_red_flags:
        details += f"\nRed flags: {len(all_red_flags)}"
    
    return log_test("Paid/Organic referer logic (all platforms)", all_passed, details)


# ============================================================================
# TEST D: BACKWARDS COMPATIBILITY
# ============================================================================

def test_d_backwards_compat():
    """Test D: Backwards compatibility - legacy behavior preserved"""
    print("\n" + "="*80)
    print("TEST D: BACKWARDS COMPATIBILITY")
    print("="*80)
    
    all_passed = True
    
    # Test 1: build_inapp_deep_referer WITHOUT is_paid kwarg (legacy)
    print("\n  Test 1: Legacy build_inapp_deep_referer (no is_paid kwarg)")
    try:
        result = build_inapp_deep_referer("tiktok", "https://offer.com")
        # Should return something (not None) - legacy behavior
        passed = result is not None
        details = f"Returned: {result[:80] if result else 'None'}"
        print(f"    Result: {details}")
        log_test("Legacy build_inapp_deep_referer", passed, details)
        all_passed = all_passed and passed
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        log_test("Legacy build_inapp_deep_referer", False, f"Exception: {e}")
        all_passed = False
    
    # Test 2: detect_is_paid function
    print("\n  Test 2: detect_is_paid function")
    test_cases = [
        ("paid", "auto", "tiktok", True),
        ("organic", "auto", "facebook", False),
        ("auto", "video_ad", "tiktok", True),
        ("auto", "auto", "google", False),
        ("auto", "auto", "unknown_platform", None),
    ]
    
    for traffic_type, campaign_type, platform, expected in test_cases:
        try:
            result = detect_is_paid(traffic_type, campaign_type, platform)
            passed = result == expected
            details = f"detect_is_paid('{traffic_type}', '{campaign_type}', '{platform}') = {result} (expected {expected})"
            print(f"    {details}")
            log_test(f"detect_is_paid({traffic_type}, {campaign_type}, {platform})", passed, details)
            all_passed = all_passed and passed
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            log_test(f"detect_is_paid({traffic_type}, {campaign_type}, {platform})", False, f"Exception: {e}")
            all_passed = False
    
    # Test 3: detect_is_paid with "mixed" mode (should be random)
    print("\n  Test 3: detect_is_paid with 'mixed' mode (100 samples)")
    try:
        results = [detect_is_paid("mixed", "auto", "facebook") for _ in range(100)]
        true_count = sum(1 for r in results if r is True)
        false_count = sum(1 for r in results if r is False)
        
        # Should be roughly 50/50 (allow 35-65% range for randomness)
        passed = 35 <= true_count <= 65
        details = f"True: {true_count}%, False: {false_count}% (expected ~50/50)"
        print(f"    {details}")
        log_test("detect_is_paid mixed mode randomness", passed, details)
        all_passed = all_passed and passed
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        log_test("detect_is_paid mixed mode randomness", False, f"Exception: {e}")
        all_passed = False
    
    return all_passed


# ============================================================================
# TEST E: LINK CRUD WITH NEW FIELD
# ============================================================================

def test_e_link_crud():
    """Test E: Link CRUD with new referrer_pro_traffic_type field"""
    print("\n" + "="*80)
    print("TEST E: LINK CRUD WITH NEW FIELD")
    print("="*80)
    
    # Register a test user for link operations
    user_token = register_and_authenticate_user()
    if not user_token:
        print("❌ Skipping - could not register test user")
        return log_test("Link CRUD", False, "Could not register test user")
    
    all_passed = True
    link_id = None
    
    # Test 1: Create link with referrer_pro_traffic_type="paid"
    print("\n  Test 1: Create link with referrer_pro_traffic_type='paid'")
    try:
        response = requests.post(
            f"{API_BASE}/links",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
            json={
                "name": "Test v2.6.24 Paid Link",
                "offer_url": "https://example.com/offer",
                "referrer_pro_enabled": True,
                "referrer_pro_traffic_type": "paid"
            },
            timeout=10
        )
        
        passed = response.status_code == 200
        if passed:
            data = response.json()
            link_id = data.get("id")
            traffic_type = data.get("referrer_pro_traffic_type")
            passed = traffic_type == "paid"
            details = f"Created link {link_id}, traffic_type: {traffic_type}"
        else:
            details = f"Status: {response.status_code}, Response: {response.text[:200]}"
        
        print(f"    {details}")
        log_test("Create link with traffic_type=paid", passed, details)
        all_passed = all_passed and passed
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        log_test("Create link with traffic_type=paid", False, f"Exception: {e}")
        all_passed = False
    
    # Test 2: PATCH link to change to "organic"
    if link_id:
        print("\n  Test 2: PATCH link to change traffic_type to 'organic'")
        try:
            response = requests.patch(
                f"{API_BASE}/links/{link_id}",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                json={"referrer_pro_traffic_type": "organic"},
                timeout=10
            )
            
            passed = response.status_code == 200
            if passed:
                data = response.json()
                traffic_type = data.get("referrer_pro_traffic_type")
                passed = traffic_type == "organic"
                details = f"Updated link {link_id}, traffic_type: {traffic_type}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            print(f"    {details}")
            log_test("PATCH link traffic_type to organic", passed, details)
            all_passed = all_passed and passed
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            log_test("PATCH link traffic_type to organic", False, f"Exception: {e}")
            all_passed = False
    
    # Test 3: GET link to verify persistence
    if link_id:
        print("\n  Test 3: GET link to verify traffic_type persisted")
        try:
            response = requests.get(
                f"{API_BASE}/links/{link_id}",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                timeout=10
            )
            
            passed = response.status_code == 200
            if passed:
                data = response.json()
                traffic_type = data.get("referrer_pro_traffic_type")
                passed = traffic_type == "organic"
                details = f"Link {link_id}, traffic_type: {traffic_type} (expected 'organic')"
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            print(f"    {details}")
            log_test("GET link verifies traffic_type persistence", passed, details)
            all_passed = all_passed and passed
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            log_test("GET link verifies traffic_type persistence", False, f"Exception: {e}")
            all_passed = False
    
    # Cleanup: Delete test link
    if link_id:
        print("\n  Cleanup: Delete test link")
        try:
            response = requests.delete(
                f"{API_BASE}/links/{link_id}",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                timeout=10
            )
            print(f"    Deleted link {link_id}")
        except Exception as e:
            print(f"    ⚠️  Cleanup failed: {e}")
    
    return all_passed


# ============================================================================
# TEST F: RELEASES MODULE
# ============================================================================

def test_f_releases():
    """Test F: Releases module - verify v2.6.24 release entry"""
    print("\n" + "="*80)
    print("TEST F: RELEASES MODULE")
    print("="*80)
    
    if not auth_token:
        print("❌ Skipping - no auth token")
        return log_test("Releases module", False, "No auth token")
    
    try:
        response = requests.get(
            f"{API_BASE}/admin/releases",
            headers=get_headers(),
            timeout=10
        )
        
        passed = response.status_code == 200
        if passed:
            data = response.json()
            releases = data.get("releases", [])
            
            # Find v2.6.24 release
            v2_6_24 = None
            for release in releases:
                if release.get("version") == "2.6.24":
                    v2_6_24 = release
                    break
            
            if v2_6_24:
                published = v2_6_24.get("published", False)
                severity = v2_6_24.get("severity", "")
                passed = published and severity == "recommended"
                details = f"Found v2.6.24: published={published}, severity={severity}"
            else:
                passed = False
                details = f"v2.6.24 not found in releases list (found {len(releases)} releases)"
        else:
            details = f"Status: {response.status_code}, Response: {response.text[:200]}"
        
        print(f"  {details}")
        return log_test("GET /api/admin/releases", passed, details)
    except Exception as e:
        print(f"  ❌ Exception: {e}")
        return log_test("GET /api/admin/releases", False, f"Exception: {e}")


# ============================================================================
# TEST G: NO REGRESSION
# ============================================================================

def test_g_no_regression():
    """Test G: No regression - existing endpoints still work"""
    print("\n" + "="*80)
    print("TEST G: NO REGRESSION")
    print("="*80)
    
    all_passed = True
    
    # Test 1: /api/diagnostics/health
    print("\n  Test 1: GET /api/diagnostics/health")
    try:
        response = requests.get(f"{API_BASE}/diagnostics/health", timeout=5)
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        print(f"    {details}")
        log_test("GET /api/diagnostics/health", passed, details)
        all_passed = all_passed and passed
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        log_test("GET /api/diagnostics/health", False, f"Exception: {e}")
        all_passed = False
    
    # Test 2: Create link WITHOUT referrer_pro fields (legacy)
    print("\n  Test 2: Create link WITHOUT referrer_pro fields (legacy)")
    
    # Register a test user for link operations
    user_token = register_and_authenticate_user()
    if user_token:
        try:
            response = requests.post(
                f"{API_BASE}/links",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                json={
                    "name": "Test Legacy Link",
                    "offer_url": "https://example.com/legacy"
                },
                timeout=10
            )
            
            passed = response.status_code == 200
            if passed:
                data = response.json()
                link_id = data.get("id")
                # Should have default traffic_type="auto"
                traffic_type = data.get("referrer_pro_traffic_type", "auto")
                passed = traffic_type == "auto"
                details = f"Created legacy link {link_id}, traffic_type: {traffic_type} (expected 'auto')"
                
                # Cleanup
                try:
                    requests.delete(
                        f"{API_BASE}/links/{link_id}",
                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {user_token}"},
                        timeout=5
                    )
                except Exception:
                    pass
            else:
                details = f"Status: {response.status_code}, Response: {response.text[:200]}"
            
            print(f"    {details}")
            log_test("Create legacy link (no pro fields)", passed, details)
            all_passed = all_passed and passed
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            log_test("Create legacy link (no pro fields)", False, f"Exception: {e}")
            all_passed = False
    else:
        print(f"    ⚠️  Skipping - could not register test user")
        log_test("Create legacy link (no pro fields)", False, "Could not register test user")
        all_passed = False
    
    # Test 3: Backend import health
    print("\n  Test 3: Backend import health")
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-c", "import server"],
            cwd="/app/backend",
            capture_output=True,
            text=True,
            timeout=30
        )
        
        passed = result.returncode == 0
        details = f"Exit code: {result.returncode}"
        if result.stderr and "Error" in result.stderr:
            details += f"\nStderr: {result.stderr[:200]}"
        
        print(f"    {details}")
        log_test("Backend import (python -c 'import server')", passed, details)
        all_passed = all_passed and passed
    except Exception as e:
        print(f"    ❌ Exception: {e}")
        log_test("Backend import (python -c 'import server')", False, f"Exception: {e}")
        all_passed = False
    
    return all_passed


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("v2.6.24 BACKEND VERIFICATION TEST SUITE")
    print("Paid vs Organic Referer Split Feature")
    print("="*80)
    
    # Run all tests
    test_a_health()
    test_a_version()
    test_a_public_latest()
    test_b_admin_login()
    test_c_paid_organic_referer_logic()
    test_d_backwards_compat()
    test_e_link_crud()
    test_f_releases()
    test_g_no_regression()
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    success_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count} ✅")
    print(f"Failed: {total_count - passed_count} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    
    # List failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
        for test in failed_tests:
            print(f"  • {test['name']}")
            if test['details']:
                print(f"    {test['details']}")
    else:
        print("\n✅ ALL TESTS PASSED!")
    
    # Production-ready verdict
    print("\n" + "="*80)
    print("PRODUCTION-READY VERDICT")
    print("="*80)
    
    if passed_count == total_count:
        print("\n✅ v2.6.24 is PRODUCTION-READY")
        print("   All tests passed. The Paid vs Organic referer split feature is working correctly.")
    else:
        print(f"\n⚠️  v2.6.24 has {total_count - passed_count} failing test(s)")
        print("   Review failed tests before deploying to production.")
    
    return 0 if passed_count == total_count else 1


if __name__ == "__main__":
    sys.exit(main())
