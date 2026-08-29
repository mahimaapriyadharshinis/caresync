# Environment notes

Two deviations from a literal reading of the proposal's tool list, both
forced by the dev environment (Windows + WSL2 + Docker Desktop), and
both worth explaining in the report/viva rather than leaving silent.

## Ryu → os-ken

The proposal names Ryu as the SDN controller framework. Plain `pip
install ryu` fails on any current Python/pip/setuptools toolchain: Ryu's
setup.py depends on `setuptools.command.easy_install`, which modern
setuptools no longer ships in a usable form. This reproduces on a clean
venv, with build isolation disabled, and with several old setuptools
versions pinned — it's not specific to this machine.

**os-ken** is the actively maintained fork of Ryu (maintained by the
OpenStack project after upstream Ryu went quiet around 2021). Same
architecture, same event-driven `RyuApp` model, same OpenFlow support —
only the import path changes (`os_ken.*` instead of `ryu.*`) and the
manager binary is `osken-manager` instead of `ryu-manager`. Every
"Ryu controller" claim in the proposal — the app_manager model, the
OFPSwitchFeatures/OFPPacketIn event handlers, installing flow rules via
OFPFlowMod — is implemented identically here, just on the maintained
fork.

## Open vSwitch: userspace datapath, not kernel

The WSL2 kernel (`*-microsoft-standard-WSL2`) does not ship the
`openvswitch.ko` kernel module, and it can't be `modprobe`'d in. This
is a property of the WSL2 kernel itself, not of Docker or of any one
container — it reproduces identically whether Open vSwitch is installed
directly on the WSL2 host or inside a container running on top of it.

Open vSwitch has a second mode that doesn't need the kernel module at
all: the **userspace ("netdev") datapath**, where `ovs-vswitchd` does
packet switching itself instead of delegating to a kernel datapath.
That's what this project uses — every switch is instantiated with
`datapath="user"` (see `topology/hospital_net.py`). Functionally
equivalent for this project's purposes (OpenFlow rule installation,
priority-based flow entries); the only real difference is throughput,
which doesn't matter for a class-sized emulated topology.

If you later move this onto a real Linux machine or a proper Linux VM
(not WSL2), the kernel module will be present and `datapath="user"` can
be dropped in favor of the default kernel datapath — nothing else in
the code needs to change.

## os-ken's default hub crashes on shutdown

os-ken 4.2.2 picks its concurrency backend via the `OSKEN_HUB_TYPE` env
var, defaulting to `"native"` (plain `threading`) when unset. That
default is incompatible with os-ken's own `AppManager.run_apps`: its
shutdown path unconditionally calls `t.kill()` on every app thread, but
the native-hub thread wrapper (`os_ken.lib.hub.HubThread`) never defines
`.kill()`. In practice this means the controller crashes with
`AttributeError: 'HubThread' object has no attribute 'kill'` the moment
`run_apps` returns — including on totally unrelated failures, since the
AttributeError masks whatever exception actually triggered shutdown.

`controller/run.py` now sets `OSKEN_HUB_TYPE=eventlet` before importing
`os_ken.base.app_manager` (the var is read once, at import time), which
selects the eventlet-backed hub whose spawned greenthreads do implement
`.kill()`. No config or command-line change needed — just run
`python3 controller/run.py` as documented.
