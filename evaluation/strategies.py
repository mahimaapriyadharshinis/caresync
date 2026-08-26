"""
Analytical comparison of the three synchronization strategies described
in the project proposal, over the same synthetic event trace — Phase
5's own deliverable: "Run the same synthetic event trace through
continuous, periodic, and your adaptive engine — plot all three side
by side."

Every strategy reports, per update: how many network messages it took
to eventually deliver it to the other hospitals (the communication
overhead claim), and staleness — seconds between when the resource
actually changed and when the other hospitals learned about it (the
decision-accuracy claim). Broadcast fan-out (one hospital's message
reaching the other N-1 hospitals) is counted explicitly, mirroring the
existing system's "redundant broadcasts to all nodes" behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sync_engine import AdaptiveSyncEngine, ResourceUpdate, SyncTier

PERIODIC_INTERVAL_SECONDS = 300.0  # the proposal's own example: "Periodic (e.g., 5 min)"
CONGESTED_HOLD_SECONDS = 30.0  # how long a CONGESTED update waits before retry


@dataclass
class DeliveryRecord:
    """One update, and when it was actually delivered to the other
    hospitals under a given strategy."""

    hospital_id: str
    resource: str
    event_time: float
    delivered_time: float
    tier: str | None  # only meaningful for the adaptive strategy

    @property
    def staleness(self) -> float:
        return self.delivered_time - self.event_time


@dataclass
class StrategyResult:
    name: str
    deliveries: list[DeliveryRecord]
    messages_sent: int

    @property
    def avg_staleness(self) -> float:
        if not self.deliveries:
            return 0.0
        return sum(d.staleness for d in self.deliveries) / len(self.deliveries)

    @property
    def max_staleness(self) -> float:
        return max((d.staleness for d in self.deliveries), default=0.0)

    def staleness_for_tier(self, tier: str) -> list[float]:
        return [d.staleness for d in self.deliveries if d.tier == tier]


def _fanout(num_hospitals: int) -> int:
    return max(0, num_hospitals - 1)


def run_continuous(events: list[tuple[float, ResourceUpdate]], num_hospitals: int) -> StrategyResult:
    """Every update is broadcast immediately — the existing system's
    behavior (redundant broadcasts to all nodes regardless of need)."""
    deliveries = [
        DeliveryRecord(u.hospital_id, u.resource.value, t, t, tier=None) for t, u in events
    ]
    return StrategyResult("continuous", deliveries, messages_sent=len(events) * _fanout(num_hospitals))


def run_periodic(
    events: list[tuple[float, ResourceUpdate]],
    num_hospitals: int,
    interval: float = PERIODIC_INTERVAL_SECONDS,
) -> StrategyResult:
    """Every hospital broadcasts its full state on a fixed timer,
    regardless of whether anything changed — timer-based sync."""
    if not events:
        return StrategyResult("periodic", [], 0)

    end_time = events[-1][0]
    num_ticks = int(end_time // interval) + 2  # one past the last event, for safety

    deliveries = [
        DeliveryRecord(u.hospital_id, u.resource.value, t, (int(t // interval) + 1) * interval, tier=None)
        for t, u in events
    ]

    messages = num_hospitals * num_ticks * _fanout(num_hospitals)
    return StrategyResult("periodic", deliveries, messages_sent=messages)


def run_adaptive(
    events: list[tuple[float, ResourceUpdate]],
    num_hospitals: int,
    congestion_at: Callable[[float], float],
    interval: float = PERIODIC_INTERVAL_SECONDS,
    congested_hold: float = CONGESTED_HOLD_SECONDS,
) -> StrategyResult:
    """CRITICAL updates broadcast immediately (like continuous, but only
    for updates that earn it). CONGESTED updates wait out the
    congestion, then send individually. ROUTINE updates batch onto the
    same fixed timer periodic uses."""
    engine = AdaptiveSyncEngine()
    fanout = _fanout(num_hospitals)

    deliveries: list[DeliveryRecord] = []
    immediate_messages = 0
    # a batched routine update is bundled into that hospital's next
    # full-state sync — one message per (hospital, tick), same
    # granularity as periodic's full-state broadcast, regardless of how
    # many of that hospital's resources changed in the same window
    routine_ticks_billed: set[tuple[str, float]] = set()

    for t, u in events:
        score = engine.evaluate(u, congestion_at(t))

        if score.tier == SyncTier.CRITICAL:
            deliveries.append(DeliveryRecord(u.hospital_id, u.resource.value, t, t, tier="critical"))
            immediate_messages += 1
            continue

        if score.tier == SyncTier.CONGESTED:
            deliveries.append(
                DeliveryRecord(u.hospital_id, u.resource.value, t, t + congested_hold, tier="congested")
            )
            immediate_messages += 1
            continue

        next_tick = (int(t // interval) + 1) * interval
        deliveries.append(DeliveryRecord(u.hospital_id, u.resource.value, t, next_tick, tier="routine"))
        routine_ticks_billed.add((u.hospital_id, next_tick))

    messages = (immediate_messages + len(routine_ticks_billed)) * fanout
    return StrategyResult("adaptive", deliveries, messages_sent=messages)
