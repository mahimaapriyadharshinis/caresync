"""
CARESync SDN controller — the "SDN CONTROLLER (RYU)" box in the project
architecture.

Built on os-ken, the actively maintained fork of the Ryu SDN framework
(see docs/ryu-vs-osken.md for why plain `ryu` was dropped). Starts as a
standard L2 learning switch so basic connectivity (`pingall`) works
immediately, and layers priority-aware flow installation on top: when
the Adaptive Sync Engine marks a hospital's update CRITICAL, that
host's traffic gets a high-priority, short-idle-timeout OpenFlow rule
instead of the default low-priority one, so it doesn't sit queued
behind routine traffic.

Run alongside congestion_monitor.py:
    osken-manager controller/flow_manager.py controller/congestion_monitor.py
"""
from __future__ import annotations

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from os_ken.lib.packet import ethernet, ether_types, packet
from os_ken.ofproto import ofproto_v1_3

# Flow priorities — higher wins. ROUTINE and CONGESTED updates both
# result in ordinary learning-switch flows; CRITICAL gets a dedicated
# high-priority rule with a short idle timeout, so it doesn't linger
# once the surge that earned it has passed.
PRIORITY_DEFAULT = 1
PRIORITY_CRITICAL = 100
CRITICAL_IDLE_TIMEOUT = 5


class FlowManager(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.mac_to_port: dict[int, dict[str, int]] = {}
        # populated by the Adaptive Sync Engine (via mark_critical, or
        # the REST hook wired up alongside congestion_monitor.py) when
        # an update is scored CRITICAL
        self.critical_hosts: set[str] = set()

    def mark_critical(self, mac_address: str) -> None:
        """Flag a host's next flow as CRITICAL priority."""
        self.critical_hosts.add(mac_address)

    def clear_critical(self, mac_address: str) -> None:
        self.critical_hosts.discard(mac_address)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev) -> None:
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # table-miss flow: send anything unmatched up to the controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)
        self.logger.info("switch connected: dpid=%s", datapath.id)

    def _add_flow(self, datapath, priority, match, actions, idle_timeout=0, buffer_id=None) -> None:
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        kwargs = dict(datapath=datapath, priority=priority, idle_timeout=idle_timeout, match=match, instructions=inst)
        if buffer_id is not None:
            kwargs["buffer_id"] = buffer_id
        datapath.send_msg(parser.OFPFlowMod(**kwargs))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev) -> None:
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        dpid = datapath.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst, src = eth.dst, eth.src
        in_port = msg.match["in_port"]

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            priority = PRIORITY_CRITICAL if src in self.critical_hosts else PRIORITY_DEFAULT
            idle_timeout = CRITICAL_IDLE_TIMEOUT if priority == PRIORITY_CRITICAL else 0
            buffer_id = msg.buffer_id if msg.buffer_id != ofproto.OFP_NO_BUFFER else None
            self._add_flow(datapath, priority, match, actions, idle_timeout, buffer_id)
            if buffer_id is not None:
                return

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data,
        )
        datapath.send_msg(out)
