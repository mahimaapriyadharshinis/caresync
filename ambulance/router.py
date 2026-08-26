"""
The decision-maker CARESync exists to inform.

The project's own motivation slide poses the scenario directly: three
hospitals, three ambulances, Hospital A suddenly runs out of ICU beds —
if an ambulance dispatch system learns that five minutes late, it sends
a patient toward a hospital that cannot take them. Everything else in
this project (the Adaptive Sync Engine, the SDN controller, the
priority flows) exists to keep hospital state fresh; this module is
what actually consumes that state to make the routing call.
"""
from __future__ import annotations


def rank_hospitals(states: dict[str, dict[str, int]], resource: str) -> list[tuple[str, int]]:
    """Hospitals with remaining capacity for `resource`, best first.
    Hospitals reporting zero (or that have never reported this
    resource) are excluded outright — sending an ambulance there is
    exactly the mistake this project exists to prevent."""
    candidates = [
        (hospital_id, resources[resource])
        for hospital_id, resources in states.items()
        if resource in resources and resources[resource] > 0
    ]
    return sorted(candidates, key=lambda pair: pair[1], reverse=True)


def choose_hospital(states: dict[str, dict[str, int]], resource: str) -> str | None:
    """The single best hospital to route an ambulance to for `resource`,
    or None if every known hospital is currently at zero."""
    ranked = rank_hospitals(states, resource)
    return ranked[0][0] if ranked else None
