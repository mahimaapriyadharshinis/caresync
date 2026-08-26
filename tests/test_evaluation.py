from evaluation.network_conditions import congestion_at
from evaluation.run_comparison import run
from evaluation.strategies import run_adaptive, run_continuous, run_periodic
from simulation.event_generator import GeneratorConfig, SyntheticEventGenerator


def _trace(seed=1, count=200):
    gen = SyntheticEventGenerator(GeneratorConfig(seed=seed))
    return list(gen.stream(count))


def test_continuous_sends_the_most_messages():
    events = _trace()
    continuous = run_continuous(events, num_hospitals=3)
    periodic = run_periodic(events, num_hospitals=3)
    adaptive = run_adaptive(events, num_hospitals=3, congestion_at=congestion_at)

    assert continuous.messages_sent > adaptive.messages_sent
    assert continuous.messages_sent > periodic.messages_sent


def test_continuous_has_zero_staleness():
    continuous = run_continuous(_trace(), num_hospitals=3)
    assert continuous.avg_staleness == 0.0


def test_periodic_has_higher_staleness_than_continuous():
    events = _trace()
    continuous = run_continuous(events, num_hospitals=3)
    periodic = run_periodic(events, num_hospitals=3)
    assert periodic.avg_staleness > continuous.avg_staleness


def test_adaptive_keeps_critical_events_near_zero_staleness():
    """The project's headline claim: adaptive shouldn't let a critical
    event go stale, even though it isn't broadcasting everything."""
    events = _trace(seed=7, count=300)
    adaptive = run_adaptive(events, num_hospitals=3, congestion_at=congestion_at)

    critical_staleness = adaptive.staleness_for_tier("critical")
    assert critical_staleness, "expected at least one critical event in this trace"
    assert max(critical_staleness) < 1.0  # delivered essentially immediately


def test_adaptive_sends_fewer_messages_than_continuous():
    events = _trace(seed=3, count=300)
    continuous = run_continuous(events, num_hospitals=3)
    adaptive = run_adaptive(events, num_hospitals=3, congestion_at=congestion_at)
    assert adaptive.messages_sent < continuous.messages_sent


def test_congested_tier_gets_exercised_by_the_synthetic_congestion_signal():
    events = _trace(seed=11, count=400)
    adaptive = run_adaptive(events, num_hospitals=3, congestion_at=congestion_at)
    assert adaptive.staleness_for_tier("congested"), "expected at least one congested-tier delivery"


def test_full_comparison_run_produces_all_three_strategies():
    result = run(num_events=150, seed=5, num_hospitals=3)
    names = {s["strategy"] for s in result["strategies"]}
    assert names == {"continuous", "periodic", "adaptive"}
    assert result["critical_events"] >= 0


def test_adaptive_beats_periodic_staleness_on_the_events_that_matter():
    """Where the project's core research question actually gets
    answered: for the events that were critical, adaptive delivers far
    faster than periodic would have."""
    result = run(num_events=400, seed=13, num_hospitals=3)
    if result["critical_events"] == 0:
        return  # trace happened to have none; nothing to compare
    assert (
        result["adaptive_critical_avg_staleness_seconds"]
        < result["periodic_would_be_staleness_for_critical_events_seconds"]
    )
