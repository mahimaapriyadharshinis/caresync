import pytest

from sync_engine import AdaptiveSyncEngine, ResourceType, ResourceUpdate, SyncTier


def make_update(previous, new, capacity=10, resource=ResourceType.ICU_BEDS):
    return ResourceUpdate(
        hospital_id="hospital-a",
        resource=resource,
        previous_value=previous,
        new_value=new,
        capacity=capacity,
    )


def test_icu_hitting_zero_is_always_critical():
    """The project's own example: ICU 3 -> 0 must jump the queue."""
    engine = AdaptiveSyncEngine()
    update = make_update(previous=3, new=0, capacity=10)

    result = engine.evaluate(update, congestion=0.0)

    assert result.tier == SyncTier.CRITICAL
    assert result.magnitude == 1.0


def test_small_change_is_batched_when_network_is_quiet():
    """The project's other example: ICU 15 -> 14 is routine, not urgent."""
    engine = AdaptiveSyncEngine()
    update = make_update(previous=15, new=14, capacity=20)

    result = engine.evaluate(update, congestion=0.1)

    assert result.tier == SyncTier.ROUTINE


def test_small_change_holds_when_network_is_congested():
    engine = AdaptiveSyncEngine()
    update = make_update(previous=15, new=14, capacity=20)

    result = engine.evaluate(update, congestion=0.9)

    assert result.tier == SyncTier.CONGESTED


def test_large_drop_below_zero_threshold_is_still_critical():
    """A big drop that doesn't hit exactly zero should still cross the
    critical-magnitude threshold on its own."""
    engine = AdaptiveSyncEngine()
    update = make_update(previous=10, new=3, capacity=10)  # 70% drop

    result = engine.evaluate(update, congestion=0.0)

    assert result.tier == SyncTier.CRITICAL


def test_resource_increasing_is_never_urgent():
    """Beds freeing up is good news — never worth pre-empting other
    traffic for."""
    engine = AdaptiveSyncEngine()
    update = make_update(previous=2, new=8, capacity=10)

    result = engine.evaluate(update, congestion=0.0)

    assert result.magnitude == 0.0
    assert result.tier == SyncTier.ROUTINE


def test_congestion_out_of_range_is_rejected():
    engine = AdaptiveSyncEngine()
    update = make_update(previous=15, new=14, capacity=20)

    with pytest.raises(ValueError):
        engine.evaluate(update, congestion=1.5)


def test_negative_resource_values_are_rejected():
    with pytest.raises(ValueError):
        make_update(previous=-1, new=0)


def test_values_exceeding_capacity_are_rejected():
    with pytest.raises(ValueError):
        make_update(previous=5, new=12, capacity=10)
