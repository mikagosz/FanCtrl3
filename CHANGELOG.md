# Changelog

All notable changes to FanCtrl3. Versions follow [Semantic Versioning](https://semver.org/).

## [1.0.6] — 2026-09-23

### Fixed
- `SAVE` replied `OK SAVE` before the file was written, so a failed write
  looked like a success (it only showed up as `ERR INTERNAL`). The reply now
  comes after the write: `OK SAVE`, or `ERR SAVE <reason>`.

## [1.0.5] — 2026-09-23

### Fixed
- A saved configuration with `min_duty` or `enabled` of the wrong length (or with
  non-numeric entries) crashed the control step. Such values are now ignored and
  the default is kept.

## [1.0.4] — 2026-09-23

### Fixed
- Ambient alarms: falling from the critical to the warning level sent
  `INFO AMB OK` followed by `ALARM AMB HIGH`, and falling from the warning level
  to normal sent nothing. Every change of level now sends exactly one line
  (`ALARM AMB HIGH`, `ALARM AMB CRIT`, `INFO AMB HIGH`, `INFO AMB OK`).
- The ambient levels have a 1.0 °C hysteresis (`amb_hyst`), so a reading that
  hovers around a threshold no longer makes the fans and the alarms flap.

## [1.0.3] — 2026-09-23

### Fixed
- A daemon restarted on a host without a readable CPU temperature left the fans at
  rest duty (20 %) for good, because the `BYE` of the previous run put the
  controller in rest mode, which has no timeout. The daemon now sends the new
  `HELLO` command whenever it connects: the controller leaves rest and goes to
  failsafe unless a `TEMP` follows.

## [1.0.2] — 2026-09-23

### Fixed
- `STATUS` right after `BYE` reported the previous mode until the next control
  step; it now reports `rest` at once, the same way `TEMP` reports `auto`.

## [1.0.1] — 2026-09-23

### Fixed
- `SERVICE` no longer drops to the REPL with the watchdog still running (the
  RP2040 watchdog cannot be stopped, so the board reset about 8 s later). It now
  resets into a service mode — fans at 100 %, REPL, no watchdog — until the next
  reset.

## [1.0.0] — 2026-09-23

First complete design. **Not yet tested on hardware** — hardware testing is coming soon.

### Hardware
- FanCtrl3 Pro: 2-layer 90 × 60 mm PCB for hand soldering — Raspberry Pi Pico,
  TPS2553 current limiter (465–570 mA), LM27313 5 V → 12.4 V boost, three 2N7002
  open-drain PWM outputs, tach inputs, DS18B20 probe terminal. ERC 0, DRC 0,
  schematic parity 0. Gerbers, drill files and BOM.
- FanCtrl3 Lite: the same circuit from modules on an SCI PC-3 perfboard — Pololu
  U3V16F12, BC547B open-collector outputs, TPS2553 on a SparkFun BOB-00717 adapter
  under the Pico. Generated layout, wiring drawing and wiring table; ERC 0.
- Parametric OpenSCAD enclosure for both variants, STL files, collision check.

### Firmware
- MicroPython for the Pico: 25 kHz PWM, tach on interrupts, DS18B20, fan curve with
  hysteresis and ramping, per-fan minimum duty, failsafe on stale temperature,
  rest on host shutdown, ambient override, stall and overload alarms, hardware
  watchdog, text protocol over USB CDC.

### Host
- `fanctl` for Proxmox VE: daemon feeding the CPU package temperature (coretemp),
  `status`, `send`, `calibrate`; udev rule, systemd unit, installer.

### Tests
- Control logic under CPython and MicroPython, firmware smoke test on stubbed
  hardware, end-to-end test of the host side against a simulated controller.
