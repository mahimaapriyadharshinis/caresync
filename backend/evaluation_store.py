"""
Read-only access to the `evaluation_runs` collection written by
evaluation/run_comparison.py — backs the /evaluation/* endpoints that
Grafana's Infinity datasource queries for the strategy-comparison
dashboard.
"""
from __future__ import annotations

import os


def _mongo_url() -> str | None:
    return os.environ.get("MONGO_URL")


async def latest_run() -> dict | None:
    mongo_url = _mongo_url()
    if not mongo_url:
        return None
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url)
    doc = await client["caresync"]["evaluation_runs"].find_one(sort=[("run_at", -1)])
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def recent_runs(limit: int = 20) -> list[dict]:
    mongo_url = _mongo_url()
    if not mongo_url:
        return []
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(mongo_url)
    cursor = client["caresync"]["evaluation_runs"].find().sort("run_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["_id"] = str(doc["_id"])
    return docs
