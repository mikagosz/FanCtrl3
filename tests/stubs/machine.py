"""Stand-in for the rp2 `machine` module, to run firmware/main.py under the unix
MicroPython port (tests/test_main_smoke.sh). Records PWM duty; the watchdog ends
the run after RUN_S seconds and prints what the pins saw."""
import sys
import time

RUN_S = 6
_start = time.ticks_ms()
pwm_log = {}


class Pin:
    IN = 0
    OUT = 1
    PULL_UP = 2
    IRQ_FALLING = 4

    def __init__(self, id, mode=0, pull=None, value=None):
        self.id = id
        self._v = 1 if pull == Pin.PULL_UP else (value or 0)

    def irq(self, trigger=0, handler=None):
        self.handler = handler

    def value(self, v=None):
        if v is None:
            return self._v
        self._v = v


class PWM:
    def __init__(self, pin):
        self.pin = pin

    def freq(self, f):
        pwm_log["freq"] = f

    def duty_u16(self, d):
        pwm_log[self.pin.id] = d


class WDT:
    def __init__(self, timeout=0):
        pwm_log["wdt"] = timeout

    def feed(self):
        if time.ticks_diff(time.ticks_ms(), _start) > RUN_S * 1000:
            pins = sorted((k, v) for k, v in pwm_log.items() if isinstance(k, int))
            sys.stdout.write("END freq=%s wdt=%s pwm=%s\n"
                             % (pwm_log.get("freq"), pwm_log.get("wdt"), pins))
            raise SystemExit


def disable_irq():
    return 0


def enable_irq(s):
    pass
