"""
Synthetic ICU/ER/ventilator event generator.

Real hospital telemetry is restricted, so this generates resource-change
events with a Poisson arrival process per hospital/resource track: events
land at realistic, uneven intervals rather than a fixed clock tick, and
each event's size is drawn from a distribution biased toward small
routine changes with an occasional large or zero-hitting swing — this
is the trace Phase 5 replays through continuous, periodic, and adaptive
sync strategies for comparison.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterator

from sync_engine import ResourceType, ResourceUpdate

DEFAULT_CAPACITY: dict[str, int] = {
    ResourceType.ICU_BEDS.value: 12,
    ResourceType.ER_CAPACITY.value: 30,
    ResourceType.VENTILATORS.value: 8,
}


@dataclass
class GeneratorConfig:
    hospital_ids: tuple[str, ...] = ("hospital-a", "hospital-b", "hospital-c")
    resources: tuple[ResourceType, ...] = (
        ResourceType.ICU_BEDS,
        ResourceType.ER_CAPACITY,
        ResourceType.VENTILATORS,
    )
    capacity: dict[str, int] = field(default_factory=dict)  # per-resource override
    mean_events_per_hospital_per_hour: float = 6.0
    critical_event_probability: float = 0.08
    seed: int | None = None


class SyntheticEventGenerator:
    """Generates an ordered stream of ResourceUpdate events across all
    configured hospitals and resources, interleaved by simulated time."""

    def __init__(self, config: GeneratorConfig = GeneratorConfig()) -> None:
        self.config = config
        self._rng = random.Random(config.seed)
        self._capacity = {**DEFAULT_CAPACITY, **config.capacity}
        self._state: dict[tuple[str, ResourceType], int] = {
            (h, r): self._capacity[r.value]
            for h in config.hospital_ids
            for r in config.resources
        }

    def _next_interval_seconds(self) -> float:
        rate_per_second = self.config.mean_events_per_hospital_per_hour / 3600.0
        return self._rng.expovariate(rate_per_second)

    def _next_value(self, current: int, capacity: int) -> int:
        if self._rng.random() < self.config.critical_event_probability:
            # a critical swing: the resource runs out, or a ward
            # freeing up suddenly restores most of it
            return 0 if self._rng.random() < 0.7 else capacity
        step = self._rng.choice([-2, -1, -1, 0, 1, 1, 2])
        return max(0, min(capacity, current + step))

    def stream(self, count: int) -> Iterator[tuple[float, ResourceUpdate]]:
        """Yield `count` events as (elapsed_seconds, update) pairs, sorted
        by simulated time across all hospital/resource tracks."""
        pending: list[tuple[float, str, ResourceType]] = [
            (self._next_interval_seconds(), hospital_id, resource)
            for (hospital_id, resource) in self._state
        ]

        emitted = 0
        while emitted < count:
            pending.sort(key=lambda item: item[0])
            due_time, hospital_id, resource = pending.pop(0)

            capacity = self._capacity[resource.value]
            previous = self._state[(hospital_id, resource)]
            new_value = self._next_value(previous, capacity)
            self._state[(hospital_id, resource)] = new_value

            update = ResourceUpdate(
                hospital_id=hospital_id,
                resource=resource,
                previous_value=previous,
                new_value=new_value,
                capacity=capacity,
            )
            yield due_time, update
            emitted += 1

            pending.append((due_time + self._next_interval_seconds(), hospital_id, resource))
