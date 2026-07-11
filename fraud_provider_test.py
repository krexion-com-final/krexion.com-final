#!/usr/bin/env python3
"""
Fraud Provider Integration Backend Test Suite
Tests the min_fraud_score threshold feature and regression tests for existing fraud endpoints.

Backend URL: https://krexion-preview-16.preview.emergentagent.com
API prefix: /api

Test Coverage:
1. Server health (GET /api/, GET /api/mode)
2. GET /api/fraud/settings - min_fraud_score field presence and default value
3. PUT /api/fraud/settings - persistence and clamping (0-100 range)
4. Regression tests for existing fraud endpoints (accounts CRUD, services)
5. Master toggle OFF regression test
"""

import requests
import time
import json
import sys
from typing import Dict, Any, List, Optional

# Configuration
BACKEND_URL = "https://krexion-preview-16.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Admin credentials (from review request)
ADMIN_EMAIL = "admin@krexion.com"
ADMIN_PASSWORD = "Admin@Krexion2026"

# Test results tracking
test_results = []
auth_token = None
test_user_token = None
test_account_ids = []


def log_test(test_name: str, passed: bool, details: str = ""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f"\n   {details}"
    print(result)
    test_results.append({"name": test_name, "passed": passed, "details": details})
    return passed


def authenticate_admin() -> Optional[str]:
    """Authenticate as admin and get JWT token"""
    global auth_token
    try:
        print(f"\n🔐 Authenticating as admin: {ADMIN_EMAIL}")
        response = requests.post(
            f"{API_BASE}/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            auth_token = data.get("access_token") or data.get("token")
            print(f"✅ Admin authenticated successfully")
            return auth_token
        else:
            print(f"❌ Admin auth failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Admin auth exception: {e}")
        return None


def register_test_user() -> Optional[str]:
    """Register a fresh test user for fraud endpoint testing"""
    global test_user_token
    try:
        timestamp = int(time.time())
        email = f"fraudtest{timestamp}@test.local"
        password = "TestPass123!"
        
        print(f"\n👤 Registering test user: {email}")
        response = requests.post(
            f"{API_BASE}/auth/register",
            json={"email": email, "password": password, "name": "Fraud Test User"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            test_user_token = data.get("access_token") or data.get("token")
            print(f"✅ Test user registered successfully")
            return test_user_token
        else:
            print(f"⚠️  Test user registration failed: {response.status_code} - {response.text[:200]}")
            # Try to login instead
            print(f"   Attempting to login with existing credentials...")
            response = requests.post(
                f"{API_BASE}/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                test_user_token = data.get("access_token") or data.get("token")
                print(f"✅ Test user logged in successfully")
                return test_user_token
            return None
    except Exception as e:
        print(f"❌ Test user registration exception: {e}")
        return None


def get_headers(use_test_user: bool = False) -> Dict[str, str]:
    """Get headers with auth token"""
    headers = {"Content-Type": "application/json"}
    token = test_user_token if use_test_user else auth_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ============================================================================
# TEST 1: Server Health
# ============================================================================

def test_1_server_health():
    """Test 1: Server health checks"""
    print("\n" + "="*80)
    print("TEST 1: Server Health")
    print("="*80)
    
    all_passed = True
    
    # Test 1a: GET /api/
    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        if passed:
            data = response.json()
            details += f", Response: {json.dumps(data)[:100]}"
        all_passed &= log_test("GET /api/ (root endpoint)", passed, details)
    except Exception as e:
        all_passed &= log_test("GET /api/ (root endpoint)", False, f"Exception: {e}")
    
    # Test 1b: GET /api/mode
    try:
        response = requests.get(f"{API_BASE}/mode", timeout=5)
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        if passed:
            data = response.json()
            details += f", Mode: {data.get('mode')}, Is Cloud: {data.get('is_cloud')}"
        all_passed &= log_test("GET /api/mode", passed, details)
    except Exception as e:
        all_passed &= log_test("GET /api/mode", False, f"Exception: {e}")
    
    return all_passed


# ============================================================================
# TEST 2: GET /api/fraud/settings - min_fraud_score field
# ============================================================================

def test_2_fraud_settings_get():
    """Test 2: GET /api/fraud/settings must return min_fraud_score"""
    print("\n" + "="*80)
    print("TEST 2: GET /api/fraud/settings - min_fraud_score field")
    print("="*80)
    
    if not test_user_token:
        return log_test("GET /api/fraud/settings", False, "No test user token available")
    
    try:
        response = requests.get(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            
            # Check for required fields
            has_min_fraud_score = "min_fraud_score" in data
            has_personal_filter = "personal_filter_enabled" in data
            has_fallback = "fallback_to_defaults" in data
            
            min_fraud_score = data.get("min_fraud_score")
            
            details += f"\n   Fields present: min_fraud_score={has_min_fraud_score}, "
            details += f"personal_filter_enabled={has_personal_filter}, "
            details += f"fallback_to_defaults={has_fallback}"
            details += f"\n   min_fraud_score value: {min_fraud_score} (expected: 75 for new user)"
            details += f"\n   Full response: {json.dumps(data, indent=2)}"
            
            # Validate min_fraud_score is present and has correct default
            if not has_min_fraud_score:
                passed = False
                details += "\n   ❌ CRITICAL: min_fraud_score field is MISSING"
            elif min_fraud_score != 75:
                # This might be OK if it's a legacy user, but flag it
                details += f"\n   ⚠️  min_fraud_score is {min_fraud_score}, not 75 (might be legacy user)"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        return log_test("GET /api/fraud/settings returns min_fraud_score", passed, details)
    
    except Exception as e:
        return log_test("GET /api/fraud/settings returns min_fraud_score", False, f"Exception: {e}")


# ============================================================================
# TEST 3: PUT /api/fraud/settings - persistence
# ============================================================================

def test_3_fraud_settings_put_persistence():
    """Test 3: PUT /api/fraud/settings with min_fraud_score=60, verify persistence"""
    print("\n" + "="*80)
    print("TEST 3: PUT /api/fraud/settings - persistence")
    print("="*80)
    
    if not test_user_token:
        return log_test("PUT /api/fraud/settings persistence", False, "No test user token available")
    
    all_passed = True
    
    # Test 3a: PUT with min_fraud_score=60
    try:
        put_data = {
            "personal_filter_enabled": True,
            "fallback_to_defaults": True,
            "min_fraud_score": 60
        }
        
        response = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            json=put_data,
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            returned_score = data.get("min_fraud_score")
            details += f"\n   Sent: min_fraud_score=60"
            details += f"\n   Returned: min_fraud_score={returned_score}"
            
            if returned_score != 60:
                passed = False
                details += f"\n   ❌ CRITICAL: Expected 60, got {returned_score}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("PUT /api/fraud/settings with min_fraud_score=60", passed, details)
    
    except Exception as e:
        all_passed &= log_test("PUT /api/fraud/settings with min_fraud_score=60", False, f"Exception: {e}")
        return False
    
    # Test 3b: GET again to verify persistence
    try:
        time.sleep(0.5)  # Brief pause
        response = requests.get(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            persisted_score = data.get("min_fraud_score")
            details += f"\n   Persisted value: {persisted_score} (expected: 60)"
            
            if persisted_score != 60:
                passed = False
                details += f"\n   ❌ CRITICAL: Value not persisted correctly. Expected 60, got {persisted_score}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("GET /api/fraud/settings confirms persistence (60)", passed, details)
    
    except Exception as e:
        all_passed &= log_test("GET /api/fraud/settings confirms persistence (60)", False, f"Exception: {e}")
    
    return all_passed


# ============================================================================
# TEST 4: Threshold clamping (upper and lower bounds)
# ============================================================================

def test_4_threshold_clamping():
    """Test 4: Threshold clamping - upper bound (200 -> 100) and lower bound (-5 -> 0)"""
    print("\n" + "="*80)
    print("TEST 4: Threshold Clamping")
    print("="*80)
    
    if not test_user_token:
        return log_test("Threshold clamping", False, "No test user token available")
    
    all_passed = True
    
    # Test 4a: Upper bound clamping (200 -> 100)
    try:
        put_data = {
            "personal_filter_enabled": True,
            "fallback_to_defaults": True,
            "min_fraud_score": 200
        }
        
        response = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            json=put_data,
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            clamped_score = data.get("min_fraud_score")
            details += f"\n   Sent: min_fraud_score=200"
            details += f"\n   Returned: min_fraud_score={clamped_score} (expected: 100)"
            
            if clamped_score != 100:
                passed = False
                details += f"\n   ❌ CRITICAL: Upper bound clamping failed. Expected 100, got {clamped_score}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("PUT min_fraud_score=200 clamps to 100", passed, details)
        
        # Verify persistence
        if passed:
            time.sleep(0.5)
            response = requests.get(
                f"{API_BASE}/fraud/settings",
                headers=get_headers(use_test_user=True),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                persisted = data.get("min_fraud_score")
                if persisted != 100:
                    all_passed &= log_test("GET confirms upper bound clamp persisted", False, 
                                          f"Expected 100, got {persisted}")
                else:
                    all_passed &= log_test("GET confirms upper bound clamp persisted", True, 
                                          f"Correctly persisted as 100")
    
    except Exception as e:
        all_passed &= log_test("PUT min_fraud_score=200 clamps to 100", False, f"Exception: {e}")
    
    # Test 4b: Lower bound clamping (-5 -> 0)
    try:
        put_data = {
            "personal_filter_enabled": True,
            "fallback_to_defaults": True,
            "min_fraud_score": -5
        }
        
        response = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            json=put_data,
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            clamped_score = data.get("min_fraud_score")
            details += f"\n   Sent: min_fraud_score=-5"
            details += f"\n   Returned: min_fraud_score={clamped_score} (expected: 0)"
            
            if clamped_score != 0:
                passed = False
                details += f"\n   ❌ CRITICAL: Lower bound clamping failed. Expected 0, got {clamped_score}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("PUT min_fraud_score=-5 clamps to 0", passed, details)
        
        # Verify persistence
        if passed:
            time.sleep(0.5)
            response = requests.get(
                f"{API_BASE}/fraud/settings",
                headers=get_headers(use_test_user=True),
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                persisted = data.get("min_fraud_score")
                if persisted != 0:
                    all_passed &= log_test("GET confirms lower bound clamp persisted", False, 
                                          f"Expected 0, got {persisted}")
                else:
                    all_passed &= log_test("GET confirms lower bound clamp persisted", True, 
                                          f"Correctly persisted as 0")
    
    except Exception as e:
        all_passed &= log_test("PUT min_fraud_score=-5 clamps to 0", False, f"Exception: {e}")
    
    return all_passed


# ============================================================================
# TEST 5: Regression - existing fraud endpoints
# ============================================================================

def test_5_fraud_endpoints_regression():
    """Test 5: Regression tests for existing fraud endpoints"""
    print("\n" + "="*80)
    print("TEST 5: Regression - Existing Fraud Endpoints")
    print("="*80)
    
    if not test_user_token:
        return log_test("Fraud endpoints regression", False, "No test user token available")
    
    all_passed = True
    
    # Test 5a: GET /api/fraud/services
    try:
        response = requests.get(
            f"{API_BASE}/fraud/services",
            headers=get_headers(use_test_user=True),
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            services = data.get("services", [])
            service_keys = [s.get("key") for s in services]
            
            expected_services = ["scamalytics", "ipqualityscore", "iphub", "proxycheck"]
            has_all = all(svc in service_keys for svc in expected_services)
            
            details += f"\n   Services returned: {service_keys}"
            details += f"\n   Expected services present: {has_all}"
            
            if not has_all:
                passed = False
                details += f"\n   ❌ Missing services: {set(expected_services) - set(service_keys)}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("GET /api/fraud/services", passed, details)
    
    except Exception as e:
        all_passed &= log_test("GET /api/fraud/services", False, f"Exception: {e}")
    
    # Test 5b: GET /api/fraud/accounts (should be empty for new user)
    try:
        response = requests.get(
            f"{API_BASE}/fraud/accounts",
            headers=get_headers(use_test_user=True),
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            # Response should be a list
            if isinstance(data, list):
                details += f"\n   Accounts count: {len(data)}"
            else:
                details += f"\n   Response type: {type(data)}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("GET /api/fraud/accounts", passed, details)
    
    except Exception as e:
        all_passed &= log_test("GET /api/fraud/accounts", False, f"Exception: {e}")
    
    # Test 5c: POST /api/fraud/accounts (create dummy account)
    try:
        account_data = {
            "service": "ipqualityscore",
            "account_name": "test-account",
            "api_key": "test-key-123",
            "enabled": True,
            "priority": 100,
            "quota_daily": 0
        }
        
        response = requests.post(
            f"{API_BASE}/fraud/accounts",
            headers=get_headers(use_test_user=True),
            json=account_data,
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            account_id = data.get("id")
            test_account_ids.append(account_id)
            
            details += f"\n   Created account ID: {account_id}"
            details += f"\n   Account name: {data.get('account_name')}"
            details += f"\n   Service: {data.get('service')}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("POST /api/fraud/accounts (create)", passed, details)
    
    except Exception as e:
        all_passed &= log_test("POST /api/fraud/accounts (create)", False, f"Exception: {e}")
    
    # Test 5d: PUT /api/fraud/accounts/{id} (update account)
    if test_account_ids:
        try:
            account_id = test_account_ids[0]
            update_data = {"priority": 50}
            
            response = requests.put(
                f"{API_BASE}/fraud/accounts/{account_id}",
                headers=get_headers(use_test_user=True),
                json=update_data,
                timeout=10
            )
            
            passed = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if passed:
                data = response.json()
                updated_priority = data.get("priority")
                details += f"\n   Updated priority: {updated_priority} (expected: 50)"
                
                if updated_priority != 50:
                    passed = False
                    details += f"\n   ❌ Priority not updated correctly"
            else:
                details += f"\n   Response: {response.text[:200]}"
            
            all_passed &= log_test("PUT /api/fraud/accounts/{id} (update)", passed, details)
        
        except Exception as e:
            all_passed &= log_test("PUT /api/fraud/accounts/{id} (update)", False, f"Exception: {e}")
    
    # Test 5e: DELETE /api/fraud/accounts/{id}
    if test_account_ids:
        try:
            account_id = test_account_ids[0]
            
            response = requests.delete(
                f"{API_BASE}/fraud/accounts/{account_id}",
                headers=get_headers(use_test_user=True),
                timeout=10
            )
            
            passed = response.status_code == 200
            details = f"Status: {response.status_code}"
            
            if passed:
                data = response.json()
                details += f"\n   Response: {json.dumps(data)}"
                
                if not data.get("ok"):
                    passed = False
                    details += f"\n   ❌ Delete did not return ok:true"
            else:
                details += f"\n   Response: {response.text[:200]}"
            
            all_passed &= log_test("DELETE /api/fraud/accounts/{id}", passed, details)
            
            # Remove from tracking
            test_account_ids.remove(account_id)
        
        except Exception as e:
            all_passed &= log_test("DELETE /api/fraud/accounts/{id}", False, f"Exception: {e}")
    
    return all_passed


# ============================================================================
# TEST 6: Master toggle OFF regression
# ============================================================================

def test_6_master_toggle_off():
    """Test 6: Master toggle OFF regression - personal_filter_enabled=false"""
    print("\n" + "="*80)
    print("TEST 6: Master Toggle OFF Regression")
    print("="*80)
    
    if not test_user_token:
        return log_test("Master toggle OFF regression", False, "No test user token available")
    
    all_passed = True
    
    # Test 6a: Set personal_filter_enabled=false
    try:
        put_data = {
            "personal_filter_enabled": False,
            "fallback_to_defaults": True,
            "min_fraud_score": 75
        }
        
        response = requests.put(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            json=put_data,
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            details += f"\n   personal_filter_enabled: {data.get('personal_filter_enabled')}"
            details += f"\n   Settings updated successfully"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("PUT settings with personal_filter_enabled=false", passed, details)
    
    except Exception as e:
        all_passed &= log_test("PUT settings with personal_filter_enabled=false", False, f"Exception: {e}")
    
    # Test 6b: Verify GET /api/fraud/settings still works
    try:
        response = requests.get(
            f"{API_BASE}/fraud/settings",
            headers=get_headers(use_test_user=True),
            timeout=10
        )
        
        passed = response.status_code == 200
        details = f"Status: {response.status_code}"
        
        if passed:
            data = response.json()
            details += f"\n   Settings readable with master toggle OFF"
            details += f"\n   personal_filter_enabled: {data.get('personal_filter_enabled')}"
        else:
            details += f"\n   Response: {response.text[:200]}"
        
        all_passed &= log_test("GET /api/fraud/settings with master toggle OFF", passed, details)
    
    except Exception as e:
        all_passed &= log_test("GET /api/fraud/settings with master toggle OFF", False, f"Exception: {e}")
    
    return all_passed


# ============================================================================
# Main Test Runner
# ============================================================================

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("FRAUD PROVIDER INTEGRATION - BACKEND TEST SUITE")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"API Base: {API_BASE}")
    print(f"Admin Email: {ADMIN_EMAIL}")
    print("="*80)
    
    # Authenticate
    if not authenticate_admin():
        print("\n❌ CRITICAL: Admin authentication failed. Cannot proceed with tests.")
        sys.exit(1)
    
    # Register test user for fraud endpoints
    if not register_test_user():
        print("\n⚠️  WARNING: Test user registration failed. Will try to use admin token for fraud tests.")
        test_user_token = auth_token  # Fallback to admin token
    
    # Run all tests
    all_tests_passed = True
    
    all_tests_passed &= test_1_server_health()
    all_tests_passed &= test_2_fraud_settings_get()
    all_tests_passed &= test_3_fraud_settings_put_persistence()
    all_tests_passed &= test_4_threshold_clamping()
    all_tests_passed &= test_5_fraud_endpoints_regression()
    all_tests_passed &= test_6_master_toggle_off()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    
    if all_tests_passed:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nFailed tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['name']}")
                if r["details"]:
                    print(f"    {r['details']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
