"""
Live scheduler implementing continuous, periodic, and adaptive delivery
timing — the same three strategies evaluation/strategies.py compares
offline, now actually running against real requests to the backend.

SYNC_MODE (env var): "adaptive" (default) | "continuous" | "periodic"

This is deliberately a separate concern from controller_client.py's
CRITICAL flow-priority notification: this scheduler governs *when the
backend considers an update delivered to the rest of the system*
(an application-layer timing question), while the controller hook
governs *how the network prioritizes a packet once it's sent*
(a network-layer QoS question). A real deployment could run periodic
application-level sync while still wanting the underlying network to
fast-path anything urgent — the two are independent by design.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from sync_engine import SyncTier

SYNC_MODE = os.environ.get("SYNC_MODE", "adaptive")
PERIODIC_INTERVAL_SECONDS = float(os.environ.get("PERIODIC_INTERVAL_SECONDS", "15"))

VALID_MODES = ("adaptive", "continuous", "periodic")


@dataclass
class PendingDelivery:
    hospital_id: str
    resource: str
    tier: str
    received_at: float


class SyncScheduler:
    """Queues non-immediate updates and flushes them on a timer. Updates
    that go out immediately (continuous mode; adaptive's CRITICAL tier)
    never touch the queue at all."""

    def __init__(self, mode: str = SYNC_MODE, interval: float = PERIODIC_INTERVAL_SECONDS) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
        self.mode = mode
        self.interval = interval
        self._queue: dict[str, PendingDelivery] = {}  # hospital_id -> latest pending
        self._delivered_log: list[dict] = []
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def is_immediate(self, tier: SyncTier) -> bool:
        if self.mode == "continuous":
            return True
        if self.mode == "periodic":
            return False
        return tier == SyncTier.CRITICAL  # adaptive

    def record(self, hospital_id: str, resource: str, tier: SyncTier) -> dict:
        """Returns a delivery record: either delivered immediately, or
        queued for the next flush."""
        now = time.monotonic()
        if self.is_immediate(tier):
            return self._log_delivery(hospital_id, resource, tier, received_at=now, delivered_at=now)
        self._queue[hospital_id] = PendingDelivery(hospital_id, resource, tier.value, now)
        return {
            "hospital_id": hospital_id,
            "mode": self.mode,
            "delivered": False,
            "queued_for_next_flush_in_seconds": round(self.interval, 1),
        }

    def _log_delivery(self, hospital_id: str, resource: str, tier, received_at: float, delivered_at: float) -> dict:
        record = {
            "hospital_id": hospital_id,
            "resource": resource,
            "tier": tier.value if isinstance(tier, SyncTier) else tier,
            "mode": self.mode,
            "delivered": True,
            "staleness_seconds": round(delivered_at - received_at, 3),
        }
        self._delivered_log.append(record)
        return record

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.interval)
                self._flush()
        except asyncio.CancelledError:
            pass

    def _flush(self) -> None:
        now = time.monotonic()
        for pending in list(self._queue.values()):
            self._log_delivery(pending.hospital_id, pending.resource, pending.tier, pending.received_at, now)
        self._queue.clear()

    def recent_deliveries(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._delivered_log[-limit:]))

    def pending_hospitals(self) -> list[str]:
        return sorted(self._queue.keys())
