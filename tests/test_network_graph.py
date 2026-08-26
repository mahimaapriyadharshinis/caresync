from topology.network_graph import build_topology_graph, fanout, hospitals, other_hospitals


def test_all_three_hospitals_present():
    graph = build_topology_graph()
    assert hospitals(graph) == ["hospA", "hospB", "hospC"]


def test_other_hospitals_excludes_self():
    graph = build_topology_graph()
    others = other_hospitals(graph, "hospA")
    assert "hospA" not in others
    assert set(others) == {"hospB", "hospC"}


def test_fanout_matches_other_hospitals_count():
    graph = build_topology_graph()
    for h in hospitals(graph):
        assert fanout(graph, h) == len(other_hospitals(graph, h)) == 2


def test_unknown_hospital_has_no_reachable_peers():
    graph = build_topology_graph()
    assert other_hospitals(graph, "not-a-real-hospital") == []
    assert fanout(graph, "not-a-real-hospital") == 0


def test_ambulances_are_not_counted_as_hospitals():
    graph = build_topology_graph()
    assert "amb1" not in hospitals(graph)
    assert "amb1" not in other_hospitals(graph, "hospA")
