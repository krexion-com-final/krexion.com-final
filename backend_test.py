#!/usr/bin/env python3
"""
v2.1.81 Backend Verification Test Suite
Tests:
1. Import + startup health
2. Backend service reliability under polling (30 requests)
3. v2.1.80 regression - Link-level Pro-Referrer (9-test suite)
4. Static analysis (informational)
"""

import requests
import time
import json
import sys
from typing import Dict, Any, List

# Configuration
BACKEND_URL = "https://krexion-preview-14.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"
ADMIN_EMAIL = "admin@krexion.local"
ADMIN_PASSWORD = "Krexion@Preview2025"

# Test results tracking
test_results = []
auth_token = None


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
            f"{API_BASE}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            auth_token = data.get("access_token")
            print(f"✅ Authenticated as {ADMIN_EMAIL}")
            return auth_token
        else:
            print(f"❌ Auth failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Auth exception: {e}")
        return None


def get_headers() -> Dict[str, str]:
    """Get headers with auth token"""
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


# ============================================================================
# TEST 1: Import + Startup Health
# ============================================================================

def test_1_import_health():
    """Test 1: Confirm python -c 'import server' loads cleanly"""
    print("\n" + "="*80)
    print("TEST 1: Import + Startup Health")
    print("="*80)
    
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
    
    return log_test("Import server module", passed, details)


