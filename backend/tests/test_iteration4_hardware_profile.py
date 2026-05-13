"""
Iteration 4 — Hardware Profile endpoint + smoke regression.

Tests added in this iteration:
  - GET /api/diagnostics/hardware-profile (new endpoint)
Regression smoke (must still pass after server.py edit + .env tuning):
  - GET /api/diagnostics/health
  - POST /api/admin/login
Also verifies scripts/detect-hardware.sh behaves correctly on Linux.
"""
import os
import subprocess
import requests
import pytest

# --- BASE_URL discovery (mirror the iter-3 pattern) ---
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "admin@realflow.local"
ADMIN_PASSWORD = "admin123"

VALID_TIERS = {"MICRO", "LOW", "MID", "HIGH", "BEAST"}


# ----------------------------------------------------------------------
# /api/diagnostics/hardware-profile — primary feature of this iteration
# ----------------------------------------------------------------------
class TestHardwareProfile:
    def test_endpoint_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"

    def test_response_shape(self):
        r = requests.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        data = r.json()
        # Top-level keys
        for key in ("detected", "recommended_tier", "recommended_settings", "applied", "hint"):
            assert key in data, f"Missing top-level key: {key}"

        # detected.* fields populated
        det = data["detected"]
        assert isinstance(det.get("total_ram_gb"), int) and det["total_ram_gb"] > 0, \
            f"total_ram_gb missing/invalid: {det}"
        assert isinstance(det.get("cpu_cores"), int) and det["cpu_cores"] >= 1, \
            f"cpu_cores missing/invalid: {det}"

        # tier is one of the 5 known values
        assert data["recommended_tier"] in VALID_TIERS, \
            f"recommended_tier '{data['recommended_tier']}' not in {VALID_TIERS}"

        # recommended_settings.rut_concurrency present
        rec = data["recommended_settings"]
        assert isinstance(rec.get("rut_concurrency"), int) and rec["rut_concurrency"] >= 1, \
            f"recommended rut_concurrency invalid: {rec}"
        # other recommended keys exist
        for key in ("mongo_mem_limit", "backend_mem_limit", "frontend_mem_limit",
                    "wsl_memory", "compose_override"):
            assert key in rec, f"recommended_settings missing: {key}"

        # applied.rut_concurrency populated
        app = data["applied"]
        assert isinstance(app.get("rut_concurrency"), int) and app["rut_concurrency"] >= 1, \
            f"applied rut_concurrency invalid: {app}"
        assert "matches_recommendation" in app

        # hint present + non-empty
        assert isinstance(data["hint"], str) and len(data["hint"]) > 0

    def test_high_tier_for_preview_host(self):
        """Preview host has ~31 GB RAM / 8 cores -> HIGH tier with rut=8."""
        r = requests.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        data = r.json()
        ram = data["detected"]["total_ram_gb"]
        cores = data["detected"]["cpu_cores"]
        # Sanity: should detect at least multi-GB RAM
        assert ram >= 8, f"Detected RAM ({ram} GB) too low; psutil may be broken"
        # If host matches the preview (~31 GB / 8 cores), tier should be HIGH
        if 17 <= ram <= 32 and cores >= 4:
            assert data["recommended_tier"] == "HIGH", \
                f"Expected HIGH tier for {ram}GB/{cores}cores, got {data['recommended_tier']}"
            assert data["recommended_settings"]["rut_concurrency"] == 8, \
                f"Expected rut_concurrency=8 for HIGH tier, got " \
                f"{data['recommended_settings']['rut_concurrency']}"

    def test_applied_matches_recommendation_on_preview(self):
        """RUT_MAX_CONCURRENCY=8 in /app/backend/.env, so applied should equal recommended."""
        r = requests.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        data = r.json()
        # On the preview host (HIGH tier), the env was tuned to 8.
        if data["recommended_tier"] == "HIGH":
            assert data["applied"]["rut_concurrency"] == data["recommended_settings"]["rut_concurrency"], (
                f"applied={data['applied']['rut_concurrency']} != "
                f"recommended={data['recommended_settings']['rut_concurrency']}"
            )
            assert data["applied"]["matches_recommendation"] is True
            assert "already running with the recommended tuning" in data["hint"].lower()

    def test_cpu_ceiling_logic(self):
        """rut_concurrency must never exceed cpu_cores * 2."""
        r = requests.get(f"{BASE_URL}/api/diagnostics/hardware-profile", timeout=15)
        data = r.json()
        cores = data["detected"]["cpu_cores"]
        rut = data["recommended_settings"]["rut_concurrency"]
        assert rut <= cores * 2, f"rut_concurrency {rut} > cpu_ceiling ({cores}*2)"


