#!/usr/bin/env python3
"""Unit tests for host/fanctl that need neither a controller nor the simulator:

    python3 tests/test_host.py

CPU sensor discovery on fake hwmon trees, CLI error messages, and a daemon that
must not hang on a silent socket client.
"""
import importlib.machinery
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FANCTL = os.path.join(ROOT, "host", "fanctl")
_loader = importlib.machinery.SourceFileLoader("fanctl", FANCTL)
_spec = importlib.util.spec_from_loader("fanctl", _loader)
F = importlib.util.module_from_spec(_spec)
_loader.exec_module(F)

tmp = tempfile.mkdtemp(prefix="fanctl-host-")


def hwmon(devices):
    """{"hwmon0": ("k10temp", {"Tctl": 51.0, None: 40.0}), ...} -> a fake hwmon root.
    A None label writes temp*_input without temp*_label."""
    root = tempfile.mkdtemp(dir=tmp)
    for dev, (name, temps) in devices.items():
        d = os.path.join(root, dev)
        os.makedirs(d)
        with open(os.path.join(d, "name"), "w") as f:
            f.write(name + "\n")
        for i, (label, t) in enumerate(temps.items(), 1):
            with open(os.path.join(d, "temp%d_input" % i), "w") as f:
                f.write("%d\n" % int(t * 1000))
            if label is not None:
                with open(os.path.join(d, "temp%d_label" % i), "w") as f:
                    f.write(label + "\n")
    return root


def test_intel_package():
    root = hwmon({"hwmon0": ("acpitz", {None: 99.0}),
                  "hwmon2": ("coretemp", {"Package id 0": 52.0, "Core 0": 60.0})})
    assert F.cpu_temp(root) == (52.0, "coretemp Package id 0")


def test_intel_two_packages_hottest_wins():
    root = hwmon({"hwmon1": ("coretemp", {"Package id 0": 48.0, "Core 0": 70.0}),
                  "hwmon2": ("coretemp", {"Package id 1": 63.0, "Core 0": 50.0})})
    assert F.cpu_temp(root) == (63.0, "coretemp Package id 0, coretemp Package id 1")


def test_intel_without_package_label_hottest_core():
    root = hwmon({"hwmon1": ("coretemp", {"Core 0": 41.0, "Core 1": 44.0})})
    assert F.cpu_temp(root) == (44.0, "coretemp hottest sensor")


def test_amd_tctl():
    root = hwmon({"hwmon0": ("nvme", {"Composite": 80.0}),
                  "hwmon3": ("k10temp", {"Tctl": 55.5, "Tccd1": 58.0})})
    assert F.cpu_temp(root) == (55.5, "k10temp Tctl")


def test_amd_tdie_preferred_over_offset_tctl():
    root = hwmon({"hwmon3": ("k10temp", {"Tctl": 72.0, "Tdie": 45.0})})
    assert F.cpu_temp(root) == (45.0, "k10temp Tdie")


def test_amd_zenpower():
    root = hwmon({"hwmon4": ("zenpower", {"Tdie": 47.0, "Tctl": 47.0})})
    assert F.cpu_temp(root) == (47.0, "zenpower Tdie")


def test_no_cpu_sensor():
    root = hwmon({"hwmon0": ("acpitz", {None: 40.0}), "hwmon1": ("nvme", {"Composite": 35.0})})
    assert F.cpu_temp(root) == (None, None)
    assert F.cpu_temp(os.path.join(tmp, "does-not-exist")) == (None, None)


def fanctl(*a):
    r = subprocess.run([sys.executable, FANCTL, "--device", os.path.join(tmp, "no-such-tty"),
                        "--socket", os.path.join(tmp, "no-such.sock"), "--reply-timeout", "0.3",
                        *a], capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout + r.stderr


def test_missing_device_is_a_message_not_a_traceback():
    for cmd in (["send", "PING"], ["status"]):
        code, out = fanctl(*cmd)
        assert code != 0, (cmd, out)
        assert "Traceback" not in out and "cannot open" in out, (cmd, out)


def test_send_without_reply_says_so():
    import pty
    master, slave = pty.openpty()      # a "device" that never answers
    link = os.path.join(tmp, "silent-tty")
    os.symlink(os.ttyname(slave), link)
    try:
        r = subprocess.run([sys.executable, FANCTL, "--device", link,
                            "--socket", os.path.join(tmp, "no-such.sock"),
                            "--reply-timeout", "0.3", "send", "PING"],
                           capture_output=True, text=True, timeout=30)
    finally:
        os.close(master)
        os.close(slave)
    out = r.stdout + r.stderr
    assert r.returncode != 0 and "no reply from the controller" in out, out
    assert "None" not in out, out


def test_silent_socket_client_does_not_block_the_daemon():
    d = F.Daemon(SimpleNamespace(reply_timeout=0.3))
    a, b = socket.socketpair()
    t0 = time.monotonic()
    th = threading.Thread(target=d.serve_client, args=(a,))
    th.start()
    th.join(5)
    assert not th.is_alive(), "serve_client still waiting for a silent client"
    assert time.monotonic() - t0 < 3
    b.close()


def main():
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("ok   ", name)
        except Exception as e:
            failed += 1
            print("FAIL ", name, repr(e))
    shutil.rmtree(tmp, ignore_errors=True)
    print("%d tests, %d failed" % (len(tests), failed))
    sys.exit(1 if failed else 0)


main()
