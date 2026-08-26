from simulation.event_generator import GeneratorConfig, SyntheticEventGenerator


def test_stream_yields_requested_count():
    gen = SyntheticEventGenerator(GeneratorConfig(seed=1))
    events = list(gen.stream(50))
    assert len(events) == 50


def test_values_stay_within_capacity_bounds():
    gen = SyntheticEventGenerator(GeneratorConfig(seed=2))
    for _, update in gen.stream(200):
        assert 0 <= update.new_value <= update.capacity
        assert 0 <= update.previous_value <= update.capacity


def test_timestamps_are_non_decreasing():
    gen = SyntheticEventGenerator(GeneratorConfig(seed=3))
    times = [t for t, _ in gen.stream(100)]
    assert times == sorted(times)


def test_seed_is_reproducible():
    a = list(SyntheticEventGenerator(GeneratorConfig(seed=42)).stream(30))
    b = list(SyntheticEventGenerator(GeneratorConfig(seed=42)).stream(30))
    a_vals = [(u.hospital_id, u.resource, u.new_value) for _, u in a]
    b_vals = [(u.hospital_id, u.resource, u.new_value) for _, u in b]
    assert a_vals == b_vals


def test_some_critical_zero_events_occur_eventually():
    gen = SyntheticEventGenerator(GeneratorConfig(seed=7, critical_event_probability=0.5))
    hit_zero = any(update.hit_zero for _, update in gen.stream(200))
    assert hit_zero
