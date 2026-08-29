"""
Launches the CARESync SDN controller apps.

The `os-ken` pip package doesn't ship an `osken-manager` CLI in the
release this project installs, so this replicates the small amount of
startup work that CLI normally does: load the OpenFlow protocol
handler (which opens the OpenFlow listening socket) plus our own apps,
then block until they stop.

Run with:
    python3 controller/run.py

os-ken 4.2.2's default hub ("native", plain threading) is incompatible
with its own AppManager.run_apps: the shutdown path calls `t.kill()` on
each app thread, which only the eventlet-backed hub implements. Under
the native hub this crashes with `AttributeError: 'HubThread' object
has no attribute 'kill'` as soon as run_apps returns (e.g. on an
uncaught exception in any app, or the socket already being bound). Force
the eventlet hub before os_ken.lib.hub is imported (it reads this env
var once, at import time) to avoid it.
"""
from __future__ import annotations

import os

os.environ.setdefault("OSKEN_HUB_TYPE", "eventlet")

from os_ken.base.app_manager import AppManager  # noqa: E402

APPS = [
    "os_ken.controller.ofp_handler",
    "controller.flow_manager",
    "controller.congestion_monitor",
    "controller.rest_api",
]


def main() -> None:
    AppManager.run_apps(APPS)


if __name__ == "__main__":
    main()
