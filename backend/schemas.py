from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from sync_engine import ResourceType, SyncTier


class ResourceUpdateIn(BaseModel):
    resource: ResourceType
    new_value: int = Field(ge=0)
    capacity: int = Field(gt=0)


class SyncDecisionOut(BaseModel):
    hospital_id: str
    resource: ResourceType
    previous_value: int
    new_value: int
    magnitude: float
    congestion: float
    urgency: float
    tier: SyncTier
    reason: str
    timestamp: datetime
    sync_mode: str
    delivered: bool
    queued_for_next_flush_in_seconds: float | None = None
    is_first_report: bool = False


class HospitalStateOut(BaseModel):
    hospital_id: str
    resources: dict[str, int]
