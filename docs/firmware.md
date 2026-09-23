# FanCtrl3 firmware

FanCtrl3 drives three 4-pin PWM fans from a Raspberry Pi Pico running MicroPython.
The controller is powered over USB and runs the fan curve itself. The host only reports
the CPU temperature over the same USB cable (see [host-proxmox.md](host-proxmox.md)).

> [!NOTE]
> **Status:** the hardware has not been tested yet. The firmware logic and the host daemon
> pass automated tests against a simulator. Hardware testing is coming soon.

## Contents

- [Firmware files](#firmware-files)
- [Installing MicroPython](#installing-micropython)
- [Copying the firmware](#copying-the-firmware)
- [Service access](#service-access)
- [Pinout](#pinout)
- [Control behaviour](#control-behaviour)
- [Serial protocol](#serial-protocol)
- [The STAT line](#the-stat-line)
- [Unsolicited messages](#unsolicited-messages)
- [Configuration and persistence](#configuration-and-persistence)
- [Status LED](#status-led)
- [Watchdog and error handling](#watchdog-and-error-handling)
- [Simulator and tests](#simulator-and-tests)

## Firmware files

| File | Purpose |
|---|---|
| [`firmware/logic.py`](../firmware/logic.py) | All control decisions: modes, fan curve, hysteresis, ramps, alarms, the command protocol and the configuration defaults. It does not access any hardware and runs under both MicroPython and CPython. |
| [`firmware/main.py`](../firmware/main.py) | Hardware layer for the Pico (MicroPython `rp2` port): PWM outputs, tachometer inputs, DS18B20 ambient probe, power-switch fault input, LED, watchdog, USB serial I/O and the configuration file. |
| [`firmware/flash.sh`](../firmware/flash.sh) | Copies `logic.py` and `main.py` onto a Pico that already runs MicroPython. |

The firmware version is `VERSION` in `logic.py`; `VER` reports it. It follows the project version in [CHANGELOG.md](../CHANGELOG.md).

## Installing MicroPython

The firmware needs the standard MicroPython build for the Raspberry Pi Pico.

1. Download the MicroPython UF2 file for the **`RPI_PICO`** board from micropython.org.
2. Hold down the **BOOTSEL** button on the Pico and connect it to your computer over USB.
   Release the button once it is connected.
3. The Pico appears as a USB drive. Copy the UF2 file onto it. The Pico reboots into
   MicroPython when the copy completes.

## Copying the firmware

[`firmware/flash.sh`](../firmware/flash.sh) uses `mpremote` to copy the two firmware files
to the root of the Pico's filesystem and reset the board. It runs the following command
from the `firmware/` directory:

```sh
mpremote connect auto cp logic.py :logic.py + cp main.py :main.py + reset
```

Requirements on the computer used for flashing:

- `mpremote`, installed with `pipx install mpremote` (or `pip install --user mpremote`).
- `zsh`, because `flash.sh` is a zsh script.

To flash a Pico that runs a fresh MicroPython install, connect it and run:

```sh
./firmware/flash.sh
```

After the reset, `main.py` starts automatically and the controller begins in **start** mode.

To update a controller that is already running FanCtrl3, you must first get past its
Ctrl-C protection. See [Service access](#service-access).

> [!IMPORTANT]
> If the controller is connected to a host running the `fanctl` daemon, stop the daemon
> first (`systemctl stop fanctl`). The daemon holds the serial port open. Stopping it
> sends `BYE`, so the controller switches to rest duty.

## Service access

After the service window closes, the firmware ignores Ctrl-C (`micropython.kbd_intr(-1)`).
Without this protection, one stray byte on the serial line could stop the program and
leave the fans without control. You can reach the MicroPython REPL (and therefore
`mpremote`) in two ways:

| Method | How it works |
|---|---|
| **Service window** | For the first **3000 ms** after power-up (`SERVICE_WINDOW_MS`), Ctrl-C still works. During this window the firmware prints the banner `FanCtrl3 <version> start` and waits. The fans run at the start duty. The control loop and the watchdog have not started yet, and commands are not processed. Run `flash.sh` (or any `mpremote` command) right after you connect or reset the board. |
| **`SERVICE` command** | The controller replies `OK SERVICE`, sets all three fans to 100 %, prints `SERVICE: resetting into service mode`, leaves a flag file (`fanctrl3.service`) and resets. The next boot finds the flag, removes it, keeps the fans at 100 %, prints `FanCtrl3 <version> service mode: REPL, fans at 100%, reset to resume` and stays at the MicroPython REPL — **without starting the watchdog**. Send it with `fanctl send SERVICE` from the host. |

The reset is deliberate: the RP2040 watchdog cannot be stopped once it runs, so the
firmware never drops to the REPL from the running control loop. Service mode lasts
until the next reset or power-cycle; `flash.sh` resets the board when it finishes, and
the board then starts normally.

## Pinout

The pinout is the same on the Pro and Lite boards.

| Pico pin | Direction | Function |
|---|---|---|
| GP0 | Output | Fan 1 PWM |
| GP1 | Input, pull-up | Fan 1 tachometer |
| GP2 | Output | Fan 2 PWM |
| GP3 | Input, pull-up | Fan 2 tachometer |
| GP4 | Output | Fan 3 PWM |
| GP5 | Input, pull-up | Fan 3 tachometer |
| GP6 | 1-Wire | DS18B20 ambient temperature probe |
| GP7 | Input, pull-up | TPS2553 `FAULT`, active low (on the Lite board the TPS2553 sits on an adapter) |
| GP8 | Output, driven high | TPS2553 `EN`. Driven high so the fans are powered; the board also pulls it up. |
| `LED` | Output | On-board status LED |

**PWM outputs.** The PWM frequency is 25 kHz. Each output drives an open-collector /
open-drain stage, so the logic is inverted: a high pin turns the transistor on, pulls the
fan's PWM line low and slows the fan. The firmware writes
`duty_u16 = (100 − duty%) × 65535 / 100`. At initialisation every pin is low (transistor
off), so the fans run at full speed until the controller applies the start duty.

**Tachometer inputs.** The firmware counts falling edges in interrupt handlers and
converts them to rpm once per control step, assuming **2 pulses per revolution**:
`rpm = pulses × 60 / 2 / elapsed seconds`.

**Ambient probe.** The DS18B20 is read without blocking. The firmware starts a conversion
and reads the result on a later pass, at least 800 ms after the start. It uses the first
sensor found on the bus. If no sensor is found, it scans again every 30 s. It discards
readings outside the range −40 to 85 °C (both limits excluded), because 85.0 °C is the
sensor's power-on value and not a real reading. After a bus error the firmware clears
the reading and scans for the sensor again. With no working probe, the ambient value is
reported as `-`. Ambient protection is then inactive and no alarm is raised.

## Control behaviour

The control step runs once per second. Duty values are percentages of fan speed
(100 = full speed).

### Modes

At every step the controller selects one mode. The conditions below are checked in
order, and the first one that applies wins.

| Mode | Condition | Base duty |
|---|---|---|
| `rest` | `BYE` received, and no `TEMP` or `HELLO` since | `rest_duty` = **20 %** |
| `failsafe` | No `TEMP` for more than `stale_s` = **30 s** (counted from power-up if no `TEMP` has ever arrived) | **100 %**, applied immediately with no ramp |
| `start` | Power-up, before the first `TEMP` | `start_duty` = **60 %** |
| `auto` | A recent `TEMP` is available | Fan curve, with hysteresis |

Notes:

- The controller stays in `start` mode for at most 30 s. If no `TEMP` arrives by then,
  it switches to `failsafe`.
- `rest` has no timeout. It lasts until the next `TEMP` or `HELLO` arrives and does not
  turn into `failsafe`. Use `BYE` for a planned host shutdown.
- `HELLO` (sent by the host daemon every time it connects) leaves `rest`, forgets the
  last CPU temperature and restarts the stale timer: the controller is in `start` and
  goes to `failsafe` unless a `TEMP` arrives within `stale_s`.
- A valid `TEMP` switches the reported mode to `auto`, and `BYE` to `rest`, at once.
  The fans follow at the next control step.

### Fan curve

The default curve maps the CPU temperature (°C) to a duty (%):

| CPU temperature | Duty |
|---|---|
| 35 °C | 20 % |
| 50 °C | 35 % |
| 65 °C | 60 % |
| 75 °C | 100 % |

- Between two points, the duty is interpolated linearly.
- At or below the first point, the duty equals the first point's duty.
- Above the last point, the duty is **100 %**, whatever duty the last point specifies.

### Hysteresis

`hyst` = **3.0 °C**. The curve is evaluated at an *effective* temperature:

- When the CPU temperature rises above the effective temperature, the effective
  temperature follows it immediately.
- When the CPU temperature falls, the effective temperature stays where it is until the
  CPU is more than 3.0 °C below it. After that it follows the CPU temperature 3.0 °C
  above it.

This stops the fans from speeding up and slowing down every second.

### Target duty for each fan

Each fan's target is calculated every step, in this order:

1. The mode's base duty. If the fan is under manual control (`SET n <duty>`), the manual
   value replaces the base duty.
2. At least the fan's `min_duty` (default **20 %** for each fan). This floor also applies
   to manual values.
3. If the ambient temperature is at or above `amb_warn` = **40.0 °C**, at least
   `amb_warn_duty` = **60 %**.
4. In `failsafe` mode, or if the ambient temperature is at or above `amb_crit` =
   **45.0 °C**: **100 %**.
5. The result is limited to 0–100 %.

The ambient levels have a hysteresis of `amb_hyst` = **1.0 °C**: a level is entered at
its threshold and left only when the temperature falls more than 1.0 °C below it
(below 39.0 °C for the warning level, below 44.0 °C for the critical one). A probe
reading that hovers around a threshold therefore does not make the fans or the alarms
flap.

Manual control therefore never overrides the safety rules in steps 2–4.

### Ramps

The output duty moves toward the target at a limited rate:

| Parameter | Default |
|---|---|
| `ramp_up` | **10 % per second** |
| `ramp_down` | **2 % per second** |

When the target is 100 % because of `failsafe` or critical ambient temperature, the
controller applies it immediately, without a ramp.

### Stall detection

A fan is reported as stalled when all of the following are true:

- the fan header is enabled (`ENABLE n 1`, the default), and
- the fan's actual output duty is at least `stall_duty` = **30 %**, and
- the fan reports **0 rpm** for `stall_s` = **5 s** in a row.

The controller then sends `ALARM FANn STALL`. It sends `INFO FANn OK` when the condition
clears. A stall is reported only; it does not change the duty. Disabled headers never
raise stall alarms, and disabling a header does not switch its PWM output off.

### Power-switch fault

When the TPS2553 `FAULT` input (GP7) is low, the controller sends `ALARM FAULT`. It sends
`INFO FAULT OK` when the input goes high again. The fault is reported only: the `EN`
output stays high and the duty does not change.

## Serial protocol

The controller communicates over USB CDC serial, one text line per command.

- A line ends with LF or CR.
- The command word is not case-sensitive. Arguments are separated by spaces.
- Fan numbers are `1`, `2` or `3`.
- Lines longer than 120 characters are truncated. Empty lines are ignored.
- The controller processes commands only after the [service window](#service-access)
  has closed.

### Commands

| Command | Arguments | Reply | Effect |
|---|---|---|---|
| `PING` | – | `PONG` | Connection test. |
| `VER` | – | `VER FanCtrl3 <version>` | Firmware version. |
| `TEMP <t>` | CPU temperature in °C, −20 to 130 | `OK` | Stores the CPU temperature, resets the stale timer, leaves `rest` and sets the mode to `auto`. |
| `BYE` | – | `OK REST` | Planned host shutdown: `rest` mode (20 %) until the next `TEMP` or `HELLO`. |
| `HELLO` | – | `OK HELLO` | A host daemon connected: leaves `rest`, clears the CPU temperature and restarts the stale timer (`start` mode, then `failsafe` if no `TEMP` follows). |
| `STATUS` or `STAT` | – | `STAT …` | Current state. See [The STAT line](#the-stat-line). |
| `SET <n> <duty>` | fan, duty 0–100 | `OK` | Puts fan *n* under manual control at the given duty. Out-of-range values are clamped to 0–100. |
| `SET <n> AUTO` | fan | `OK` | Returns fan *n* to automatic control. |
| `AUTO` | – | `OK` | Returns all fans to automatic control. |
| `MIN <n> <duty>` | fan, duty 0–100 | `OK` | Sets the minimum duty of fan *n*, clamped to 0–100 and truncated to an integer. |
| `ENABLE <n> <v>` | fan, `1` / `on` / `ON` | `OK` | Enables stall detection for fan *n* when *v* is `1`, `on` or `ON`. Any other value disables it. |
| `CURVE <t:d> <t:d> …` | two or more points | `OK` | Replaces the fan curve. Each point is `temperature:duty`. |
| `SAVE` | – | `OK SAVE` | Writes the current configuration to the Pico's filesystem. |
| `CONF` | – | `CONF {…}` | Current configuration as JSON on a single line. |
| `SERVICE` | – | `OK SERVICE` | Resets the board into service mode. See [Service access](#service-access). |

Changes made with `SET`, `MIN`, `ENABLE` and `CURVE` take effect immediately. Only
`MIN`, `ENABLE` and `CURVE` are part of the configuration that `SAVE` stores. Manual
`SET` values are never saved, so after a reset all fans are under automatic control.

### Error replies

| Reply | Cause |
|---|---|
| `ERR ARGS <CMD>` | A required argument is missing or cannot be parsed, or the fan number is not 1–3. `<CMD>` is the command word in upper case. |
| `ERR UNKNOWN <CMD>` | Unknown command. |
| `ERR TEMP out of range` | `TEMP` value outside −20 to 130 °C. The value is ignored. |
| `ERR CURVE need at least 2 points` | `CURVE` with fewer than two points. |
| `ERR CURVE temperatures must rise` | The point temperatures are not strictly increasing. |
| `ERR CURVE duty must be 0..100` | A point's duty is outside 0–100. |

When `CURVE` is rejected, the existing curve stays in place.

### Examples

```text
> TEMP 54.0
< OK
> SET 2 40
< OK
> CURVE 30:20 45:35 60:60 70:100
< OK
> MIN 4 20
< ERR ARGS MIN
> CURVE 50:40 40:60
< ERR CURVE temperatures must rise
> SAVE
< OK SAVE
```

## The STAT line

Example:

```text
STAT mode=auto cpu=54.0 age=3 amb=27.5 fault=0 f1=54/728 f2=54m/728 f3=54/728
```

| Field | Meaning |
|---|---|
| `mode` | `start`, `auto`, `rest` or `failsafe`. Updated at each control step, except that a valid `TEMP` switches it to `auto` and `BYE` to `rest` at once. |
| `cpu` | Last CPU temperature received with `TEMP`, one decimal place. `-` if none has been received. |
| `age` | Whole seconds since the last `TEMP`. `-` if none has been received. |
| `amb` | Ambient temperature from the DS18B20, one decimal place. `-` if there is no valid reading. |
| `fault` | `1` while the TPS2553 `FAULT` input is active, otherwise `0`. |
| `f1`, `f2`, `f3` | `<duty>[m]/<rpm>` for each fan. `duty` is the current output duty in %, rounded to an integer. A trailing `m` means the fan is under manual control (`SET`). `rpm` is the speed measured during the last control step. |

## Unsolicited messages

The controller sends these lines without being asked:

| Message | When |
|---|---|
| `FanCtrl3 <version> start` | At power-up, at the start of the service window. |
| `ALARM TEMP STALE` / `INFO TEMP OK` | Entering / leaving `failsafe`. |
| `ALARM AMB HIGH` | Ambient temperature rises into the warning level (≥ 40.0 °C). |
| `ALARM AMB CRIT` | Ambient temperature rises into the critical level (≥ 45.0 °C). |
| `INFO AMB HIGH` | Ambient temperature falls from the critical level back to the warning level. |
| `INFO AMB OK` | Ambient temperature falls back to normal, or the probe stops giving readings. |
| `ALARM FAULT` / `INFO FAULT OK` | TPS2553 fault input becomes active / inactive. |
| `ALARM FANn STALL` / `INFO FANn OK` | Fan *n* stalls / recovers (see [Stall detection](#stall-detection)). |
| `ERR INTERNAL <error>` | An exception occurred in the main loop (see [Watchdog and error handling](#watchdog-and-error-handling)). |
| `SERVICE: resetting into service mode` | After `SERVICE`, just before the reset. |
| `FanCtrl3 <version> service mode: REPL, fans at 100%, reset to resume` | At the boot after `SERVICE`. |

Each alarm is reported once when the condition starts, and once more (as `INFO`) when
it ends. The ambient messages report every change of level, one line per change.

## Configuration and persistence

The configuration is stored as JSON in **`/fanctrl3.json`** at the root of the Pico's
filesystem.

**At power-up** the controller starts from the defaults below and applies the saved file
over them:

- If the file is missing or cannot be read, the defaults are used.
- Unknown keys are ignored.
- A value of the wrong type is ignored, and the default is kept. An integer is accepted
  where the default is a floating-point number.
- If the saved curve is invalid, the default curve is used.

**`SAVE`** writes the complete current configuration, including every key, to
`/fanctrl3.json.tmp` and then renames it to `/fanctrl3.json`. The main loop performs the
write just after it sends the `OK SAVE` reply. Changes made with `CURVE`, `MIN` and
`ENABLE` are lost at the next reset unless you save them.

**`CONF`** returns the configuration currently in memory. It may differ from the saved
file if you have not saved your changes yet.

### Defaults

| Key | Default | Meaning | Protocol command |
|---|---|---|---|
| `curve` | `[[35, 20], [50, 35], [65, 60], [75, 100]]` | CPU °C → duty % | `CURVE` |
| `min_duty` | `[20, 20, 20]` | Minimum duty for each fan, % (measure with `fanctl calibrate`) | `MIN` |
| `enabled` | `[1, 1, 1]` | 0 = no fan on that header (no stall alarms) | `ENABLE` |
| `hyst` | `3.0` | °C the CPU must fall before the fans slow down | – |
| `ramp_up` | `10.0` | % per second | – |
| `ramp_down` | `2.0` | % per second | – |
| `stale_s` | `30` | Seconds without `TEMP` before `failsafe` | – |
| `start_duty` | `60` | Duty after power-up, before the first `TEMP` | – |
| `rest_duty` | `20` | Duty after `BYE` | – |
| `amb_warn` | `40.0` | Ambient °C at which the duty is at least `amb_warn_duty` | – |
| `amb_warn_duty` | `60` | % | – |
| `amb_crit` | `45.0` | Ambient °C at which the duty is 100 % | – |
| `amb_hyst` | `1.0` | °C below a threshold before its ambient level clears | – |
| `stall_duty` | `30` | Stall check applies at or above this duty, % | – |
| `stall_s` | `5` | Seconds at 0 rpm before `ALARM FANn STALL` | – |

Keys without a protocol command can only be changed in the file. Enter the service
window, copy the file off the Pico, edit it, copy it back and reset the board:

```sh
mpremote connect auto cp :fanctrl3.json fanctrl3.json
# edit fanctrl3.json
mpremote connect auto cp fanctrl3.json :fanctrl3.json + reset
```

If the file does not exist yet, run `fanctl send SAVE` once to create it with the
current values.

## Status LED

The on-board LED shows the current mode. Each pattern repeats every 2 s, except in
`failsafe`.

| Mode | Pattern |
|---|---|
| `auto` | One short flash (60 ms) every 2 s |
| `start`, `rest` | Two short flashes (60 ms each, 200 ms apart) every 2 s |
| `failsafe` | Fast blinking: 125 ms on, 125 ms off |

The LED stays off during the service window.

## Watchdog and error handling

- **Hardware watchdog.** The firmware starts a watchdog with an **8000 ms** timeout when
  the service window closes, and feeds it on every pass of the main loop. If the loop
  hangs, the board resets and starts again in `start` mode.
- **Non-blocking loop.** The firmware polls the serial input with a 20 ms timeout,
  counts tachometer pulses in interrupts and reads the DS18B20 without waiting. The
  control step runs once per second.
- **Exceptions.** An exception inside the main loop never stops the loop. The firmware
  sends `ERR INTERNAL <error>`, sets all fans to 100 % and continues. The next
  successful control step applies the normal duty again.
- **Clock.** The firmware keeps an internal millisecond counter that does not wrap
  around, so timeouts behave the same however long the controller runs.

## Simulator and tests

You can test the control logic and the host software without hardware.

**Simulator.** [`sim/pico_sim.py`](../sim/pico_sim.py) runs the real `firmware/logic.py`
on a pseudo-terminal. It prints the device path, then behaves like the controller: it
reads and writes text lines and runs a control step every second. In the simulator, a
fan turns at 1300 rpm × duty and stops below 18 % duty.

```sh
python3 sim/pico_sim.py [--stale S] [--link PATH] [--state FILE] [--dead N] [--amb T]
```

| Option | Effect |
|---|---|
| `--stale S` | Overrides `stale_s`. |
| `--link PATH` | Creates a symlink to the pseudo-terminal. |
| `--state FILE` | Rewrites the state as JSON every step. |
| `--dead N` | Fan *N* never turns. The option can be repeated. |
| `--amb T` | Simulated ambient temperature. |

To point the host tool at the simulator, pass the link as its device, for example
`host/fanctl --device PATH status`.

**Tests.** [`tests/run_all.sh`](../tests/run_all.sh) runs every test that does not need
hardware. It needs `zsh`, `python3` and the unix port of MicroPython (`micropython`).

| Test | What it covers |
|---|---|
| `python3 tests/test_logic.py` | Control logic under CPython |
| `micropython tests/test_logic.py` | The same tests under MicroPython |
| `tests/test_main_smoke.sh` | Runs `firmware/main.py` under unix MicroPython with a stub `machine` module ([`tests/stubs/machine.py`](../tests/stubs/machine.py)) |
| `python3 tests/test_e2e.py` | End-to-end test: simulator, `fanctl` daemon and `fanctl` commands. Takes about a minute. |
