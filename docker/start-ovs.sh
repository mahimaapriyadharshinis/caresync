#!/bin/bash
# Brings up Open vSwitch in userspace mode (no kernel module needed —
# see docs/environment-notes.md) and then runs whatever command this
# container was started with.
set -e

mkdir -p /etc/openvswitch /var/run/openvswitch

if [ ! -f /etc/openvswitch/conf.db ]; then
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
fi

if ! pgrep -f ovsdb-server > /dev/null; then
    ovsdb-server --remote=punix:/var/run/openvswitch/db.sock --pidfile --detach --log-file
fi

ovs-vsctl --no-wait init

if ! pgrep -f ovs-vswitchd > /dev/null; then
    ovs-vswitchd --pidfile --detach --log-file unix:/var/run/openvswitch/db.sock
fi

exec "$@"
