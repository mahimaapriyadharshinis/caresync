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

HOSPITALS = [
    ("hospA", "10.0.0.1/24"),
    ("hospB", "10.0.0.2/24"),
    ("hospC", "10.0.0.3/24"),
]
AMBULANCES = [
    ("amb1", "10.0.0.11/24"),
    ("amb2", "10.0.0.12/24"),
]


class HospitalTopo(Topo):
    """3 hospitals + 2 ambulances on a single switch."""

    def build(self) -> None:
        switch = self.addSwitch("s1", protocols="OpenFlow13")

        for name, ip in HOSPITALS + AMBULANCES:
            host = self.addHost(name, ip=ip)
            self.addLink(host, switch, cls=TCLink, bw=10)


topos = {"hospital": HospitalTopo}


def run(controller_ip: str = "127.0.0.1", controller_port: int = 6653) -> None:
    setLogLevel("info")

    UserspaceOVSSwitch = partial(OVSSwitch, datapath="user")

    net = Mininet(
        topo=HospitalTopo(),
        switch=UserspaceOVSSwitch,
        controller=None,
        autoSetMacs=True,
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
