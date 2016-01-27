#!/usr/bin/env bash

# Since mininet already installs OpenvSwitch, we just need
# to configure and start ovsdb and vswitchd.
modprobe openvswitch
export DB_SOCK=/var/run/openvswitch/db.sock
mkdir -p /var/run/openvswitch/
ovsdb-tool create /etc/openvswitch/conf.db \
	/usr/share/openvswitch/vswitch.ovsschema
ovsdb-server --remote=punix:$DB_SOCK \
	--remote=db:Open_vSwitch,Open_vSwitch,manager_options \
	--pidfile --detach
ovs-vswitchd unix:$DB_SOCK --pidfile \
	--log-file=/var/log/openvswitch/ovs-vswitchd.log \
	--detach
