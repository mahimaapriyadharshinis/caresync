"""
Thin HTTP client for the SDN controller's REST hook
(controller/rest_api.py) — the network-facing side of "SDN CONTROLLER
(RYU): Translates engine decisions ... into flow rules".

Optional by design: if CONTROLLER_URL isn't set, the backend still runs
standalone — as it does under the test suite and the default
docker-compose stack — with no network coupling to Mininet/the
controller. Point CONTROLLER_URL at the controller's REST port (e.g.
http://<mininet-container-host>:8080) to connect them.
"""
from __future__ import annotations

import os

import httpx

CONTROLLER_URL = os.environ.get("CONTROLLER_URL")


class ControllerClient:
    def __init__(self, base_url: str | None = CONTROLLER_URL, timeout: float = 1.0) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return self._base_url is not None

    def mark_critical(self, mac_address: str) -> None:
        if not self.enabled:
            return
        try:
            httpx.put(f"{self._base_url}/critical/{mac_address}", timeout=self._timeout)
        except httpx.HTTPError:
            pass  # best-effort: an unreachable controller must never block the API response

    def clear_critical(self, mac_address: str) -> None:
        if not self.enabled:
            return
        try:
            httpx.delete(f"{self._base_url}/critical/{mac_address}", timeout=self._timeout)
        except httpx.HTTPError:
            pass
