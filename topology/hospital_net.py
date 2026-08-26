"""
Mininet topology: 3 hospitals + 2 ambulances on one switch, connected to
a remote SDN controller (controller/flow_manager.py).

This is the project's own Phase 2 milestone: "pingall passes on a
3-hospital Mininet topology."

Run directly (needs root — network namespaces):
    sudo python3 topology/hospital_net.py

The switch is forced to OVS's userspace ("netdev") datapath rather than
the kernel one — see docs/environment-notes.md: the stock WSL2 kernel
this project was developed against doesn't ship the openvswitch.ko
kernel module, and userspace mode needs no kernel module at all.
"""
from __future__ import annotations

from functools import partial

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo

from deployment_config import HOSPITAL_MACS

HOSPITALS = [
    ("hospA", "10.0.0.1/24", HOSPITAL_MACS["hospA"]),
    ("hospB", "10.0.0.2/24", HOSPITAL_MACS["hospB"]),
    ("hospC", "10.0.0.3/24", HOSPITAL_MACS["hospC"]),
]
AMBULANCES = [
    ("amb1", "10.0.0.11/24", "00:00:00:00:00:11"),
    ("amb2", "10.0.0.12/24", "00:00:00:00:00:12"),
]


class HospitalTopo(Topo):
    """3 hospitals + 2 ambulances on a single switch.

    Hosts get explicit MAC addresses (matching deployment_config.py)
    rather than Mininet's auto-assigned ones, so the backend can tell
    the controller "mark this hospital's flow CRITICAL" by a MAC it
    actually knows ahead of time.
    """

    def build(self) -> None:
        switch = self.addSwitch("s1", protocols="OpenFlow13")

        for name, ip, mac in HOSPITALS + AMBULANCES:
            host = self.addHost(name, ip=ip, mac=mac)
            self.addLink(host, switch, cls=TCLink, bw=10)


topos = {"hospital": HospitalTopo}


def run(controller_ip: str = "127.0.0.1", controller_port: int = 6653) -> None:
    setLogLevel("info")

    UserspaceOVSSwitch = partial(OVSSwitch, datapath="user")

    net = Mininet(
        topo=HospitalTopo(),
        switch=UserspaceOVSSwitch,
        controller=None,
        autoSetMacs=False,  # hosts already carry explicit MACs (deployment_config.py)
        link=TCLink,
    )
    net.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)

    net.start()
    print("*** Running pingall")
    loss = net.pingAll()
    print(f"*** pingall packet loss: {loss}%")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    run()
