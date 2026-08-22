"""Simulate production fresh-DB seed: run seed_myntra_campaign against a temp DB."""
import asyncio
import os
import sys

from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
for k, v in env.items():
    if v is not None:
        os.environ.setdefault(k, v)
os.environ["DB_NAME"] = "TEST_seed_sim_db"
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from routes.campaign_manager import seed_myntra_campaign, _db  # noqa: E402


async def main():
    print("Simulating on DB:", _db.name)
    assert _db.name == "TEST_seed_sim_db", "env override failed"
    await _db.outreach_campaigns.delete_many({})
    await _db.campaign_prospects.delete_many({})

    await seed_myntra_campaign()
    camp = await _db.outreach_campaigns.find_one({"campaign_id": "7701ea79"})
    n = await _db.campaign_prospects.count_documents({"campaign_id": "7701ea79"})
    pending = await _db.campaign_prospects.count_documents({"campaign_id": "7701ea79", "status": "pending"})
    print(f"campaign_created={camp is not None} prospects={n} pending={pending}")
    bad_name = await _db.campaign_prospects.count_documents({"campaign_id": "7701ea79", "name": ""})
    print("prospects_with_empty_name:", bad_name)
    print("attachment_path_present:", bool(camp.get("attachment_path")))

    # idempotency: run twice
    await seed_myntra_campaign()
    n2 = await _db.campaign_prospects.count_documents({"campaign_id": "7701ea79"})
    print(f"after_second_run={n2} duplicated={n2 != n}")

    # cleanup temp db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    await client.drop_database("TEST_seed_sim_db")
    print("temp db dropped")

asyncio.run(main())
