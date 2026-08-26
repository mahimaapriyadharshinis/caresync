"""
Launches the CARESync SDN controller apps.

The `os-ken` pip package doesn't ship an `osken-manager` CLI in the
release this project installs, so this replicates the small amount of
startup work that CLI normally does: load the OpenFlow protocol
handler (which opens the OpenFlow listening socket) plus our own apps,
then block until they stop.

Run with:
    python3 controller/run.py
"""
from __future__ import annotations

from os_ken.base.app_manager import AppManager

APPS = [
    "os_ken.controller.ofp_handler",
    "controller.flow_manager",
    "controller.congestion_monitor",
]


def main() -> None:
    AppManager.run_apps(APPS)


if __name__ == "__main__":
    main()
