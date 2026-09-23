"""FanCtrl3 control logic - no hardware here, runs under MicroPython and CPython.

main.py (on the Pico) and sim/pico_sim.py (on a computer) feed it the clock,
fan speeds, ambient temperature and command lines; it answers with the duty for
each fan and the lines to send back to the host.

Safety rules:
- the curve runs here, not on the host - a host restart does not stop cooling;
- no TEMP for STALE_S seconds -> 100 % (not knowing the CPU is no reason to slow down);
- BYE (clean host shutdown) -> REST_DUTY instead of 100 %;
- ambient (DS18B20) above AMB_WARN / AMB_CRIT raises the fans whatever the host says;
- MIN_DUTY per fan, so a fan never stalls below its starting duty;
- hysteresis + ramp, so the fans do not "pump" every second.

Duty values are percent of fan speed (100 = full). main.py inverts them for the
open-collector / open-drain output.
"""

VERSION = "1.0.2"
NFANS = 3

DEFAULTS = {
    "curve": [[35, 20], [50, 35], [65, 60], [75, 100]],  # CPU degC -> duty %
    "min_duty": [20, 20, 20],     # per fan; measure with `fanctl calibrate`
    "enabled": [1, 1, 1],         # 0 = no fan on that header (no stall alarms)
    "hyst": 3.0,                  # degC the CPU must fall before the fans slow down
    "ramp_up": 10.0,              # % per second
    "ramp_down": 2.0,             # % per second
    "stale_s": 30,                # no TEMP this long -> 100 %
    "start_duty": 60,             # after power-up, before the first TEMP
    "rest_duty": 20,              # after BYE
    "amb_warn": 40.0,             # ambient degC -> at least amb_warn_duty
    "amb_warn_duty": 60,
    "amb_crit": 45.0,             # ambient degC -> 100 %
    "stall_duty": 30,             # a fan this fast with 0 rpm ...
    "stall_s": 5,                 # ... for this long -> ALARM FANn STALL
}

MODES = ("start", "auto", "rest", "failsafe")


def merge_config(saved):
    """Defaults overlaid with a saved config; anything malformed falls back."""
    cfg = {}
    for k, v in DEFAULTS.items():
        cfg[k] = list(v) if isinstance(v, list) else v
    if isinstance(saved, dict):
        for k, v in saved.items():
            if k in cfg and type(v) == type(cfg[k]):
                cfg[k] = v
            elif k in cfg and isinstance(cfg[k], float) and isinstance(v, int):
                cfg[k] = float(v)
    if check_curve(cfg["curve"]):
        cfg["curve"] = [list(p) for p in DEFAULTS["curve"]]
    return cfg


def check_curve(points):
    """None if the curve is usable, otherwise the reason."""
    if not isinstance(points, list) or len(points) < 2:
        return "need at least 2 points"
    last = None
    for p in points:
        if not isinstance(p, list) or len(p) != 2:
            return "point must be t:p"
        t, d = p
        if not (0 <= d <= 100):
            return "duty must be 0..100"
        if last is not None and t <= last:
            return "temperatures must rise"
        last = t
    return None


