"""Shared data structures for the Adaptive Sync Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ResourceType(str, Enum):
    ICU_BEDS = "icu_beds"
    ER_CAPACITY = "er_capacity"
    VENTILATORS = "ventilators"


class SyncTier(str, Enum):
    CRITICAL = "critical"      # sync now, highest OpenFlow priority
    CONGESTED = "congested"    # hold briefly, sync once the link clears
    ROUTINE = "routine"        # batch into the next periodic interval


@dataclass(frozen=True)
class ResourceUpdate:
    """One reported change in a hospital's resource state."""

    hospital_id: str
    resource: ResourceType
    previous_value: int
    new_value: int
    capacity: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if self.previous_value < 0 or self.new_value < 0:
            raise ValueError("resource values cannot be negative")
        if self.previous_value > self.capacity or self.new_value > self.capacity:
            raise ValueError("resource values cannot exceed capacity")

    @property
    def delta(self) -> int:
        return self.new_value - self.previous_value

    @property
    def hit_zero(self) -> bool:
        """The resource just ran out — the textbook 'ICU 3 -> 0' case."""
        return self.previous_value > 0 and self.new_value == 0


@dataclass(frozen=True)
class ScoreResult:
    """Output of the Adaptive Sync Engine for one update."""

    magnitude: float   # normalized 0..1 severity of the resource change
    congestion: float  # normalized 0..1 current network load
    urgency: float      # blended 0..1 score, used for logging/ranking only
    tier: SyncTier       # the actual routing decision
    reason: str
