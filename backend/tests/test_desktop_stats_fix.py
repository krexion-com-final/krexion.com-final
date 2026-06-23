"""
Unit test for the v2.1.59 desktop_module.py bug fix.

Verifies that the Native PC dashboard's `/api/desktop/stats` endpoint
correctly populates Active + Recent jobs panels from the `bridge_jobs`
collection — previously broken due to wrong field-name projections.

Run with:
    cd /app/krexion_repo/backend
    KREXION_MODE=local python -m pytest tests/test_desktop_stats_fix.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend dir to path so we can import desktop_module
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force local mode so _active_and_recent_jobs actually queries
os.environ["KREXION_MODE"] = "local"

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import desktop_module


# ───────────────────────── Pure helper tests ──────────────────────────

def test_feature_to_label_known_prefixes():
    assert desktop_module._feature_to_label("visual-recorder/start") == "Visual Recorder · start"
    assert desktop_module._feature_to_label("real-user-traffic/jobs") == "Real User Traffic · jobs"
    assert desktop_module._feature_to_label("form-filler/jobs") == "Form Filler · jobs"
    assert desktop_module._feature_to_label("adspower/create") == "AdsPower · create"
    assert desktop_module._feature_to_label("browser-profile/launch") == "Browser Profile · launch"
    assert desktop_module._feature_to_label("proxies/bulk-test") == "Proxy Check · bulk test"


def test_feature_to_label_strips_api_prefix_and_uuids():
    # Path-style features (auto-route uses URL paths)
    sid = uuid.uuid4().hex
    label = desktop_module._feature_to_label(f"/api/visual-recorder/{sid}/screenshot")
    assert label == "Visual Recorder · screenshot"


def test_feature_to_label_unknown_prefix_falls_back():
    assert desktop_module._feature_to_label("custom-thing/do") == "Custom Thing · do"
    assert desktop_module._feature_to_label("") == "job"
    assert desktop_module._feature_to_label(None) == "job"  # type: ignore[arg-type]


def test_bridge_detail_pulls_url_from_payload_body():
    doc = {
        "payload": {"body": {"url": "https://example.com/offer"}, "path": "/api/x"},
        "status": "running",
    }
    assert desktop_module._bridge_detail(doc) == "https://example.com/offer"


def test_bridge_detail_falls_back_to_error_then_path():
    err_doc = {"payload": {"body": {}}, "status": "failed", "error": "proxy timeout"}
    assert desktop_module._bridge_detail(err_doc).startswith("⚠ proxy timeout")

    path_doc = {"payload": {"body": {}, "path": "/api/some/endpoint"}, "status": "running"}
    assert desktop_module._bridge_detail(path_doc) == "/api/some/endpoint"


def test_bridge_detail_session_id_from_result():
    sid = uuid.uuid4().hex
    doc = {
        "payload": {"body": {}},
        "status": "done",
        "result": {"body": {"session_id": sid}},
    }
    assert sid[:12] in desktop_module._bridge_detail(doc)


# ───────────────────────── Mongo-integration tests ────────────────────

@pytest.fixture
async def db():
    """Spin up an isolated test database — uses local MongoDB."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
    test_db_name = f"krexion_test_{uuid.uuid4().hex[:8]}"
    test_db = client[test_db_name]
    desktop_module._db = test_db  # bind the module-level db
    yield test_db
    # cleanup
    await client.drop_database(test_db_name)
    client.close()


def _now_iso(offset_sec: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_sec)).isoformat()


@pytest.mark.asyncio
async def test_active_jobs_show_friendly_kind_and_detail(db):
    """A running visual-recorder job should appear with a friendly label
    AND a non-empty detail (the target URL)."""
    await db.bridge_jobs.insert_one({
        "id": uuid.uuid4().hex,
        "user_id": "u-1",
        "feature": "visual-recorder/start",
        "payload": {"body": {"url": "https://offer.example.com/cpa"}},
        "status": "running",
        "created_at": _now_iso(-30),
        "started_at": _now_iso(-25),
    })
    result = await desktop_module._active_and_recent_jobs()
    assert len(result["active"]) == 1
    row = result["active"][0]
    assert row["kind"] == "Visual Recorder · start"          # <-- friendly label
    assert row["detail"] == "https://offer.example.com/cpa"  # <-- detail populated
    assert row["status"] == "running"
    assert row["started_ago"]                                # non-empty


