"""
Unit tests for the priority/timeout decisions in controller/flow_manager.py.

FlowManager is an os-ken app that normally only runs against a real
OpenFlow datapath (see docs/environment-notes.md for the live Mininet
verification). What's tested here is the pure decision logic —
mark_critical/clear_critical bookkeeping, and which (priority,
idle_timeout) pair packet_in_handler picks — using a minimal fake
datapath so the test doesn't need a running switch.
"""
from unittest.mock import MagicMock

from controller.flow_manager import (
    CRITICAL_IDLE_TIMEOUT,
    DEFAULT_IDLE_TIMEOUT,
    PRIORITY_CRITICAL,
    PRIORITY_DEFAULT,
    FlowManager,
)


def make_manager() -> FlowManager:
    # OSKenApp.__init__ only needs to not blow up; no live datapath required
    return FlowManager()


def test_mark_and_clear_critical():
    fm = make_manager()
    fm.mark_critical("00:00:00:00:00:01")
    assert "00:00:00:00:00:01" in fm.critical_hosts

    fm.clear_critical("00:00:00:00:00:01")
    assert "00:00:00:00:00:01" not in fm.critical_hosts


def test_clearing_a_host_that_was_never_marked_does_not_raise():
    fm = make_manager()
    fm.clear_critical("00:00:00:00:00:99")  # must not raise


def test_default_flows_get_a_bounded_idle_timeout_not_zero():
    """The proactive-timeout mitigation: ordinary flows must expire on
    their own rather than living forever in the switch's flow table."""
    assert DEFAULT_IDLE_TIMEOUT > 0
    assert CRITICAL_IDLE_TIMEOUT > 0


def test_critical_hosts_get_higher_priority_and_shorter_timeout():
    assert PRIORITY_CRITICAL > PRIORITY_DEFAULT
    assert CRITICAL_IDLE_TIMEOUT < DEFAULT_IDLE_TIMEOUT


def test_packet_in_installs_critical_priority_for_marked_host():
    fm = make_manager()
    fm.mark_critical("aa:aa:aa:aa:aa:aa")

    recorded = {}

    def fake_add_flow(datapath, priority, match, actions, idle_timeout=0, buffer_id=None):
        recorded["priority"] = priority
        recorded["idle_timeout"] = idle_timeout

    fm._add_flow = fake_add_flow

    ev = _fake_packet_in_event(src="aa:aa:aa:aa:aa:aa", dst="bb:bb:bb:bb:bb:bb", dpid=1)
    # prime mac_to_port so dst resolves to a real port, not FLOOD, which
    # is the branch that actually installs a flow
    fm.mac_to_port[1] = {"bb:bb:bb:bb:bb:bb": 2}

    fm.packet_in_handler(ev)

    assert recorded["priority"] == PRIORITY_CRITICAL
    assert recorded["idle_timeout"] == CRITICAL_IDLE_TIMEOUT


def test_packet_in_installs_default_priority_for_unmarked_host():
    fm = make_manager()

    recorded = {}

    def fake_add_flow(datapath, priority, match, actions, idle_timeout=0, buffer_id=None):
        recorded["priority"] = priority
        recorded["idle_timeout"] = idle_timeout

    fm._add_flow = fake_add_flow

    ev = _fake_packet_in_event(src="cc:cc:cc:cc:cc:cc", dst="dd:dd:dd:dd:dd:dd", dpid=1)
    fm.mac_to_port[1] = {"dd:dd:dd:dd:dd:dd": 3}

    fm.packet_in_handler(ev)

    assert recorded["priority"] == PRIORITY_DEFAULT
    assert recorded["idle_timeout"] == DEFAULT_IDLE_TIMEOUT


def _fake_packet_in_event(src: str, dst: str, dpid: int):
    """Builds the minimum fake OFPPacketIn event packet_in_handler
    actually touches: a real Ethernet frame (so os_ken's own packet
    parser works unmodified) wrapped in mocked OpenFlow plumbing."""
    from os_ken.lib.packet import ethernet, ether_types, packet

    pkt = packet.Packet()
    pkt.add_protocol(ethernet.ethernet(dst=dst, src=src, ethertype=ether_types.ETH_TYPE_IP))
    pkt.serialize()

    ofproto = MagicMock()
    ofproto.OFPP_FLOOD = 0xFFFFFFFF
    ofproto.OFPP_CONTROLLER = 0xFFFFFFFD
    ofproto.OFPCML_NO_BUFFER = 0xFFFF
    ofproto.OFP_NO_BUFFER = 0xFFFFFFFF

    datapath = MagicMock()
    datapath.id = dpid
    datapath.ofproto = ofproto
    datapath.ofproto_parser = MagicMock()

    msg = MagicMock()
    msg.datapath = datapath
    msg.data = pkt.data
    msg.match = {"in_port": 1}
    msg.buffer_id = ofproto.OFP_NO_BUFFER  # unbuffered, so packet_in_handler always sends OFPPacketOut too

    ev = MagicMock()
    ev.msg = msg
    return ev
