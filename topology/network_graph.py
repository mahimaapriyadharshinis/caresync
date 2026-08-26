"""
NetworkX representation of the hospital network topology, mirroring
topology/hospital_net.py (hospitals + ambulances on one switch).

This is what makes NetworkX a load-bearing part of the project rather
than an unused dependency: the evaluation harness derives each
hospital's broadcast fan-out — how many other hospitals a message
actually has to reach — from this graph's connectivity, instead of a
flat constant.
"""
from __future__ import annotations

import networkx as nx

from deployment_config import HOSPITAL_MACS

SWITCH = "s1"
AMBULANCES = ("amb1", "amb2")


def build_topology_graph() -> nx.Graph:
    """One graph mirroring topology/hospital_net.py: every host links to
    the single switch s1."""
    graph = nx.Graph()
    graph.add_node(SWITCH, kind="switch")

    for hospital_id in HOSPITAL_MACS:
        graph.add_node(hospital_id, kind="hospital")
        graph.add_edge(hospital_id, SWITCH)

    for amb in AMBULANCES:
        graph.add_node(amb, kind="ambulance")
        graph.add_edge(amb, SWITCH)

    return graph


def hospitals(graph: nx.Graph) -> list[str]:
    return sorted(n for n, data in graph.nodes(data=True) if data.get("kind") == "hospital")


def other_hospitals(graph: nx.Graph, hospital_id: str) -> list[str]:
    """Every other hospital reachable from `hospital_id` — the set that
    needs to learn about its resource change. Computed via graph
    connectivity rather than assumed."""
    if hospital_id not in graph:
        return []
    reachable = nx.node_connected_component(graph, hospital_id)
    return sorted(h for h in hospitals(graph) if h in reachable and h != hospital_id)


def fanout(graph: nx.Graph, hospital_id: str) -> int:
    return len(other_hospitals(graph, hospital_id))
