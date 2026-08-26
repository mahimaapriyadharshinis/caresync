"""
Stand-in for the real network-congestion signal.

In the full deployment this value comes from
controller/congestion_monitor.py, which polls OpenFlow port statistics
via the SDN controller. Keeping it behind this small interface lets the
backend be developed and tested without Mininet or a controller
running, and swapped for a real HTTP call to the controller's stats
endpoint later without touching main.py.
"""
from __future__ import annotations


class CongestionProvider:
    def __init__(self, default: float = 0.0) -> None:
        self._default = default
        self._levels: dict[str, float] = {}

    def get(self, hospital_id: str) -> float:
        return self._levels.get(hospital_id, self._default)

    def set(self, hospital_id: str, value: float) -> None:
        self._levels[hospital_id] = value
