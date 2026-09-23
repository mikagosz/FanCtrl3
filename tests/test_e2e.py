#!/usr/bin/env python3
"""End to end on this computer: sim/pico_sim.py <-> host/fanctl daemon <-> fanctl CLI.

    python3 tests/test_e2e.py

Fake hwmon tree with a coretemp device (and a hotter decoy that must be ignored).
Takes about a minute, mostly the calibration.
"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FANCTL = os.path.join(ROOT, "host", "fanctl")
SIM = os.path.join(ROOT, "sim", "pico_sim.py")
sys.path.insert(0, os.path.join(ROOT, "firmware"))
import logic  # noqa: E402

tmp = tempfile.mkdtemp(prefix="fanctl-e2e-")
link = os.path.join(tmp, "fanctl")
sock = os.path.join(tmp, "fanctl.sock")
state_file = os.path.join(tmp, "state.json")
hw = os.path.join(tmp, "hwmon")
procs = []
results = []


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def set_cpu(c):
    write(os.path.join(hw, "hwmon3", "temp1_input"), str(int(c * 1000)))


no_coretemp = os.path.join(tmp, "hwmon-no-coretemp")
write(os.path.join(no_coretemp, "hwmon0", "name"), "acpitz\n")
write(os.path.join(no_coretemp, "hwmon0", "temp1_input"), "40000\n")
write(os.path.join(hw, "hwmon0", "name"), "acpitz\n")
write(os.path.join(hw, "hwmon0", "temp1_input"), "99000\n")      # decoy
write(os.path.join(hw, "hwmon3", "name"), "coretemp\n")
write(os.path.join(hw, "hwmon3", "temp1_label"), "Package id 0\n")
write(os.path.join(hw, "hwmon3", "temp2_label"), "Core 0\n")
write(os.path.join(hw, "hwmon3", "temp2_input"), "45000\n")
set_cpu(38)


def fanctl(*a, timeout=120):
    try:
        r = subprocess.run([sys.executable, FANCTL, "--device", link, "--socket", sock, *a],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "TIMEOUT after %d s" % timeout
    return r.stdout + r.stderr


def start_daemon(hwmon=None):
    logf = open(os.path.join(tmp, "daemon.log"), "a")
    p = subprocess.Popen([sys.executable, FANCTL, "--device", link, "--socket", sock,
                          "daemon", "--interval", "1", "--hwmon", hwmon or hw],
                         stdout=logf, stderr=subprocess.STDOUT)
    procs.append(p)
    return p


def state():
    with open(state_file) as f:
        return json.load(f)


def check(name, ok, detail=""):
    results.append(ok)
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else "  <- " + str(detail)), flush=True)


def wait_for(pred, seconds):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if pred():
                return True
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.25)
    return False


try:
    # 1. daemon first, controller plugged in later
    d = start_daemon()
    time.sleep(1.5)
    log = open(os.path.join(tmp, "daemon.log")).read()
    check("daemon waits for a missing device without crashing",
          d.poll() is None and "no controller" in log, log)

    sim = subprocess.Popen([sys.executable, SIM, "--stale", "4", "--link", link, "--dead", "3",
                            "--state", state_file], stdout=subprocess.PIPE, text=True)
    procs.append(sim)
    sim.stdout.readline()
    check("daemon picks up the controller and sends coretemp (not the 99 °C decoy)",
          wait_for(lambda: state()["mode"] == "auto" and state()["cpu"] == 38.0, 6),
          open(state_file).read() if os.path.exists(state_file) else "no state")

    out = fanctl("status")
    check("fanctl status through the daemon", "curve" in out and "38.0" in out, out)
    check("fanctl send PING", fanctl("send", "PING").strip() == "PONG")

    # 2. hot CPU: fans follow the curve (ramp 10 %/s)
    set_cpu(70)
    want = logic.curve_duty(logic.DEFAULTS["curve"], 70)
    check("CPU 70 °C -> fans on the curve (%.0f%%)" % want,
          wait_for(lambda: abs(state()["duty"][0] - want) < 0.5, 12), state())

    # 3. calibration: the simulated fans stop below 18 % -> lowest working 20 % -> MIN 25
    out = fanctl("calibrate", "1", "--settle", "3", timeout=200)
    ok = wait_for(lambda: state()["min_duty"][0] == 25 and state()["saved"], 3)
    check("calibrate: fan 1 MIN = 25%% and saved (%s)" % state()["min_duty"], ok, out)

    # 3b. a fan that never turns: nothing measured -> old MIN kept, nothing saved
    saves = state()["saves"]
    out = fanctl("calibrate", "3", "--settle", "1", timeout=200)
    check("calibrate a dead fan: MIN kept, no SAVE",
          "does not spin" in out and "nothing saved" in out
          and wait_for(lambda: state()["min_duty"][2] == 20, 3)
          and state()["saves"] == saves, (out, state()))

    # 4. clean stop -> BYE -> rest 20 %
    d.send_signal(signal.SIGTERM)
    d.wait(10)
    log = open(os.path.join(tmp, "daemon.log")).read()
    check("SIGTERM -> BYE -> rest", wait_for(lambda: state()["mode"] == "rest", 3)
          and "BYE -> OK REST" in log, log[-400:])
    time.sleep(5)  # longer than stale_s: rest must NOT turn into failsafe
    check("rest does not turn into failsafe", state()["mode"] == "rest", state())

    # 5. status straight from the port when no daemon runs
    out = fanctl("status")
    check("fanctl status without the daemon (straight from the port)", "rest" in out, out)

    # 5b. daemon restarted on a host without coretemp: HELLO takes the controller
    #     out of rest, so it reaches failsafe instead of resting at 20 % for good
    d = start_daemon(no_coretemp)
    check("daemon without coretemp after BYE -> HELLO -> failsafe, not rest forever",
          wait_for(lambda: state()["mode"] == "failsafe", 10), state())
    d.send_signal(signal.SIGTERM)
    d.wait(10)

    # 6. daemon killed without goodbye -> failsafe after stale_s
    d = start_daemon()
    wait_for(lambda: state()["mode"] == "auto", 5)
    d.kill()
    d.wait(5)
    check("kill -9 of the daemon -> failsafe 100% after 4 s",
          wait_for(lambda: state()["mode"] == "failsafe" and state()["duty"] == [100.0] * 3, 8),
          state())

    # 7. calibrate without the daemon while in failsafe: refuse, change nothing
    saves = state()["saves"]
    out = fanctl("calibrate", "2", "--settle", "1", timeout=30)
    check("calibrate in failsafe refuses and changes nothing",
          "failsafe" in out and "Traceback" not in out
          and wait_for(lambda: state()["min_duty"][1] == 20, 3)
          and state()["saves"] == saves, (out, state()))
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()
            p.wait()

print("%d tests, %d failed  (logs: %s)" % (len(results), results.count(False), tmp))
sys.exit(0 if all(results) else 1)
