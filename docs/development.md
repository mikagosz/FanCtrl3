# Development

The hardware of FanCtrl3 is **generated from code**. Each variant has one design
file that is the single source of truth; KiCad files, the perfboard drawing, the
wiring table, the enclosure geometry and the fabrication outputs are all derived
from it. Edit the design file, run the build script, commit the results.

## Tools

| Tool | Version used | Needed for |
|---|---|---|
| Python | 3.9 or newer (developed on 3.14) | generators, host daemon, tests |
| KiCad | 10 | schematics, PCB, ERC/DRC, Gerbers, renders |
| OpenSCAD | 2024 or newer, Manifold backend (developed on 2026.06) | enclosure |
| MicroPython (unix port) | 1.2x (developed on 1.29) | running the firmware tests |
| mpremote | any recent | copying the firmware to the Pico |
| zsh | any | the build and test scripts (`*.sh`, except `host/install.sh`, which is POSIX sh) |

The scripts use the default macOS install location of KiCad. Elsewhere, point them
at your install:

```bash
export KICAD_CLI=/usr/bin/kicad-cli
export KICAD_PYTHON=/usr/bin/python3          # a Python that can `import pcbnew`
export KICAD_SHARE=/usr/share/kicad           # holds symbols/ and footprints/
```

## Hardware

### Pro — `hardware/tools/design_pro.py`

```bash
hardware/tools/build_pro.sh    # schematic -> ERC -> place -> geom -> route -> finish -> DRC
hardware/tools/export_pro.sh   # Gerbers + drill -> ZIP, BOM CSV, schematic PDF
```

- `gen_sch.py` writes the schematic: every pin gets a short stub with a net label or
  power symbol, so every connection is explicit.
- `gen_pcb.py place` places the footprints and the silkscreen (inside KiCad's
  Python), `gen_pcb.py geom` exports the pad geometry, `router.py` routes the tracks,
  and `gen_pcb.py finish` adds them to the board with GND stitching vias and fills
  the ground zones.
- DRC runs with `--schematic-parity`: the board has to match the schematic.
- The router is not deterministic — each run gives slightly different tracks, each
  passing DRC. **Run `export_pro.sh` right after every `build_pro.sh`.**

### Lite — `hardware/tools/design_lite.py`

```bash
hardware/tools/build_lite.sh   # layout search + routing + checks, SVG, wiring table, enclosure geometry, schematic, ERC, PDF
```

`gen_lite.py` tries every combination of fan-channel columns and limiter
positions (280 placements), routes each with a few random net orders, then gives
the five best many more orders. Bare wire runs hole to hole on the solder side and
never shares a hole with another net; what cannot be routed that way within a
detour limit becomes an insulated wire. The layout with the fewest signal wires,
then the shortest insulated wire, wins. A full run takes about two minutes and
gives the same result every time.

The checker rejects a layout if any net is not connected, a hole carries two nets,
a wire passes a foreign pad, a part sticks out of the board, part bodies overlap,
or a part under the Pico covers its sockets.

Environment variables for quick experiments: `LITE_TRIES_FIRST` (default 20),
`LITE_KEEP` (5), `LITE_TRIES` (120).

Translations: when a file `<lang>/lang_<lang>.py` exists at the repository root,
`build_lite.sh` also writes the drawing and the wiring table in that language into
the same folder. Such local folders are not tracked.

### Enclosure

```bash
hardware/tools/build_enclosure.sh   # 4 STL files, collision check, previews
```

Run `build_lite.sh` first when the Lite layout changed — it writes
`hardware/enclosure/FanCtrl3-lite-geometry.scad`, which the enclosure reads.

## Firmware and host

```bash
tests/run_all.sh
```

| Test | What it covers |
|---|---|
| `tests/test_logic.py` | the control logic, under CPython **and** MicroPython (same file, plain asserts): curve, hysteresis, ramps, stale temperature, BYE/rest, minimum duty, ambient override, stall alarm, FAULT edge, manual mode, protocol errors, config merge |
| `tests/test_main_smoke.sh` | the real `firmware/main.py` under the MicroPython unix port with a stub `machine` module ([`tests/stubs/machine.py`](../tests/stubs/machine.py)): replies to commands, 25 kHz PWM, inverted output, 8 s watchdog |
| `tests/test_e2e.py` | host daemon + CLI against [`sim/pico_sim.py`](../sim/pico_sim.py), a simulated controller on a pseudo-terminal with pretend fans: waiting for the device, picking the right hwmon sensor, curve, `status`, `send`, `calibrate`, clean stop → rest, crash → failsafe |

The simulator is also handy on its own for trying the host side:

```bash
python3 sim/pico_sim.py --link /tmp/fanctl
fanctl --device /tmp/fanctl status
```

## Conventions

- One design file per variant; generated files are committed so that people can
  use them without running anything, but never edited by hand.
- Firmware logic without hardware in `logic.py`, pins and timers in `main.py` —
  everything that can be tested off the board lives in `logic.py`.
- The host side uses the Python standard library only.
