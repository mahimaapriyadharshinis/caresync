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
reaching the other hospitals) is derived from the actual topology graph
(topology/network_graph.py) rather than a flat constant, mirroring the
existing system's "redundant broadcasts to all nodes" behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import networkx as nx

from sync_engine import AdaptiveSyncEngine, ResourceUpdate, SyncTier
from topology.network_graph import fanout as graph_fanout
from topology.network_graph import hospitals as graph_hospitals

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


def run_continuous(events: list[tuple[float, ResourceUpdate]], graph: nx.Graph) -> StrategyResult:
    """Every update is broadcast immediately to every other hospital the
    graph says is reachable — the existing system's behavior (redundant
    broadcasts to all nodes regardless of need)."""
    deliveries = []
    messages = 0
    for t, u in events:
        deliveries.append(DeliveryRecord(u.hospital_id, u.resource.value, t, t, tier=None))
        messages += graph_fanout(graph, u.hospital_id)
    return StrategyResult("continuous", deliveries, messages_sent=messages)


def run_periodic(
    events: list[tuple[float, ResourceUpdate]],
    graph: nx.Graph,
    interval: float = PERIODIC_INTERVAL_SECONDS,
) -> StrategyResult:
    """Every hospital broadcasts its full state to every other reachable
    hospital on a fixed timer, regardless of whether anything changed —
    timer-based sync."""
    if not events:
        return StrategyResult("periodic", [], 0)

    end_time = events[-1][0]
    num_ticks = int(end_time // interval) + 2  # one past the last event, for safety

    deliveries = [
        DeliveryRecord(u.hospital_id, u.resource.value, t, (int(t // interval) + 1) * interval, tier=None)
        for t, u in events
    ]

    messages = sum(graph_fanout(graph, h) for h in graph_hospitals(graph)) * num_ticks
    return StrategyResult("periodic", deliveries, messages_sent=messages)


def run_adaptive(
    events: list[tuple[float, ResourceUpdate]],
    graph: nx.Graph,
    congestion_at: Callable[[float], float],
    interval: float = PERIODIC_INTERVAL_SECONDS,
    congested_hold: float = CONGESTED_HOLD_SECONDS,
) -> StrategyResult:
    """CRITICAL updates broadcast immediately (like continuous, but only
    for updates that earn it). CONGESTED updates wait out the
    congestion, then send individually. ROUTINE updates batch onto the
    same fixed timer periodic uses."""
    engine = AdaptiveSyncEngine()

    deliveries: list[DeliveryRecord] = []
    messages = 0
    # a batched routine update is bundled into that hospital's next
    # full-state sync — one message per (hospital, tick), same
    # granularity as periodic's full-state broadcast, regardless of how
    # many of that hospital's resources changed in the same window
    routine_ticks_billed: set[tuple[str, float]] = set()

    for t, u in events:
        score = engine.evaluate(u, congestion_at(t))

        if score.tier == SyncTier.CRITICAL:
            deliveries.append(DeliveryRecord(u.hospital_id, u.resource.value, t, t, tier="critical"))
            messages += graph_fanout(graph, u.hospital_id)
            continue

        if score.tier == SyncTier.CONGESTED:
            deliveries.append(
                DeliveryRecord(u.hospital_id, u.resource.value, t, t + congested_hold, tier="congested")
            )
            messages += graph_fanout(graph, u.hospital_id)
            continue

        next_tick = (int(t // interval) + 1) * interval
        deliveries.append(DeliveryRecord(u.hospital_id, u.resource.value, t, next_tick, tier="routine"))
        routine_ticks_billed.add((u.hospital_id, next_tick))

    for hospital_id, _tick in routine_ticks_billed:
        messages += graph_fanout(graph, hospital_id)

    return StrategyResult("adaptive", deliveries, messages_sent=messages)
