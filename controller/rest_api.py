"""
Small REST hook the FastAPI backend uses to tell the controller about
Adaptive Sync Engine decisions — the concrete implementation of the
"SDN CONTROLLER (RYU): Translates engine decisions (WHEN, WHO, WHAT,
HOW) into flow rules" step from the project architecture.

os-ken's own WSGI app support (os_ken.app.wsgi) isn't included in the
pip package this project installs (its own dependencies — eventlet,
WebOb, Routes — are, just not that one module), so this is a small
hand-rolled WSGI app on eventlet.wsgi, run as its own os-ken app so
app_manager starts it alongside flow_manager and congestion_monitor.

Endpoints:
    PUT    /critical/<mac>    mark_critical(mac) on the flow manager
    DELETE /critical/<mac>    clear_critical(mac)
    GET    /critical          list of currently-critical MACs (debug)
    GET    /congestion/<dpid> current congestion reading, 0..1
"""
from __future__ import annotations

import json
import re

import eventlet
from eventlet import wsgi

from os_ken.base import app_manager
from os_ken.lib import hub

LISTEN_PORT = 8080

_CRITICAL_MAC_RE = re.compile(r"^/critical/([0-9A-Fa-f:]+)$")
_CONGESTION_RE = re.compile(r"^/congestion/(\d+)$")


class RestApi(app_manager.OSKenApp):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._server_thread = hub.spawn(self._serve)

    def _serve(self) -> None:
        try:
            listener = eventlet.listen(("0.0.0.0", LISTEN_PORT))
            self.logger.info("REST hook listening on :%d", LISTEN_PORT)
            wsgi.server(listener, self._handle, log_output=False)
        except Exception:
            self.logger.exception("REST hook server crashed")

    def _handle(self, environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ["PATH_INFO"]

        flow_manager = app_manager.lookup_service_brick("FlowManager")
        congestion_monitor = app_manager.lookup_service_brick("CongestionMonitor")

        if path == "/critical" and method == "GET" and flow_manager is not None:
            return self._json(start_response, 200, {"critical_hosts": sorted(flow_manager.critical_hosts)})

        match = _CRITICAL_MAC_RE.match(path)
        if match and flow_manager is not None:
            mac = match.group(1).lower()
            if method == "PUT":
                flow_manager.mark_critical(mac)
                return self._json(start_response, 200, {"mac": mac, "critical": True})
            if method == "DELETE":
                flow_manager.clear_critical(mac)
                return self._json(start_response, 200, {"mac": mac, "critical": False})

        match = _CONGESTION_RE.match(path)
        if match and method == "GET" and congestion_monitor is not None:
            dpid = int(match.group(1))
            value = congestion_monitor.get_congestion(dpid)
            return self._json(start_response, 200, {"dpid": dpid, "congestion": value})

        return self._json(start_response, 404, {"error": "not found"})

    @staticmethod
    def _json(start_response, status_code: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        reason = {200: "OK", 404: "Not Found"}[status_code]
        start_response(f"{status_code} {reason}", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(payload))),
        ])
        return [payload]