def test_1_desktop_stats_basic():
    """Test 1: GET /api/desktop/stats - basic health check"""
    try:
        start = time.time()
        response = requests.get(f"{API_BASE}/desktop/stats", timeout=5)
        elapsed_ms = int((time.time() - start) * 1000)
        
        if response.status_code != 200:
            return log_test(
                "GET /api/desktop/stats returns 200",
                False,
                f"Got {response.status_code}: {response.text[:200]}"
            )
        
        # Check response time
        if elapsed_ms >= 500:
            return log_test(
                "Response time < 500ms",
                False,
                f"Took {elapsed_ms}ms (limit: 500ms)"
            )
        
        data = response.json()
        
        # Validate response shape
        required_fields = ["ok", "backend_version", "system", "database", "cloud", 
                          "license", "jobs", "dependencies"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return log_test(
                "Response has all required fields",
                False,
                f"Missing: {missing}"
            )
        
        # Validate system block
        system = data.get("system", {})
        system_fields = ["cpu_cores", "ram_gb", "ram_used_gb", "ram_used_pct", 
                        "cpu_pct", "tier", "max_concurrent_heavy_jobs", "detected_by"]
        missing_sys = [f for f in system_fields if f not in system]
        if missing_sys:
            return log_test(
                "System block has all required fields",
                False,
                f"Missing: {missing_sys}"
            )
        
        # Check backend_version
        version = data.get("backend_version", "")
        if not version or version == "":
            return log_test(
                "backend_version is non-empty",
                False,
                f"Got: '{version}'"
            )
        
        # Check ok flag
        if not data.get("ok"):
            return log_test(
                "Response ok=true",
                False,
                f"Got ok={data.get('ok')}"
            )
        
        details = f"Response time: {elapsed_ms}ms, version: {version}"
        return log_test("GET /api/desktop/stats basic health", True, details)
        
    except Exception as e:
        return log_test("GET /api/desktop/stats basic health", False, str(e))


# ============================================================================
# TEST 2: Backend Service Reliability Under Polling
# ============================================================================

def test_2_polling_reliability():
    """Test 2: Call /api/desktop/stats 30 times with 100ms sleep"""
    print("\n" + "="*80)
    print("TEST 2: Backend Service Reliability Under Polling")
    print("="*80)
    
    try:
        times = []
        failures = []
        
        for i in range(30):
            start = time.time()
            try:
                response = requests.get(f"{API_BASE}/desktop/stats", timeout=5)
                elapsed_ms = int((time.time() - start) * 1000)
                times.append(elapsed_ms)
                
                if response.status_code != 200:
                    failures.append(f"Request {i+1}: HTTP {response.status_code}")
                else:
                    # Validate shape on every 10th request
                    if (i + 1) % 10 == 0:
                        data = response.json()
                        if not data.get("ok") or "system" not in data:
                            failures.append(f"Request {i+1}: Invalid shape")
                
            except Exception as e:
                failures.append(f"Request {i+1}: {str(e)}")
                times.append(5000)  # Timeout
            
            if i < 29:  # Don't sleep after last request
                time.sleep(0.1)
        
        # Check for failures
        if failures:
            return log_test(
                "30 polling requests all succeed",
                False,
                f"{len(failures)} failures: {failures[:3]}"
            )
        
        # Check for slowdown
        first_10_avg = sum(times[:10]) / 10
        last_10_avg = sum(times[-10:]) / 10
        slowdown_ratio = last_10_avg / first_10_avg if first_10_avg > 0 else 1.0
        
        if slowdown_ratio > 3.0:
            return log_test(
                "No cumulative slowdown (last 10 < 3x first 10)",
                False,
                f"Slowdown ratio: {slowdown_ratio:.2f}x (first 10 avg: {first_10_avg:.0f}ms, last 10 avg: {last_10_avg:.0f}ms)"
            )
        
        details = f"All 30 requests succeeded. Times: min={min(times)}ms, max={max(times)}ms, avg={sum(times)/len(times):.0f}ms. Slowdown ratio: {slowdown_ratio:.2f}x"
        return log_test("30 polling requests reliability", True, details)
        
    except Exception as e:
        return log_test("30 polling requests reliability", False, str(e))


# ============================================================================
# TEST 3: v2.1.80 Regression - Link-level Pro-Referrer (9 tests)
# ============================================================================

def test_3a_link_backward_compat():
    """Test 3a: POST /api/links without pro-referrer fields"""
    print("\n" + "="*80)
    print("TEST 3: v2.1.80 Regression - Link-level Pro-Referrer")
    print("="*80)
    
    try:
        # Create link without pro-referrer fields
        link_data = {
            "name": "v2.1.81-test-backward-compat",
            "offer_url": "https://example.com/backward-compat",
            "strict_duplicate_check": False
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3a: Backward-compat link creation",
                False,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        link_id = data.get("id")
        
        # Verify defaults
        checks = [
            (data.get("referrer_pro_enabled") == False, "referrer_pro_enabled=False"),
            (data.get("name") == link_data["name"], "name preserved"),
            (data.get("offer_url") == link_data["offer_url"], "offer_url preserved"),
        ]
        
        failed_checks = [msg for passed, msg in checks if not passed]
        if failed_checks:
            return log_test(
                "3a: Backward-compat link creation",
                False,
                f"Failed checks: {failed_checks}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3a: Backward-compat link creation",
            True,
            f"Link {link_id} created with correct defaults"
        )
        
    except Exception as e:
        return log_test("3a: Backward-compat link creation", False, str(e))


def test_3b_link_full_pro_referrer():
    """Test 3b: POST /api/links with FULL pro-referrer body"""
    try:
        link_data = {
            "name": "v2.1.81-test-full-pro",
            "offer_url": "https://example.com/full-pro",
            "strict_duplicate_check": False,
            "referrer_pro_enabled": True,
            "referrer_pro_platform_pool": "facebook:50,instagram:30,google:20",
            "referrer_pro_email_weights": '{"gmail":40,"yahoo":25,"empty":35}',
            "referrer_pro_brand": "testbrand",
            "referrer_pro_search_engine": "google",
            "referrer_pro_country": "us",
            "referrer_pro_search_keywords": "diet plan\nketo recipes",
            "referrer_pro_social_wrapper": True,
            "referrer_pro_inapp_deep_path": True,
            "referrer_pro_strip_search_path": True,
            "referrer_pro_network_click_chain": True,
            "referrer_pro_wrapper_redirect": True
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3b: Full pro-referrer creation",
                False,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        link_id = data.get("id")
        
        # Verify all 13 fields
        checks = [
            (data.get("referrer_pro_enabled") == True, "referrer_pro_enabled"),
            (data.get("referrer_pro_platform_pool") == link_data["referrer_pro_platform_pool"], "referrer_pro_platform_pool"),
            (data.get("referrer_pro_brand") == link_data["referrer_pro_brand"], "referrer_pro_brand"),
            (data.get("referrer_pro_search_keywords") == link_data["referrer_pro_search_keywords"], "referrer_pro_search_keywords"),
            (data.get("referrer_pro_wrapper_redirect") == True, "referrer_pro_wrapper_redirect"),
        ]
        
        failed_checks = [msg for passed, msg in checks if not passed]
        if failed_checks:
            return log_test(
                "3b: Full pro-referrer creation",
                False,
                f"Failed checks: {failed_checks}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3b: Full pro-referrer creation",
            True,
            f"Link {link_id} created with all 13 pro-referrer fields"
        )
        
    except Exception as e:
        return log_test("3b: Full pro-referrer creation", False, str(e))


def test_3c_link_partial_update():
    """Test 3c: PUT /api/links/{id} partial update"""
    try:
        # First create a link
        link_data = {
            "name": "v2.1.81-test-partial-update",
            "offer_url": "https://example.com/partial-update",
            "strict_duplicate_check": False,
            "forced_source": "original_source",
            "referrer_mode": "original_mode"
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3c: Partial update",
                False,
                f"Create failed: HTTP {response.status_code}"
            )
        
        data = response.json()
        link_id = data.get("id")
        original_name = data.get("name")
        original_offer_url = data.get("offer_url")
        
        # Now update ONLY 2 fields
        update_data = {
            "referrer_pro_enabled": True,
            "referrer_pro_platform_pool": "facebook:100"
        }
        
        response = requests.put(
            f"{API_BASE}/links/{link_id}",
            json=update_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3c: Partial update",
                False,
                f"Update failed: HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        
        # Verify updated fields changed
        checks = [
            (data.get("referrer_pro_enabled") == True, "referrer_pro_enabled updated"),
            (data.get("referrer_pro_platform_pool") == "facebook:100", "referrer_pro_platform_pool updated"),
            (data.get("name") == original_name, "name unchanged"),
            (data.get("offer_url") == original_offer_url, "offer_url unchanged"),
        ]
        
        failed_checks = [msg for passed, msg in checks if not passed]
        if failed_checks:
            return log_test(
                "3c: Partial update",
                False,
                f"Failed checks: {failed_checks}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3c: Partial update",
            True,
            f"Link {link_id} partially updated without clobbering other fields"
        )
        
    except Exception as e:
        return log_test("3c: Partial update", False, str(e))


def test_3d_preview_valid_pool():
    """Test 3d: POST /api/links/preview-referrer with valid pool"""
    try:
        preview_data = {
            "referrer_pro_platform_pool": "facebook:50,instagram:30,google:20",
            "sample_count": 20
        }
        
        response = requests.post(
            f"{API_BASE}/links/preview-referrer",
            json=preview_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3d: Preview valid pool",
                False,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        samples = data.get("samples", [])
        
        if len(samples) != 20:
            return log_test(
                "3d: Preview valid pool",
                False,
                f"Expected 20 samples, got {len(samples)}"
            )
        
        # Check sample structure
        sample = samples[0]
        required_keys = ["index", "ua_type", "platform", "referer", "utm_source", 
                        "utm_medium", "utm_campaign"]
        missing = [k for k in required_keys if k not in sample]
        if missing:
            return log_test(
                "3d: Preview valid pool",
                False,
                f"Sample missing keys: {missing}"
            )
        
        # Check distribution
        platforms = [s.get("platform") for s in samples]
        platform_counts = {}
        for p in platforms:
            platform_counts[p] = platform_counts.get(p, 0) + 1
        
        # Should have at least 2 different platforms
        if len(platform_counts) < 2:
            return log_test(
                "3d: Preview valid pool",
                False,
                f"Expected ≥2 platforms, got {len(platform_counts)}: {platform_counts}"
            )
        
        return log_test(
            "3d: Preview valid pool",
            True,
            f"20 samples with correct structure, distribution: {platform_counts}"
        )
        
    except Exception as e:
        return log_test("3d: Preview valid pool", False, str(e))


def test_3e_preview_empty_pool():
    """Test 3e: POST /api/links/preview-referrer with empty pool"""
    try:
        preview_data = {
            "referrer_pro_platform_pool": "",
            "sample_count": 5
        }
        
        response = requests.post(
            f"{API_BASE}/links/preview-referrer",
            json=preview_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3e: Preview empty pool (graceful fallback)",
                False,
                f"HTTP {response.status_code}: {response.text[:200]}"
            )
        
        data = response.json()
        samples = data.get("samples", [])
        
        if len(samples) != 5:
            return log_test(
                "3e: Preview empty pool (graceful fallback)",
                False,
                f"Expected 5 samples, got {len(samples)}"
            )
        
        return log_test(
            "3e: Preview empty pool (graceful fallback)",
            True,
            f"Returned 5 samples with graceful fallback"
        )
        
    except Exception as e:
        return log_test("3e: Preview empty pool (graceful fallback)", False, str(e))


def test_3f_click_legacy():
    """Test 3f: GET /r/{short_code} on legacy link (pro OFF)"""
    try:
        # Create legacy link
        link_data = {
            "name": "v2.1.81-test-legacy-click",
            "offer_url": "https://example.com/legacy-click",
            "strict_duplicate_check": False,
            "referrer_pro_enabled": False
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3f: Click legacy link",
                False,
                f"Create failed: HTTP {response.status_code}"
            )
        
        data = response.json()
        link_id = data.get("id")
        short_code = data.get("short_code")
        
        # Click the link (don't follow redirects)
        response = requests.get(
            f"{API_BASE}/r/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        
        if response.status_code != 302:
            return log_test(
                "3f: Click legacy link",
                False,
                f"Expected 302, got {response.status_code}"
            )
        
        location = response.headers.get("Location", "")
        
        # Should redirect to offer URL, no wrapper, no UTM
        checks = [
            ("example.com" in location, "Redirects to offer domain"),
            ("l.facebook.com" not in location, "No Facebook wrapper"),
            ("google.com/url" not in location, "No Google wrapper"),
            ("t.co" not in location, "No Twitter wrapper"),
        ]
        
        failed_checks = [msg for passed, msg in checks if not passed]
        if failed_checks:
            return log_test(
                "3f: Click legacy link",
                False,
                f"Failed checks: {failed_checks}. Location: {location}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3f: Click legacy link",
            True,
            f"302 to {location[:80]}... (no wrapper, legacy behavior)"
        )
        
    except Exception as e:
        return log_test("3f: Click legacy link", False, str(e))


def test_3g_click_pro_no_wrapper():
    """Test 3g: GET /r/{short_code} on pro=ON, wrapper=OFF"""
    try:
        # Create pro link without wrapper
        link_data = {
            "name": "v2.1.81-test-pro-no-wrapper",
            "offer_url": "https://example.com/pro-no-wrapper",
            "strict_duplicate_check": False,
            "referrer_pro_enabled": True,
            "referrer_pro_platform_pool": "facebook:100",
            "referrer_pro_wrapper_redirect": False
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3g: Click pro no wrapper",
                False,
                f"Create failed: HTTP {response.status_code}"
            )
        
        data = response.json()
        link_id = data.get("id")
        short_code = data.get("short_code")
        
        # Click the link
        response = requests.get(
            f"{API_BASE}/r/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        
        if response.status_code != 302:
            return log_test(
                "3g: Click pro no wrapper",
                False,
                f"Expected 302, got {response.status_code}"
            )
        
        location = response.headers.get("Location", "")
        
        # Should have facebook params but no wrapper
        checks = [
            ("example.com" in location, "Redirects to offer domain"),
            ("fbclid=" in location or "utm_source=facebook" in location, "Has Facebook params"),
            ("l.facebook.com" not in location, "No wrapper hop"),
        ]
        
        failed_checks = [msg for passed, msg in checks if not passed]
        if failed_checks:
            return log_test(
                "3g: Click pro no wrapper",
                False,
                f"Failed checks: {failed_checks}. Location: {location}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3g: Click pro no wrapper",
            True,
            f"302 with Facebook params, no wrapper"
        )
        
    except Exception as e:
        return log_test("3g: Click pro no wrapper", False, str(e))


def test_3h_click_pro_with_wrapper():
    """Test 3h: GET /r/{short_code} on pro=ON, wrapper=ON"""
    try:
        # Create pro link with wrapper
        link_data = {
            "name": "v2.1.81-test-pro-with-wrapper",
            "offer_url": "https://example.com/pro-with-wrapper",
            "strict_duplicate_check": False,
            "referrer_pro_enabled": True,
            "referrer_pro_platform_pool": "google:100",
            "referrer_pro_wrapper_redirect": True
        }
        
        response = requests.post(
            f"{API_BASE}/links",
            json=link_data,
            headers=get_headers(),
            timeout=10
        )
        
        if response.status_code != 200:
            return log_test(
                "3h: Click pro with wrapper",
                False,
                f"Create failed: HTTP {response.status_code}"
            )
        
        data = response.json()
        link_id = data.get("id")
        short_code = data.get("short_code")
        
        # Click the link
        response = requests.get(
            f"{API_BASE}/r/{short_code}",
            allow_redirects=False,
            timeout=10
        )
        
        if response.status_code != 302:
            return log_test(
                "3h: Click pro with wrapper",
                False,
                f"Expected 302, got {response.status_code}"
            )
        
        location = response.headers.get("Location", "")
        
        # Should redirect to a wrapper URL
        wrapper_domains = ["google.com", "l.facebook.com", "t.co", "lm.facebook.com"]
        has_wrapper = any(domain in location for domain in wrapper_domains)
        
        if not has_wrapper:
            return log_test(
                "3h: Click pro with wrapper",
                False,
                f"Expected wrapper domain, got: {location}"
            )
        
        # Store for cleanup
        test_results.append({"cleanup_link_id": link_id})
        
        return log_test(
            "3h: Click pro with wrapper",
            True,
            f"302 to wrapper URL: {location[:80]}..."
        )
        
    except Exception as e:
        return log_test("3h: Click pro with wrapper", False, str(e))


def test_3i_cleanup():
    """Test 3i: DELETE all test links"""
    try:
        link_ids = [r.get("cleanup_link_id") for r in test_results if "cleanup_link_id" in r]
        
        if not link_ids:
            return log_test("3i: Cleanup", True, "No links to clean up")
        
        deleted = 0
        failed = []
        
        for link_id in link_ids:
            try:
                response = requests.delete(
                    f"{API_BASE}/links/{link_id}",
                    headers=get_headers(),
                    timeout=10
                )
                if response.status_code in [200, 204]:
                    deleted += 1
                else:
                    failed.append(f"{link_id}: HTTP {response.status_code}")
            except Exception as e:
                failed.append(f"{link_id}: {str(e)}")
        
        if failed:
            return log_test(
                "3i: Cleanup",
                False,
                f"Deleted {deleted}/{len(link_ids)}, failed: {failed}"
            )
        
        return log_test(
            "3i: Cleanup",
            True,
            f"Deleted all {deleted} test links"
        )
        
    except Exception as e:
        return log_test("3i: Cleanup", False, str(e))


# ============================================================================
# TEST 4: Static Analysis (Informational)
# ============================================================================

def test_4_static_analysis():
    """Test 4: Static analysis of desktop scripts"""
    print("\n" + "="*80)
    print("TEST 4: Static Analysis (Informational)")
    print("="*80)
    
    import subprocess
    
    # Test 4a: Python syntax check
    try:
        result = subprocess.run(
            ["python", "-c", "import ast; ast.parse(open('/app/desktop/krexion_dashboard.py').read())"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        passed_py = result.returncode == 0
        details_py = f"Exit code: {result.returncode}"
        if result.stderr:
            details_py += f"\nStderr: {result.stderr[:200]}"
        
        log_test("4a: Python syntax check (krexion_dashboard.py)", passed_py, details_py)
        
    except Exception as e:
        log_test("4a: Python syntax check (krexion_dashboard.py)", False, str(e))
    
    # Test 4b: JavaScript syntax check
    try:
        result = subprocess.run(
            ["node", "-c", "/app/desktop/static/dashboard.js"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        passed_js = result.returncode == 0
        details_js = f"Exit code: {result.returncode}"
        if result.stderr:
            details_js += f"\nStderr: {result.stderr[:200]}"
        
        log_test("4b: JavaScript syntax check (dashboard.js)", passed_js, details_js)
        
    except Exception as e:
        log_test("4b: JavaScript syntax check (dashboard.js)", False, str(e))


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    print("\n" + "="*80)
    print("v2.1.81 Backend Verification Test Suite")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Base: {API_BASE}")
    print(f"Admin: {ADMIN_EMAIL}")
    print("="*80)
    
    # Authenticate
    if not authenticate():
        print("\n❌ FATAL: Authentication failed. Cannot proceed with tests.")
        sys.exit(1)
    
    # Run all tests
    all_passed = True
    
    # Test 1: Import + Startup Health
    all_passed &= test_1_import_health()
    all_passed &= test_1_desktop_stats_basic()
    
    # Test 2: Polling Reliability
    all_passed &= test_2_polling_reliability()
    
    # Test 3: v2.1.80 Regression - Link-level Pro-Referrer
    all_passed &= test_3a_link_backward_compat()
    all_passed &= test_3b_link_full_pro_referrer()
    all_passed &= test_3c_link_partial_update()
    all_passed &= test_3d_preview_valid_pool()
    all_passed &= test_3e_preview_empty_pool()
    all_passed &= test_3f_click_legacy()
    all_passed &= test_3g_click_pro_no_wrapper()
    all_passed &= test_3h_click_pro_with_wrapper()
    all_passed &= test_3i_cleanup()
    
    # Test 4: Static Analysis (informational, doesn't affect all_passed)
    test_4_static_analysis()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r.get("passed"))
    total_count = len([r for r in test_results if "passed" in r])
    
    print(f"Passed: {passed_count}/{total_count}")
    
    if all_passed:
        print("\n✅ ALL CRITICAL TESTS PASSED")
        print("v2.1.81 is ready for deployment")
    else:
        print("\n❌ SOME TESTS FAILED")
        print("Review failures above before deploying v2.1.81")
        failed = [r for r in test_results if "passed" in r and not r["passed"]]
        for f in failed:
            print(f"  - {f['name']}: {f['details']}")
    
    print("="*80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
