"""
Shared identifiers between the backend and the SDN controller/topology.

A hospital's MAC address here must match the `mac=` given to its host
in topology/hospital_net.py — the controller keys CRITICAL flow
priority by source MAC, and the backend needs to know which MAC to
mark critical when the Adaptive Sync Engine flags an update as such.
"""
from __future__ import annotations

HOSPITAL_MACS: dict[str, str] = {
    "hospA": "00:00:00:00:00:01",
    "hospB": "00:00:00:00:00:02",
    "hospC": "00:00:00:00:00:03",
}