def curve_duty(points, t):
    if t <= points[0][0]:
        return float(points[0][1])
    for i in range(1, len(points)):
        t0, d0 = points[i - 1]
        t1, d1 = points[i]
        if t <= t1:
            return d0 + (d1 - d0) * (t - t0) / (t1 - t0)
    return 100.0  # above the last point: full speed, whatever the last duty says


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class Controller:
    def __init__(self, cfg=None, now_ms=0):
        self.cfg = merge_config(cfg)
        self.boot_ms = now_ms
        self.last_ms = now_ms
        self.cpu = None          # last CPU temperature from the host
        self.cpu_ms = None       # when it came
        self.t_eff = None        # CPU temperature after hysteresis
        self.rest = False        # BYE received
        self.mode = "start"
        self.manual = [None] * NFANS
        self.duty = [float(self.cfg["start_duty"])] * NFANS
        self.target = list(self.duty)
        self.rpm = [0] * NFANS
        self.amb = None
        self.fault = False
        self.stall_since = [None] * NFANS
        self.stalled = [False] * NFANS
        self.flags = {}          # alarm name -> active
        self.save_requested = False
        self.service_requested = False

    # --- host commands -------------------------------------------------------------
    def command(self, line, now_ms):
        """One command line in, list of reply lines out."""
        parts = line.strip().split()
        if not parts:
            return []
        cmd = parts[0].upper()
        args = parts[1:]
        try:
            if cmd == "PING":
                return ["PONG"]
            if cmd == "VER":
                return ["VER FanCtrl3 " + VERSION]
            if cmd == "TEMP":
                t = float(args[0])
                if not (-20 <= t <= 130):
                    return ["ERR TEMP out of range"]
                self.cpu = t
                self.cpu_ms = now_ms
                self.rest = False
                if self.mode != "auto":
                    self.mode = "auto"  # fans follow at the next step, the status now
                return ["OK"]
            if cmd == "BYE":
                self.rest = True
                self.mode = "rest"  # like TEMP: the status now, the fans at the next step
                return ["OK REST"]
            if cmd in ("STATUS", "STAT"):
                return [self.status(now_ms)]
            if cmd == "SET":
                n = self._fan(args[0])
                if args[1].upper() == "AUTO":
                    self.manual[n] = None
                else:
                    self.manual[n] = clamp(float(args[1]), 0, 100)
                return ["OK"]
            if cmd == "AUTO":
                self.manual = [None] * NFANS
                return ["OK"]
            if cmd == "MIN":
                n = self._fan(args[0])
                self.cfg["min_duty"][n] = int(clamp(float(args[1]), 0, 100))
                return ["OK"]
            if cmd == "ENABLE":
                n = self._fan(args[0])
                self.cfg["enabled"][n] = 1 if args[1] in ("1", "on", "ON") else 0
                return ["OK"]
            if cmd == "CURVE":
                pts = []
                for a in args:
                    t, d = a.split(":")
                    pts.append([float(t), float(d)])
                why = check_curve(pts)
                if why:
                    return ["ERR CURVE " + why]
                self.cfg["curve"] = pts
                return ["OK"]
            if cmd == "SAVE":
                self.save_requested = True
                return ["OK SAVE"]
            if cmd == "CONF":
                return ["CONF " + self.config_json()]
            if cmd == "SERVICE":
                self.service_requested = True
                return ["OK SERVICE"]
        except (IndexError, ValueError):
            return ["ERR ARGS " + cmd]
        return ["ERR UNKNOWN " + cmd]

    def _fan(self, s):
        n = int(s) - 1
        if not 0 <= n < NFANS:
            raise ValueError
        return n

    def config_json(self):
        import json
        return json.dumps(self.cfg)

    # --- once a second ------------------------------------------------------------------
    def tick(self, now_ms, rpm, amb=None, fault=False):
        """Advance the clock; returns alarm/info lines for the host."""
        cfg = self.cfg
        dt = max(0.0, (now_ms - self.last_ms) / 1000.0)
        self.last_ms = now_ms
        self.rpm = list(rpm)
        self.amb = amb
        self.fault = fault
        out = []

        since = self.cpu_ms if self.cpu_ms is not None else self.boot_ms
        stale = (now_ms - since) > cfg["stale_s"] * 1000
        if self.rest:
            mode = "rest"
        elif stale:
            mode = "failsafe"
        elif self.cpu is None:
            mode = "start"
        else:
            mode = "auto"
        self.mode = mode
        out += self._flag("TEMP STALE", mode == "failsafe", "TEMP OK")

        if mode == "auto":
            t = self.cpu
            h = cfg["hyst"]
            if self.t_eff is None or t > self.t_eff:
                self.t_eff = t
            elif t < self.t_eff - h:
                self.t_eff = t + h
            base = curve_duty(cfg["curve"], self.t_eff)
        elif mode == "rest":
            base = float(cfg["rest_duty"])
        elif mode == "start":
            base = float(cfg["start_duty"])
        else:
            base = 100.0

        amb_crit = amb is not None and amb >= cfg["amb_crit"]
        amb_warn = amb is not None and amb >= cfg["amb_warn"]
        out += self._flag("AMB CRIT", amb_crit, "AMB OK")
        out += self._flag("AMB HIGH", amb_warn and not amb_crit, None)
        out += self._flag("FAULT", fault, "FAULT OK")

        for i in range(NFANS):
            want = base if self.manual[i] is None else self.manual[i]
            want = max(want, cfg["min_duty"][i])
            if amb_warn:
                want = max(want, cfg["amb_warn_duty"])
            urgent = mode == "failsafe" or amb_crit
            if urgent:
                want = 100.0
            want = clamp(want, 0.0, 100.0)
            self.target[i] = want
            d = self.duty[i]
            if urgent:  # no ramp on the way to 100 % for safety reasons
                d = want
            elif want > d:
                d = min(want, d + cfg["ramp_up"] * dt)
            else:
                d = max(want, d - cfg["ramp_down"] * dt)
            self.duty[i] = d
            out += self._stall(i, now_ms)
        return out

    def _stall(self, i, now_ms):
        cfg = self.cfg
        if not cfg["enabled"][i]:
            self.stall_since[i] = None
            return self._flag("FAN%d STALL" % (i + 1), False, "FAN%d OK" % (i + 1))
        if self.duty[i] >= cfg["stall_duty"] and self.rpm[i] == 0:
            if self.stall_since[i] is None:
                self.stall_since[i] = now_ms
        else:
            self.stall_since[i] = None
        stalled = (self.stall_since[i] is not None
                   and now_ms - self.stall_since[i] >= cfg["stall_s"] * 1000)
        return self._flag("FAN%d STALL" % (i + 1), stalled, "FAN%d OK" % (i + 1))

    def _flag(self, name, active, clear_msg):
        """Report a condition once when it starts (and once when it ends)."""
        was = self.flags.get(name, False)
        self.flags[name] = active
        if active and not was:
            return ["ALARM " + name]
        if was and not active and clear_msg:
            return ["INFO " + clear_msg]
        return []

    # --- reporting ------------------------------------------------------------------------
    def status(self, now_ms):
        age = "-" if self.cpu_ms is None else "%d" % ((now_ms - self.cpu_ms) // 1000)
        cpu = "-" if self.cpu is None else "%.1f" % self.cpu
        amb = "-" if self.amb is None else "%.1f" % self.amb
        s = "STAT mode=%s cpu=%s age=%s amb=%s fault=%d" % (
            self.mode, cpu, age, amb, 1 if self.fault else 0)
        for i in range(NFANS):
            man = "m" if self.manual[i] is not None else ""
            s += " f%d=%d%s/%d" % (i + 1, round(self.duty[i]), man, self.rpm[i])
        return s
