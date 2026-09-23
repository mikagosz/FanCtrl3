# Changelog

All notable changes to FanCtrl3. Versions follow [Semantic Versioning](https://semver.org/).

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
