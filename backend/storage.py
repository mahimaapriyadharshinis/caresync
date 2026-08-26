"""
Storage for hospital resource state and sync-decision history.

InMemoryStore needs no external service and is what the test suite and
local dev use by default. MongoStore is the real deployment target —
point MONGO_URL at a running Mongo instance (see docker/docker-compose.yml)
to persist state and get_store() will return it instead.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Protocol

from sync_engine import ResourceUpdate, ScoreResult


class Storage(Protocol):
    async def get_state(self, hospital_id: str) -> dict[str, int]: ...
    async def set_value(self, hospital_id: str, resource: str, value: int, capacity: int) -> None: ...
    async def record_decision(self, update: ResourceUpdate, score: ScoreResult) -> None: ...
    async def recent_decisions(self, limit: int = 50) -> list[dict]: ...


class InMemoryStore:
    def __init__(self) -> None:
        self._state: dict[str, dict[str, int]] = {}
        self._decisions: list[dict] = []

    async def get_state(self, hospital_id: str) -> dict[str, int]:
        return dict(self._state.get(hospital_id, {}))

    async def set_value(self, hospital_id: str, resource: str, value: int, capacity: int) -> None:
        self._state.setdefault(hospital_id, {})[resource] = value

    async def record_decision(self, update: ResourceUpdate, score: ScoreResult) -> None:
        self._decisions.append(
            {
                "hospital_id": update.hospital_id,
                "resource": update.resource.value,
                "previous_value": update.previous_value,
                "new_value": update.new_value,
                "magnitude": score.magnitude,
                "congestion": score.congestion,
                "urgency": score.urgency,
                "tier": score.tier.value,
                "reason": score.reason,
                "timestamp": update.timestamp.isoformat(),
            }
        )

    async def recent_decisions(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._decisions[-limit:]))


class MongoStore:
    """Motor-backed implementation. Only imports motor when actually
    instantiated, so the rest of the backend works without it installed."""

    def __init__(self, mongo_url: str, db_name: str = "caresync") -> None:
        from motor.motor_asyncio import AsyncIOMotorClient  # local import

        self._client = AsyncIOMotorClient(mongo_url)
        self._db = self._client[db_name]
        self._hospitals = self._db["hospital_state"]
        self._decisions = self._db["sync_decisions"]

    async def get_state(self, hospital_id: str) -> dict[str, int]:
        doc = await self._hospitals.find_one({"_id": hospital_id})
        return dict(doc.get("resources", {})) if doc else {}

    async def set_value(self, hospital_id: str, resource: str, value: int, capacity: int) -> None:
        await self._hospitals.update_one(
            {"_id": hospital_id},
            {
                "$set": {
                    f"resources.{resource}": value,
                    f"capacities.{resource}": capacity,
                    "last_updated": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    async def record_decision(self, update: ResourceUpdate, score: ScoreResult) -> None:
        await self._decisions.insert_one(
            {
                "hospital_id": update.hospital_id,
                "resource": update.resource.value,
                "previous_value": update.previous_value,
                "new_value": update.new_value,
                "magnitude": score.magnitude,
                "congestion": score.congestion,
                "urgency": score.urgency,
                "tier": score.tier.value,
                "reason": score.reason,
                "timestamp": update.timestamp,
            }
        )

    async def recent_decisions(self, limit: int = 50) -> list[dict]:
        cursor = self._decisions.find().sort("timestamp", -1).limit(limit)
        docs = await cursor.to_list(length=limit)
        for doc in docs:
            doc["_id"] = str(doc["_id"])
            doc["timestamp"] = doc["timestamp"].isoformat()
        return docs


def get_store() -> Storage:
    mongo_url = os.environ.get("MONGO_URL")
    if mongo_url:
        return MongoStore(mongo_url)
    return InMemoryStore()
