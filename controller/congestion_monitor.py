"""
Polls OpenFlow port statistics and turns them into the 0..1 congestion
reading that sync_engine.policy.decide_tier() needs — the "network
congestion" input in the project's PROCESSING box.

Runs as its own os-ken app, launched alongside flow_manager.py:
    osken-manager controller/flow_manager.py controller/congestion_monitor.py
"""
from __future__ import annotations

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib import hub
from os_ken.ofproto import ofproto_v1_3

POLL_INTERVAL_SECONDS = 2
# a monitored switch moving at or above this many bytes/sec (summed
# across its ports) counts as fully congested (congestion == 1.0);
# scaled linearly below that
SATURATION_BYTES_PER_SEC = 5_000_000


class CongestionMonitor(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.datapaths: dict[int, object] = {}
        self._last_bytes: dict[tuple[int, int], int] = {}
        self._congestion: dict[int, float] = {}  # dpid -> 0..1
        self.monitor_thread = hub.spawn(self._monitor)

    def get_congestion(self, dpid: int) -> float:
        """Read the most recent congestion estimate for a switch. Safe
        to call from outside the event loop (e.g. from the FastAPI
        backend via a small REST wrapper)."""
        return self._congestion.get(dpid, 0.0)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev) -> None:
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    def _monitor(self):
        while True:
            for datapath in list(self.datapaths.values()):
                self._request_stats(datapath)
            hub.sleep(POLL_INTERVAL_SECONDS)

    def _request_stats(self, datapath) -> None:
        parser = datapath.ofproto_parser
        datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY))

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev) -> None:
        dpid = ev.msg.datapath.id
        total_rate = 0.0
        for stat in ev.msg.body:
            key = (dpid, stat.port_no)
            current = stat.tx_bytes + stat.rx_bytes
            previous = self._last_bytes.get(key, current)
            total_rate += max(0, current - previous) / POLL_INTERVAL_SECONDS
            self._last_bytes[key] = current

        self._congestion[dpid] = min(1.0, total_rate / SATURATION_BYTES_PER_SEC)
