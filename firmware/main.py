"""FanCtrl3 firmware for the Raspberry Pi Pico (MicroPython, rp2 port).

Hardware glue only - all decisions are in logic.py.

Pinout (same on Pro and Lite):
  GP0/GP2/GP4  PWM to fan 1/2/3 (25 kHz, inverted: pin high = transistor on = fan slower)
  GP1/GP3/GP5  tach of fan 1/2/3 (2 pulses per revolution)
  GP6          DS18B20 ambient probe (1-Wire)
  GP7          TPS2553 FAULT, active low (both; Lite has the TPS2553 on an adapter)
  GP8          TPS2553 EN - driven high, fans powered (pulled up on the board too)
  LED          status: slow blink = auto, double blink = start/rest, fast = failsafe

Protocol: text lines over USB CDC, see logic.Controller.command.

Nothing blocks: stdin is polled, tach pulses are counted in IRQs, and the control
step runs every second from the main loop.
Ctrl-C from the host is ignored (micropython.kbd_intr(-1)), otherwise one stray
byte would stop the program and freeze the fans. Service access: the first
SERVICE_WINDOW_MS after power-up still accept Ctrl-C (mpremote), or send SERVICE:
the board resets into service mode - fans at 100 %, REPL, no watchdog - until the
next reset. A hardware watchdog restarts the board if the loop ever hangs.
"""
import json
import sys
import time

import machine
import micropython
import select
from machine import PWM, Pin

import logic

# relative to the working directory, which is the filesystem root on the Pico
CONFIG_FILE = "fanctrl3.json"
SERVICE_FLAG = "fanctrl3.service"
SERVICE_WINDOW_MS = 3000
PWM_FREQ = 25000
PWM_PINS = (0, 2, 4)
TACH_PINS = (1, 3, 5)
PULSES_PER_REV = 2
STEP_MS = 1000
DS_CONVERT_MS = 800        # DS18B20 needs 750 ms at 12 bit
DS_RESCAN_MS = 30000

# --- hardware -------------------------------------------------------------------------
pwms = []
for g in PWM_PINS:
    p = PWM(Pin(g))
    p.freq(PWM_FREQ)
    p.duty_u16(0)          # pin low = transistor off = fan at 100 % until we decide
    pwms.append(p)

counts = [0, 0, 0]


def _tach_irq(i):
    def handler(pin):
        counts[i] += 1
    return handler


for i, g in enumerate(TACH_PINS):
    Pin(g, Pin.IN, Pin.PULL_UP).irq(trigger=Pin.IRQ_FALLING, handler=_tach_irq(i))

fault_pin = Pin(7, Pin.IN, Pin.PULL_UP)
en_pin = Pin(8, Pin.OUT, value=1)
led = Pin("LED", Pin.OUT, value=0)


def set_duty(i, pct):
    # open collector / open drain: the fan sees high while our pin is LOW
    pwms[i].duty_u16(int((100.0 - pct) * 65535 / 100))


class Ambient:
    """DS18B20 without blocking: start a conversion, read it on a later step."""

    def __init__(self):
        self.ds = None
        self.rom = None
        self.started = None
        self.value = None
        self.last_scan = None
        try:
            import onewire
            import ds18x20
            self.ds = ds18x20.DS18X20(onewire.OneWire(Pin(6)))
        except Exception:
            self.ds = None

    def poll(self, now):
        if self.ds is None:
            return None
        try:
            if self.rom is None:
                if self.last_scan is None or now - self.last_scan >= DS_RESCAN_MS:
                    self.last_scan = now
                    roms = self.ds.scan()
                    self.rom = roms[0] if roms else None
                return None
            if self.started is None:
                self.ds.convert_temp()
                self.started = now
            elif now - self.started >= DS_CONVERT_MS:
                t = self.ds.read_temp(self.rom)
                self.started = None
                # 85.0 is the power-on value, not a reading
                self.value = t if t is not None and -40 < t < 85 else None
        except Exception:
            self.rom = None
            self.started = None
            self.value = None
        return self.value


# --- config -----------------------------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def save_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f)
    import os
    os.rename(tmp, CONFIG_FILE)


# --- clock without wrap-around --------------------------------------------------------------
_ms = 0
_last_ticks = time.ticks_ms()


def now_ms():
    global _ms, _last_ticks
    t = time.ticks_ms()
    _ms += time.ticks_diff(t, _last_ticks)
    _last_ticks = t
    return _ms


def write(line):
    try:
        sys.stdout.write(line + "\n")
    except Exception:
        pass


def blink(mode, now):
    phase = now % 2000
    if mode == "failsafe":
        on = (now % 250) < 125
    elif mode == "auto":
        on = phase < 60
    else:
        on = phase < 60 or 200 <= phase < 260
    led.value(1 if on else 0)


def service_boot():
    """Boot after SERVICE: fans at 100 %, REPL, no watchdog. True if this is one.

    The RP2040 watchdog cannot be stopped once started, so SERVICE does not drop
    to the REPL from the running program - it leaves a flag and resets instead."""
    import os
    try:
        os.remove(SERVICE_FLAG)
    except OSError:
        return False
    for i in range(logic.NFANS):
        set_duty(i, 100)
    en_pin.value(1)
    led.value(1)
    write("FanCtrl3 %s service mode: REPL, fans at 100%%, reset to resume" % logic.VERSION)
    return True


def main():
    if service_boot():
        return
    ctl = logic.Controller(load_config(), now_ms())
    for i in range(logic.NFANS):
        set_duty(i, ctl.duty[i])
    amb = Ambient()

    # service window: Ctrl-C still works for SERVICE_WINDOW_MS after power-up
    write("FanCtrl3 %s start" % logic.VERSION)
    while now_ms() < SERVICE_WINDOW_MS:
        time.sleep_ms(50)
    micropython.kbd_intr(-1)
    wdt = machine.WDT(timeout=8000)

    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    buf = ""
    next_step = now_ms()
    last_counts_ms = now_ms()

    while True:
        wdt.feed()
        try:
            for _ in poll.poll(20):
                ch = sys.stdin.read(1)
                if ch in ("\n", "\r"):
                    if buf:
                        for line in ctl.command(buf, now_ms()):
                            write(line)
                        buf = ""
                elif len(buf) < 120:
                    buf += ch
            if ctl.save_requested:
                ctl.save_requested = False
                save_config(ctl.cfg)
            if ctl.service_requested:
                for i in range(logic.NFANS):
                    set_duty(i, 100)
                with open(SERVICE_FLAG, "w") as f:
                    f.write("1")
                write("SERVICE: resetting into service mode")
                machine.reset()

            now = now_ms()
            a = amb.poll(now)
            if now >= next_step:
                next_step += STEP_MS
                dt = (now - last_counts_ms) / 1000.0
                last_counts_ms = now
                irq_state = machine.disable_irq()
                c = list(counts)
                for i in range(3):
                    counts[i] = 0
                machine.enable_irq(irq_state)
                rpm = [int(n * 60 / PULSES_PER_REV / dt) if dt > 0 else 0 for n in c]
                for line in ctl.tick(now, rpm, a, fault_pin.value() == 0):
                    write(line)
                for i in range(logic.NFANS):
                    set_duty(i, ctl.duty[i])
            blink(ctl.mode, now)
        except Exception as e:
            # never leave the loop on an error - the fans must keep being driven
            write("ERR INTERNAL %s" % e)
            for i in range(logic.NFANS):
                set_duty(i, 100)


main()
