import asyncio

from backend.sync_scheduler import SyncScheduler
from sync_engine import SyncTier


def test_continuous_mode_always_delivers_immediately():
    scheduler = SyncScheduler(mode="continuous", interval=100)
    result = scheduler.record("hospA", "icu_beds", SyncTier.ROUTINE)
    assert result["delivered"] is True


def test_periodic_mode_always_queues():
    scheduler = SyncScheduler(mode="periodic", interval=100)
    result = scheduler.record("hospA", "icu_beds", SyncTier.CRITICAL)
    assert result["delivered"] is False
    assert scheduler.pending_hospitals() == ["hospA"]


def test_adaptive_mode_delivers_critical_immediately_and_queues_routine():
    scheduler = SyncScheduler(mode="adaptive", interval=100)
    critical = scheduler.record("hospA", "icu_beds", SyncTier.CRITICAL)
    routine = scheduler.record("hospB", "icu_beds", SyncTier.ROUTINE)
    assert critical["delivered"] is True
    assert routine["delivered"] is False


def test_invalid_mode_is_rejected():
    try:
        SyncScheduler(mode="not-a-real-mode")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_second_update_for_same_hospital_replaces_the_queued_one():
    scheduler = SyncScheduler(mode="periodic", interval=100)
    scheduler.record("hospA", "icu_beds", SyncTier.ROUTINE)
    scheduler.record("hospA", "ventilators", SyncTier.ROUTINE)
    assert scheduler.pending_hospitals() == ["hospA"]  # still just one entry, not two


async def test_periodic_flush_delivers_queued_updates_after_interval():
    scheduler = SyncScheduler(mode="periodic", interval=0.05)
    scheduler.record("hospA", "icu_beds", SyncTier.ROUTINE)
    assert scheduler.pending_hospitals() == ["hospA"]

    scheduler.start()
    await asyncio.sleep(0.15)
    await scheduler.stop()

    assert scheduler.pending_hospitals() == []
    deliveries = scheduler.recent_deliveries()
    assert any(d["hospital_id"] == "hospA" and d["delivered"] for d in deliveries)


async def test_stopping_before_first_flush_leaves_updates_queued():
    scheduler = SyncScheduler(mode="periodic", interval=10)
    scheduler.record("hospA", "icu_beds", SyncTier.ROUTINE)

    scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop()

    assert scheduler.pending_hospitals() == ["hospA"]  # never got the chance to flush