@pytest.mark.asyncio
async def test_recent_jobs_match_done_and_failed_status(db):
    """Recent activity must include jobs whose status is 'done' or 'failed'.
    Previously the query filtered on 'completed'/'error' (wrong) so this
    list was ALWAYS empty even on busy installs."""
    await db.bridge_jobs.insert_many([
        {
            "id": uuid.uuid4().hex,
            "user_id": "u-1",
            "feature": "real-user-traffic/jobs",
            "payload": {"body": {"name": "Campaign Alpha"}},
            "status": "done",
            "created_at": _now_iso(-600),
            "completed_at": _now_iso(-300),
        },
        {
            "id": uuid.uuid4().hex,
            "user_id": "u-1",
            "feature": "form-filler/jobs",
            "payload": {"body": {}},
            "status": "failed",
            "error": "proxy unreachable",
            "created_at": _now_iso(-500),
            "completed_at": _now_iso(-200),
        },
    ])
    result = await desktop_module._active_and_recent_jobs()
    assert len(result["recent"]) == 2, f"Expected 2 recent rows, got {result['recent']}"
    # Most recent first
    statuses = [r["status"] for r in result["recent"]]
    kinds = [r["kind"] for r in result["recent"]]
    assert "completed" in statuses                # done → completed
    assert "failed" in statuses
    assert "Real User Traffic · jobs" in kinds
    assert "Form Filler · jobs" in kinds
    # Detail surfaces the error on failed rows
    failed_row = next(r for r in result["recent"] if r["status"] == "failed")
    assert "proxy unreachable" in failed_row["detail"]


@pytest.mark.asyncio
async def test_throughput_counts_completed_in_last_hour(db):
    """jobs_per_hour + success_rate_pct must reflect actual completion
    activity — previously zeroed because count_documents queried
    `finished_at` (no such field)."""
    await db.bridge_jobs.insert_many([
        {
            "feature": "real-user-traffic/jobs",
            "status": "done",
            "completed_at": _now_iso(-1500),       # 25 min ago — in window
        },
        {
            "feature": "form-filler/jobs",
            "status": "done",
            "completed_at": _now_iso(-100),        # 100s ago — in window
        },
        {
            "feature": "real-user-traffic/jobs",
            "status": "failed",
            "completed_at": _now_iso(-2000),       # in window
        },
        {
            "feature": "old/job",
            "status": "done",
            "completed_at": _now_iso(-7200),       # 2h ago — OUT of window
        },
    ])
    result = await desktop_module._active_and_recent_jobs()
    t = result["throughput"]
    assert t["jobs_per_hour"] == 3              # 2 done + 1 failed in last hour
    # 2 successful out of 3 → ~66.6%
    assert 60.0 < t["success_rate_pct"] < 75.0


@pytest.mark.asyncio
async def test_empty_db_returns_clean_empty_payload(db):
    result = await desktop_module._active_and_recent_jobs()
    assert result["active"] == []
    assert result["recent"] == []
    assert result["throughput"] == {"jobs_per_hour": 0, "success_rate_pct": 0}


@pytest.mark.asyncio
async def test_active_jobs_sorted_newest_first(db):
    """Newest active job must appear first in the list."""
    base = datetime.now(timezone.utc)
    await db.bridge_jobs.insert_many([
        {
            "id": "old",
            "feature": "real-user-traffic/jobs",
            "payload": {"body": {"name": "Older"}},
            "status": "running",
            "created_at": (base - timedelta(minutes=10)).isoformat(),
        },
        {
            "id": "new",
            "feature": "visual-recorder/start",
            "payload": {"body": {"name": "Newer"}},
            "status": "pending",
            "created_at": (base - timedelta(minutes=1)).isoformat(),
        },
    ])
    result = await desktop_module._active_and_recent_jobs()
    assert len(result["active"]) == 2
    assert result["active"][0]["kind"].startswith("Visual Recorder")
    assert result["active"][1]["kind"].startswith("Real User Traffic")
