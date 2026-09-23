# Building FanCtrl3 Lite

The Lite variant is built from ready-made modules on a 72 × 47 mm perfboard (SCI
PC-3). Everything is through-hole except the TPS2553 current limiter, which comes
on a small SOT-23 → DIP adapter.

> [!NOTE]
> Not built and tested yet — hardware testing is coming soon. The layout below
> passes an automatic check (every net connected, no hole shared by two nets, no
> wire through a foreign pad, no overlapping parts), but it has not been soldered.

## What you need

- the parts from the [bill of materials](bill-of-materials.md#fanctrl3-lite--modules-on-a-perfboard);
- a soldering iron with a fine tip, thin solder, flux, a multimeter;
- side cutters and a wire stripper;
- the two build documents, generated from the same design:

| Document | What it shows |
|---|---|
| [`FanCtrl3-Lite-perfboard.svg`](../hardware/lite/FanCtrl3-Lite-perfboard.svg) | the component side, and the solder side **mirrored** — the way you see it when you turn the board over — with every wire drawn |
| [`FanCtrl3-Lite-wiring.md`](../hardware/lite/FanCtrl3-Lite-wiring.md) | every part with its holes, every net, every bare wire run and every insulated wire, hole by hole |
| [`FanCtrl3-Lite-schematic.pdf`](../hardware/lite/FanCtrl3-Lite-schematic.pdf) | the circuit |

![Lite perfboard: component side and mirrored solder side](../hardware/lite/FanCtrl3-Lite-perfboard.svg)

## How holes are named

Holes are counted **from the component side**: columns **1–25** from the left,
rows **A–O** from the top, e.g. `E8`. The PC-3 prints its column numbers on the
copper side, so there they run from the right — go by the drawing, not by the
print. Positions A1, A25, O1 and O25 do not exist; the mounting holes are there.

## Wiring

- **Bare wire** runs on the solder side from hole to hole along the grid. Use a
  wire from the MIKROE-2022 kit with its insulation stripped completely; for short
  bridges between neighbouring holes, cut-off resistor leads are enough.
- **Ground** is a bare rail along row O.
- **W wires** (W1, W2, …) are insulated wires on the solder side, soldered straight
  to the pads. They may cross bare wires. 3.3 V and 12 V always use insulated wire.
- The current layout has 44 bare runs (170 steps of 2.54 mm) and 15 insulated
  wires.

## Assembly order

1. **Prepare the current limiter.** Solder the TPS2553DBVR onto the SparkFun
   BOB-00717 adapter so that the chip's **pin 1 lands on adapter hole 1**. Solder
   six header pins (cut from a ZL201-20G strip) into the adapter.
2. **Parts under the Pico first** — they are not reachable once the sockets are in:
   U3 (the adapter, pin 1 at **E8**), C3, and the three resistors that **lie flat**:
   R14 (51 kΩ), R15 and R16 (10 kΩ). Bend their leads at 10.16 mm (4 holes).
   Hold the adapter against its holes before you solder it.
3. **The two Pico sockets** (ZL262-20SG) along rows B and I, columns 1–20 —
   without the Pico.
4. **Standing resistors and transistors.** BC547B with the **flat side towards the
   Pico**, pins C-B-E as in the table.
5. **Connectors:** the three fan headers (pin 1 = GND on the right) and the probe
   terminal.
6. **Capacitors** — mind the polarity of C1 and C2.
7. **The Pololu module** last: it lies flat above the board on its 3-pin header and
   overhangs to the right.
8. **Wiring on the solder side**, net by net, following the tables.
9. **Headers onto the Pico** (two ZL201-20G strips).

## Before you plug in the Pico

> [!IMPORTANT]
> With the Pico **out** of its sockets, check with a multimeter:
> 1. no short between **VBUS (B1)** and **GND (B3)**;
> 2. no short between the **limited 5 V (D22)** and **GND (D23)**;
> 3. no short between **12 V** (K23) and **GND** (K24).
>
> Then plug in the Pico and connect USB. All three fans start at **100 %** until
> the firmware takes over — that is the fail-safe default, not a fault.

Next: [flash the firmware](firmware.md), then [install the host side](host-proxmox.md).

## Regenerating the layout

The perfboard layout, the wiring, the checks, both documents and the enclosure
geometry come from [`hardware/tools/design_lite.py`](../hardware/tools/design_lite.py):

```bash
hardware/tools/build_lite.sh
```

It tries 280 placements of the fan channels and the limiter block, routes each,
and keeps the one with the fewest insulated wires. See
[development.md](development.md).
