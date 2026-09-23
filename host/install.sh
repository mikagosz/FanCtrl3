#!/bin/sh
# Installs the FanCtrl3 host side on a Proxmox VE (Debian) host. Run as root.
# Python standard library only - nothing else to install.
set -e
cd "$(dirname "$0")"
install -m 755 fanctl /usr/local/bin/fanctl
install -m 644 99-fanctl.rules /etc/udev/rules.d/99-fanctl.rules
install -m 644 fanctl.service /etc/systemd/system/fanctl.service
udevadm control --reload
udevadm trigger --subsystem-match=tty
systemctl daemon-reload
systemctl enable --now fanctl
sleep 2
systemctl --no-pager status fanctl | head -12
echo
ls -l /dev/fanctl 2>/dev/null || echo "No /dev/fanctl - the controller is not plugged in (the daemon is waiting)."
