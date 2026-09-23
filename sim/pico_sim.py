#!/usr/bin/env python3
"""FanCtrl3 on a pseudo-terminal: the real firmware/logic.py with pretend fans.

    python3 sim/pico_sim.py [--stale 30] [--link /tmp/fanctl-sim]

Prints the device path (and makes a symlink if asked), then behaves like the
Pico: text lines in and out, a control step every second. Fans turn at
1300 rpm * duty, and stop below 18 % (a made-up start threshold, so that
`fanctl calibrate` has something to find). `--dead 2` makes fan 2 never turn.
Every step it writes the state as JSON to --state for tests to read.
"""
import argparse
import json
import os
import pty
import select
import sys
import time
import tty

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "firmware"))
import logic  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--stale", type=int, help="stale_s override (s)")
ap.add_argument("--link", help="symlink to the device")
ap.add_argument("--state", help="JSON state file, rewritten every step")
ap.add_argument("--dead", type=int, action="append", default=[], help="fan that never turns")
ap.add_argument("--amb", type=float, help="ambient temperature")
args = ap.parse_args()

master, slave = pty.openpty()
tty.setraw(slave)
path = os.ttyname(slave)
if args.link:
    try:
        os.unlink(args.link)
    except FileNotFoundError:
        pass
    os.symlink(path, args.link)
print(path, flush=True)

cfg = {"stale_s": args.stale} if args.stale else None
t0 = time.monotonic()


def now_ms():
    return int((time.monotonic() - t0) * 1000)


ctl = logic.Controller(cfg, now_ms())
os.write(master, ("FanCtrl3 %s start\n" % logic.VERSION).encode())


def rpm_of(i, duty):
    if (i + 1) in args.dead or duty < 18:
        return 0
    return int(1300 * duty / 100)


buf = b""
saves = 0
next_step = now_ms() + 1000
while True:
    r, _, _ = select.select([master], [], [], 0.05)
    if r:
        try:
            data = os.read(master, 1024)
        except OSError:
            data = b""
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            for out in ctl.command(line.decode(errors="replace"), now_ms()):
                os.write(master, (out + "\n").encode())
            if ctl.save_requested:  # the simulator keeps its config in memory only
                saves += 1
                for out in ctl.saved():
                    os.write(master, (out + "\n").encode())
    if now_ms() >= next_step:
        next_step += 1000
        rpm = [rpm_of(i, d) for i, d in enumerate(ctl.duty)]
        for out in ctl.tick(now_ms(), rpm, args.amb, False):
            os.write(master, (out + "\n").encode())
        if args.state:
            tmp = args.state + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"mode": ctl.mode, "duty": ctl.duty, "cpu": ctl.cpu,
                           "min_duty": ctl.cfg["min_duty"], "saved": saves > 0, "saves": saves}, f)
            os.replace(tmp, args.state)
