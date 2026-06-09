"""End-to-end regression test for IdentityStore (Step 5 Big-4).

Runs against the local MongoDB. Skips when MONGO_URL isn't reachable.
"""
import asyncio
import os
import sys
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from advanced_anti_detect import IdentityStore  # noqa: E402


@pytest.mark.asyncio
async def test_identity_store_full_e2e():
    c = AsyncIOMotorClient(
        os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=2000,
    )
    db = c[os.environ.get("DB_NAME", "krexion")]
    try:
        await db.command("ping")
    except Exception:
        pytest.skip("MongoDB not reachable in this env")

    store = IdentityStore(db)
    label = f"pytest-{os.urandom(4).hex()}"

    # 1. create
    doc = await store.get_or_create(owner_user_id="pytest", label=label)
    assert doc["id"].startswith("id_")
    identity_id = doc["id"]

    try:
        # 2. save + 3. load storage_state
        fake_ss = {
            "cookies": [
                {"name": "cf_clearance", "value": "abc", "domain": ".x.com", "path": "/"}
            ],
            "origins": [
                {"origin": "https://x.com", "localStorage": [{"name": "k", "value": "v"}]}
            ],
        }
        await store.save_storage_state(identity_id, fake_ss)
        loaded = await store.load_storage_state(identity_id)
        assert loaded == fake_ss

        # 4. fpHash stable
        h1 = await store.get_or_set_fp_hash(identity_id)
        h2 = await store.get_or_set_fp_hash(identity_id)
        assert h1 == h2 and h1 != 0

        # 5. reserve_visit_slot rate-limits
        w1 = await store.reserve_visit_slot(identity_id, target_per_hour=60)
        assert w1 == 0.0
        w2 = await store.reserve_visit_slot(identity_id, target_per_hour=60)
        assert w2 > 30.0, f"second reservation should wait, got {w2}"

        # 6. same label returns same identity
        doc2 = await store.get_or_create(owner_user_id="pytest", label=label)
        assert doc2["id"] == identity_id
    finally:
        await db.anti_detect_identities.delete_one({"id": identity_id})


if __name__ == "__main__":
    asyncio.run(test_identity_store_full_e2e())
    print("OK")
