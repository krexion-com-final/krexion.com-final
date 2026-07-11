#!/usr/bin/env python3
"""
Backend Test Suite for Krexion Fraud Custom Rules + Historical Cache
=====================================================================

Tests THREE new features added to the fraud detection system:
1. Fraud Custom Rules (GET/PUT /api/fraud/rules)
2. IP Reputation Cache (GET /api/fraud/cache/stats, GET /api/fraud/cache, DELETE endpoints)
3. Regression testing (prior /api/fraud/* endpoints unchanged)

Backend base URL: https://krexion-preview-16.preview.emergentagent.com
API prefix: /api

AUTH:
- Admin login: POST /api/admin/login with { email:"admin@krexion.com", password:"Admin@Krexion2026" }
- Regular user: POST /api/auth/register then POST /api/auth/login
- /api/fraud/* endpoints need any authenticated bearer.
"""

import sys
import time
import json
import requests
from typing import Dict, Any, Optional

# Backend base URL
BASE_URL = "https://krexion-preview-16.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

# Test results tracking
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "tests": []
}


def log_test(name: str, passed: bool, details: str = ""):
    """Log a test result"""
    test_results["total"] += 1
    if passed:
        test_results["passed"] += 1
        status = "✅ PASS"
    else:
        test_results["failed"] += 1
        status = "❌ FAIL"
    
    test_results["tests"].append({
        "name": name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {name}")
    if details:
        print(f"  → {details}")


def admin_login() -> Optional[str]:
    """Login as admin and return access token"""
    try:
        resp = requests.post(
            f"{API_BASE}/admin/login",
            json={"email": "admin@krexion.com", "password": "Admin@Krexion2026"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            if token:
                log_test("Admin login", True, f"Token obtained: {token[:20]}...")
                return token
            else:
                log_test("Admin login", False, "No access_token in response")
                return None
        else:
            log_test("Admin login", False, f"Status {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Admin login", False, f"Exception: {e}")
        return None


def register_and_login_user() -> Optional[str]:
    """Register a fresh user and return access token"""
    try:
        # Generate unique email
        email = f"fraudtest{int(time.time())}@test.local"
        password = "TestPass123!"
        
        # Register
        resp = requests.post(
            f"{API_BASE}/auth/register",
            json={"email": email, "password": password, "name": "Fraud Test User"},
            timeout=10
        )
        if resp.status_code not in (200, 201):
            log_test("User registration", False, f"Status {resp.status_code}: {resp.text[:200]}")
            return None
        
        # Login
        resp = requests.post(
            f"{API_BASE}/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            if token:
                log_test("User registration + login", True, f"User: {email}, Token: {token[:20]}...")
                return token
            else:
                log_test("User registration + login", False, "No access_token in login response")
                return None
        else:
            log_test("User registration + login", False, f"Login status {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("User registration + login", False, f"Exception: {e}")
        return None


def test_server_health():
    """TEST 4(a) — Server boot health: GET /api/mode responds within 3s"""
    print("\n" + "="*70)
    print("TEST 4 — Server Boot Health")
    print("="*70)
    
    try:
        start = time.time()
        resp = requests.get(f"{API_BASE}/mode", timeout=3)
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            log_test(
                "GET /api/mode responds within 3s",
                True,
                f"Status 200, elapsed {elapsed:.2f}s, mode={data.get('mode')}, is_cloud={data.get('is_cloud')}"
            )
        else:
            log_test(
                "GET /api/mode responds within 3s",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except requests.Timeout:
        log_test("GET /api/mode responds within 3s", False, "Request timed out after 3s")
    except Exception as e:
        log_test("GET /api/mode responds within 3s", False, f"Exception: {e}")


def test_fraud_rules(token: str):
    """TEST 1 — Fraud Custom Rules"""
    print("\n" + "="*70)
    print("TEST 1 — Fraud Custom Rules")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # TEST 1(a) — GET /api/fraud/rules on fresh user → 200 with defaults
    try:
        resp = requests.get(f"{API_BASE}/fraud/rules", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            expected_defaults = {
                "enabled": False,
                "allowed_countries": [],
                "blocked_countries": [],
                "blocked_asns": [],
                "block_hosting": True,
                "block_tor": True,
                "block_datacenter": True
            }
            
            # Check all default fields
            all_match = True
            mismatches = []
            for key, expected_val in expected_defaults.items():
                actual_val = data.get(key)
                if actual_val != expected_val:
                    all_match = False
                    mismatches.append(f"{key}: expected {expected_val}, got {actual_val}")
            
            if all_match:
                log_test(
                    "GET /api/fraud/rules (fresh user) returns defaults",
                    True,
                    f"All default fields correct: {json.dumps(data, indent=2)}"
                )
            else:
                log_test(
                    "GET /api/fraud/rules (fresh user) returns defaults",
                    False,
                    f"Mismatches: {', '.join(mismatches)}"
                )
        else:
            log_test(
                "GET /api/fraud/rules (fresh user) returns defaults",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/rules (fresh user) returns defaults", False, f"Exception: {e}")
    
    # TEST 1(b) — PUT /api/fraud/rules with valid data
    try:
        put_data = {
            "enabled": True,
            "allowed_countries": ["us", "gb"],
            "blocked_countries": ["cn", "ru"],
            "blocked_asns": [15169, 16509],
            "block_hosting": True,
            "block_tor": False,
            "block_datacenter": True
        }
        
        resp = requests.put(
            f"{API_BASE}/fraud/rules",
            headers=headers,
            json=put_data,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Verify uppercase countries
            allowed = data.get("allowed_countries", [])
            blocked = data.get("blocked_countries", [])
            asns = data.get("blocked_asns", [])
            block_tor = data.get("block_tor")
            
            checks = []
            checks.append(("allowed_countries uppercase", allowed == ["US", "GB"]))
            checks.append(("blocked_countries uppercase", blocked == ["CN", "RU"]))
            checks.append(("blocked_asns as integers", asns == [15169, 16509]))
            checks.append(("block_tor is False", block_tor is False))
            
            all_pass = all(check[1] for check in checks)
            details = ", ".join([f"{name}: {'✓' if passed else '✗'}" for name, passed in checks])
            
            if all_pass:
                log_test(
                    "PUT /api/fraud/rules with valid data",
                    True,
                    f"All checks passed: {details}"
                )
                
                # Verify persistence with GET
                resp2 = requests.get(f"{API_BASE}/fraud/rules", headers=headers, timeout=10)
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    if (data2.get("allowed_countries") == ["US", "GB"] and
                        data2.get("blocked_countries") == ["CN", "RU"] and
                        data2.get("blocked_asns") == [15169, 16509] and
                        data2.get("block_tor") is False):
                        log_test(
                            "GET /api/fraud/rules confirms persistence",
                            True,
                            "All fields persisted correctly"
                        )
                    else:
                        log_test(
                            "GET /api/fraud/rules confirms persistence",
                            False,
                            f"Data mismatch after GET: {json.dumps(data2)}"
                        )
                else:
                    log_test(
                        "GET /api/fraud/rules confirms persistence",
                        False,
                        f"GET failed with status {resp2.status_code}"
                    )
            else:
                log_test(
                    "PUT /api/fraud/rules with valid data",
                    False,
                    f"Some checks failed: {details}"
                )
        else:
            log_test(
                "PUT /api/fraud/rules with valid data",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("PUT /api/fraud/rules with valid data", False, f"Exception: {e}")
    
    # TEST 1(c) — PUT with mixed-type asns (garbage coercion)
    try:
        put_data = {
            "enabled": True,
            "blocked_asns": ["not-a-number", "42", 15169, ""],
            "allowed_countries": [],
            "blocked_countries": [],
            "block_hosting": True,
            "block_tor": True,
            "block_datacenter": True
        }
        
        resp = requests.put(
            f"{API_BASE}/fraud/rules",
            headers=headers,
            json=put_data,
            timeout=10
        )
        
        if resp.status_code == 200:
            # GET to verify coercion
            resp2 = requests.get(f"{API_BASE}/fraud/rules", headers=headers, timeout=10)
            if resp2.status_code == 200:
                data = resp2.json()
                asns = data.get("blocked_asns", [])
                
                # Should contain 42 and 15169 (parseable), NOT "not-a-number" or ""
                has_42 = 42 in asns
                has_15169 = 15169 in asns
                has_garbage = any(not isinstance(x, int) for x in asns)
                
                if has_42 and has_15169 and not has_garbage:
                    log_test(
                        "PUT /api/fraud/rules with mixed-type asns (coercion)",
                        True,
                        f"Coerced correctly: {asns} (contains 42, 15169, no garbage)"
                    )
                else:
                    log_test(
                        "PUT /api/fraud/rules with mixed-type asns (coercion)",
                        False,
                        f"Coercion failed: {asns} (has_42={has_42}, has_15169={has_15169}, has_garbage={has_garbage})"
                    )
            else:
                log_test(
                    "PUT /api/fraud/rules with mixed-type asns (coercion)",
                    False,
                    f"GET after PUT failed with status {resp2.status_code}"
                )
        else:
            log_test(
                "PUT /api/fraud/rules with mixed-type asns (coercion)",
                False,
                f"PUT status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("PUT /api/fraud/rules with mixed-type asns (coercion)", False, f"Exception: {e}")


def test_fraud_cache(token: str):
    """TEST 2 — IP Reputation Cache"""
    print("\n" + "="*70)
    print("TEST 2 — IP Reputation Cache")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # TEST 2(a) — GET /api/fraud/cache/stats
    try:
        resp = requests.get(f"{API_BASE}/fraud/cache/stats", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            expected = {"total": 0, "clean": 0, "blocked": 0, "block_rate_pct": 0}
            
            if data == expected:
                log_test(
                    "GET /api/fraud/cache/stats (fresh user)",
                    True,
                    f"Returns zero stats: {data}"
                )
            else:
                log_test(
                    "GET /api/fraud/cache/stats (fresh user)",
                    False,
                    f"Expected {expected}, got {data}"
                )
        else:
            log_test(
                "GET /api/fraud/cache/stats (fresh user)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/cache/stats (fresh user)", False, f"Exception: {e}")
    
    # TEST 2(b) — GET /api/fraud/cache
    try:
        resp = requests.get(f"{API_BASE}/fraud/cache", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            count = data.get("count", -1)
            
            if items == [] and count == 0:
                log_test(
                    "GET /api/fraud/cache (fresh user)",
                    True,
                    f"Returns empty: items=[], count=0"
                )
            else:
                log_test(
                    "GET /api/fraud/cache (fresh user)",
                    False,
                    f"Expected empty, got items={len(items)}, count={count}"
                )
        else:
            log_test(
                "GET /api/fraud/cache (fresh user)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/cache (fresh user)", False, f"Exception: {e}")
    
    # TEST 2(c) — GET /api/fraud/cache?limit=50&blocked_only=true
    try:
        resp = requests.get(
            f"{API_BASE}/fraud/cache",
            headers=headers,
            params={"limit": 50, "blocked_only": True},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            count = data.get("count", -1)
            
            if items == [] and count == 0:
                log_test(
                    "GET /api/fraud/cache?limit=50&blocked_only=true (fresh user)",
                    True,
                    "Returns empty"
                )
            else:
                log_test(
                    "GET /api/fraud/cache?limit=50&blocked_only=true (fresh user)",
                    False,
                    f"Expected empty, got items={len(items)}, count={count}"
                )
        else:
            log_test(
                "GET /api/fraud/cache?limit=50&blocked_only=true (fresh user)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/cache?limit=50&blocked_only=true (fresh user)", False, f"Exception: {e}")
    
    # TEST 2(d) — DELETE /api/fraud/cache
    try:
        resp = requests.delete(f"{API_BASE}/fraud/cache", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ok = data.get("ok")
            deleted = data.get("deleted")
            
            if ok is True and deleted == 0:
                log_test(
                    "DELETE /api/fraud/cache (fresh user)",
                    True,
                    f"Returns ok=true, deleted=0"
                )
            else:
                log_test(
                    "DELETE /api/fraud/cache (fresh user)",
                    False,
                    f"Expected ok=true, deleted=0, got ok={ok}, deleted={deleted}"
                )
        else:
            log_test(
                "DELETE /api/fraud/cache (fresh user)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("DELETE /api/fraud/cache (fresh user)", False, f"Exception: {e}")
    
    # TEST 2(e) — DELETE /api/fraud/cache/1.2.3.4
    try:
        resp = requests.delete(f"{API_BASE}/fraud/cache/1.2.3.4", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            ok = data.get("ok")
            deleted = data.get("deleted")
            
            if ok is True and deleted == 0:
                log_test(
                    "DELETE /api/fraud/cache/1.2.3.4 (fresh user)",
                    True,
                    f"Returns ok=true, deleted=0"
                )
            else:
                log_test(
                    "DELETE /api/fraud/cache/1.2.3.4 (fresh user)",
                    False,
                    f"Expected ok=true, deleted=0, got ok={ok}, deleted={deleted}"
                )
        else:
            log_test(
                "DELETE /api/fraud/cache/1.2.3.4 (fresh user)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("DELETE /api/fraud/cache/1.2.3.4 (fresh user)", False, f"Exception: {e}")


def test_fraud_regression(token: str):
    """TEST 3 — Regression on prior /api/fraud/* endpoints"""
    print("\n" + "="*70)
    print("TEST 3 — Regression (prior /api/fraud/* endpoints)")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # TEST 3(a) — GET /api/fraud/settings still returns min_fraud_score
    try:
        resp = requests.get(f"{API_BASE}/fraud/settings", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            has_min_fraud_score = "min_fraud_score" in data
            has_personal_filter = "personal_filter_enabled" in data
            has_fallback = "fallback_to_defaults" in data
            
            if has_min_fraud_score and has_personal_filter and has_fallback:
                log_test(
                    "GET /api/fraud/settings returns expected fields",
                    True,
                    f"Fields present: min_fraud_score={data.get('min_fraud_score')}, "
                    f"personal_filter_enabled={data.get('personal_filter_enabled')}, "
                    f"fallback_to_defaults={data.get('fallback_to_defaults')}"
                )
            else:
                log_test(
                    "GET /api/fraud/settings returns expected fields",
                    False,
                    f"Missing fields: min_fraud_score={has_min_fraud_score}, "
                    f"personal_filter_enabled={has_personal_filter}, "
                    f"fallback_to_defaults={has_fallback}"
                )
        else:
            log_test(
                "GET /api/fraud/settings returns expected fields",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/settings returns expected fields", False, f"Exception: {e}")
    
    # TEST 3(b) — GET /api/fraud/services lists 4 services
    try:
        resp = requests.get(f"{API_BASE}/fraud/services", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            services = data.get("services", [])
            service_keys = [s.get("key") for s in services]
            
            expected_services = ["scamalytics", "ipqualityscore", "iphub", "proxycheck"]
            all_present = all(svc in service_keys for svc in expected_services)
            
            if all_present and len(services) == 4:
                log_test(
                    "GET /api/fraud/services lists 4 services",
                    True,
                    f"Services: {service_keys}"
                )
            else:
                log_test(
                    "GET /api/fraud/services lists 4 services",
                    False,
                    f"Expected 4 services {expected_services}, got {len(services)}: {service_keys}"
                )
        else:
            log_test(
                "GET /api/fraud/services lists 4 services",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("GET /api/fraud/services lists 4 services", False, f"Exception: {e}")
    
    # TEST 3(c) — Full accounts CRUD cycle
    account_id = None
    try:
        # POST /api/fraud/accounts
        create_data = {
            "service": "ipqualityscore",
            "account_name": "test-account",
            "api_key": "test-key-123",
            "enabled": True,
            "priority": 100,
            "quota_daily": 0
        }
        
        resp = requests.post(
            f"{API_BASE}/fraud/accounts",
            headers=headers,
            json=create_data,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            account_id = data.get("id")
            
            if account_id:
                log_test(
                    "POST /api/fraud/accounts (create)",
                    True,
                    f"Account created: id={account_id}, name={data.get('account_name')}"
                )
            else:
                log_test(
                    "POST /api/fraud/accounts (create)",
                    False,
                    "No 'id' in response"
                )
        else:
            log_test(
                "POST /api/fraud/accounts (create)",
                False,
                f"Status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("POST /api/fraud/accounts (create)", False, f"Exception: {e}")
    
    # PUT /api/fraud/accounts/{id}
    if account_id:
        try:
            update_data = {"priority": 50}
            resp = requests.put(
                f"{API_BASE}/fraud/accounts/{account_id}",
                headers=headers,
                json=update_data,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                new_priority = data.get("priority")
                
                if new_priority == 50:
                    log_test(
                        "PUT /api/fraud/accounts/{id} (update)",
                        True,
                        f"Priority updated to 50"
                    )
                else:
                    log_test(
                        "PUT /api/fraud/accounts/{id} (update)",
                        False,
                        f"Expected priority=50, got {new_priority}"
                    )
            else:
                log_test(
                    "PUT /api/fraud/accounts/{id} (update)",
                    False,
                    f"Status {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as e:
            log_test("PUT /api/fraud/accounts/{id} (update)", False, f"Exception: {e}")
    
    # DELETE /api/fraud/accounts/{id}
    if account_id:
        try:
            resp = requests.delete(
                f"{API_BASE}/fraud/accounts/{account_id}",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                ok = data.get("ok")
                
                if ok is True:
                    log_test(
                        "DELETE /api/fraud/accounts/{id}",
                        True,
                        "Account deleted successfully"
                    )
                else:
                    log_test(
                        "DELETE /api/fraud/accounts/{id}",
                        False,
                        f"Expected ok=true, got {ok}"
                    )
            else:
                log_test(
                    "DELETE /api/fraud/accounts/{id}",
                    False,
                    f"Status {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as e:
            log_test("DELETE /api/fraud/accounts/{id}", False, f"Exception: {e}")
    
    # TEST 3(d) — Regression on min_fraud_score clamping
    try:
        # Test upper bound (200 → 100)
        resp = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=headers,
            json={
                "personal_filter_enabled": True,
                "fallback_to_defaults": True,
                "min_fraud_score": 200
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            # GET to verify clamping
            resp2 = requests.get(f"{API_BASE}/fraud/settings", headers=headers, timeout=10)
            if resp2.status_code == 200:
                data = resp2.json()
                score = data.get("min_fraud_score")
                
                if score == 100:
                    log_test(
                        "PUT /api/fraud/settings with min_fraud_score=200 (clamp to 100)",
                        True,
                        f"Clamped correctly to 100"
                    )
                else:
                    log_test(
                        "PUT /api/fraud/settings with min_fraud_score=200 (clamp to 100)",
                        False,
                        f"Expected 100, got {score}"
                    )
            else:
                log_test(
                    "PUT /api/fraud/settings with min_fraud_score=200 (clamp to 100)",
                    False,
                    f"GET failed with status {resp2.status_code}"
                )
        else:
            log_test(
                "PUT /api/fraud/settings with min_fraud_score=200 (clamp to 100)",
                False,
                f"PUT status {resp.status_code}: {resp.text[:200]}"
            )
        
        # Test lower bound (-5 → 0)
        resp = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=headers,
            json={
                "personal_filter_enabled": True,
                "fallback_to_defaults": True,
                "min_fraud_score": -5
            },
            timeout=10
        )
        
        if resp.status_code == 200:
            # GET to verify clamping
            resp2 = requests.get(f"{API_BASE}/fraud/settings", headers=headers, timeout=10)
            if resp2.status_code == 200:
                data = resp2.json()
                score = data.get("min_fraud_score")
                
                if score == 0:
                    log_test(
                        "PUT /api/fraud/settings with min_fraud_score=-5 (clamp to 0)",
                        True,
                        f"Clamped correctly to 0"
                    )
                else:
                    log_test(
                        "PUT /api/fraud/settings with min_fraud_score=-5 (clamp to 0)",
                        False,
                        f"Expected 0, got {score}"
                    )
            else:
                log_test(
                    "PUT /api/fraud/settings with min_fraud_score=-5 (clamp to 0)",
                    False,
                    f"GET failed with status {resp2.status_code}"
                )
        else:
            log_test(
                "PUT /api/fraud/settings with min_fraud_score=-5 (clamp to 0)",
                False,
                f"PUT status {resp.status_code}: {resp.text[:200]}"
            )
    except Exception as e:
        log_test("min_fraud_score clamping tests", False, f"Exception: {e}")


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total tests: {test_results['total']}")
    print(f"Passed: {test_results['passed']} ✅")
    print(f"Failed: {test_results['failed']} ❌")
    print(f"Success rate: {(test_results['passed'] / test_results['total'] * 100) if test_results['total'] > 0 else 0:.1f}%")
    
    if test_results['failed'] > 0:
        print("\nFailed tests:")
        for test in test_results['tests']:
            if not test['passed']:
                print(f"  ❌ {test['name']}")
                if test['details']:
                    print(f"     → {test['details']}")


def main():
    print("="*70)
    print("Krexion Backend Test Suite")
    print("Fraud Custom Rules + Historical Cache + Antidetect")
    print("="*70)
    print(f"Backend URL: {BASE_URL}")
    print(f"API Base: {API_BASE}")
    print("="*70)
    
    # Test server health first
    test_server_health()
    
    # Register and login a fresh user
    print("\n" + "="*70)
    print("Authentication Setup")
    print("="*70)
    
    user_token = register_and_login_user()
    if not user_token:
        print("\n❌ CRITICAL: Could not authenticate user. Aborting tests.")
        print_summary()
        sys.exit(1)
    
    # Run all fraud tests
    test_fraud_rules(user_token)
    test_fraud_cache(user_token)
    test_fraud_regression(user_token)
    
    # Print summary
    print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if test_results['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