# ----------------------------------------------------------------------
# Regression smoke — ensure existing endpoints still work after server edit
# ----------------------------------------------------------------------
class TestRegressionSmoke:
    def test_diagnostics_health_still_ok(self):
        r = requests.get(f"{BASE_URL}/api/diagnostics/health", timeout=15)
        assert r.status_code == 200, f"/health returned {r.status_code}: {r.text[:300]}"
        data = r.json()
        # Per iter-3, overall is 'ok' or 'warn' (playwright/gsheet warns are documented)
        assert data.get("overall") in ("ok", "warn"), \
            f"overall='{data.get('overall')}' not in (ok|warn)"

    def test_admin_login_still_works(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 200, f"admin/login returned {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str) \
            and len(data["access_token"]) > 0


# ----------------------------------------------------------------------
# scripts/detect-hardware.sh — Linux/macOS profile picker
# ----------------------------------------------------------------------
class TestDetectHardwareShellScript:
    SCRIPT = "/app/scripts/detect-hardware.sh"

    def test_script_exists_and_executable(self):
        assert os.path.exists(self.SCRIPT), f"Missing: {self.SCRIPT}"
        # Ensure it's executable for the test
        if not os.access(self.SCRIPT, os.X_OK):
            os.chmod(self.SCRIPT, 0o755)
        assert os.access(self.SCRIPT, os.X_OK)

    def test_human_flag_exits_0_and_prints_tier(self):
        os.chmod(self.SCRIPT, 0o755)
        proc = subprocess.run(
            ["bash", self.SCRIPT, "--human"],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0, f"--human exited {proc.returncode}: {proc.stderr}"
        # Look for a "Selected tier" line in the human output
        assert "Selected tier" in proc.stdout, f"No 'Selected tier' line:\n{proc.stdout}"
        # And the tier should be one of the known values
        assert any(t in proc.stdout for t in VALID_TIERS), \
            f"No known tier name in output:\n{proc.stdout}"

    def test_default_emits_evaluable_env(self):
        os.chmod(self.SCRIPT, 0o755)
        proc = subprocess.run(
            ["bash", self.SCRIPT],
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 0
        # Must emit the canonical env vars an installer would eval
        for var in ("RF_TIER", "RF_RUT_CONCURRENCY", "RF_RAM_GB",
                    "RF_CPU_CORES", "RF_COMPOSE_OVERRIDE"):
            assert f"export {var}=" in proc.stdout, f"Missing export {var}= in:\n{proc.stdout}"

        # Sanity: eval'ing the output should produce a known tier
        eval_proc = subprocess.run(
            ["bash", "-c", f'eval "$(bash {self.SCRIPT})" && echo "$RF_TIER|$RF_RUT_CONCURRENCY"'],
            capture_output=True, text=True, timeout=10,
        )
        assert eval_proc.returncode == 0, eval_proc.stderr
        tier, rut = eval_proc.stdout.strip().split("|")
        assert tier in VALID_TIERS, f"eval'd tier '{tier}' invalid"
        assert int(rut) >= 1


# ----------------------------------------------------------------------
# Companion files exist (sanity, no exec)
# ----------------------------------------------------------------------
class TestCompanionFilesExist:
    @pytest.mark.parametrize("path", [
        "/app/scripts/detect-hardware.ps1",
        "/app/docker-compose.micro.yml",
        "/app/docker-compose.lowram.yml",
        "/app/docker-compose.mid.yml",
        "/app/docker-compose.high.yml",
        "/app/docker-compose.beast.yml",
        "/app/RealFlow-RETUNE.bat",
        "/app/RealFlow-RETUNE.sh",
        "/app/PERFORMANCE-PROFILES.md",
    ])
    def test_file_exists_non_empty(self, path):
        assert os.path.exists(path), f"Missing: {path}"
        assert os.path.getsize(path) > 0, f"Empty: {path}"
