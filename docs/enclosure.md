# Enclosure

One parametric OpenSCAD file,
[`hardware/enclosure/FanCtrl3-enclosure.scad`](../hardware/enclosure/FanCtrl3-enclosure.scad),
produces a base and a lid for each variant. Ready-to-print STL files are in
[`hardware/enclosure/stl/`](../hardware/enclosure/stl/).

| File | Size (X × Y × Z) |
|---|---|
| `FanCtrl3-lite-base.stl` | 77.6 × 66.6 × 27.6 mm |
| `FanCtrl3-lite-lid.stl` | 77.6 × 66.6 × 3.5 mm |
| `FanCtrl3-pro-base.stl` | 95.6 × 79.6 × 22.6 mm |
| `FanCtrl3-pro-lid.stl` | 95.6 × 79.6 × 3.5 mm |

| Lite | Pro |
|---|---|
| ![Lite enclosure preview](../hardware/enclosure/preview/lite-assembly.png) | ![Pro enclosure preview](../hardware/enclosure/preview/pro-assembly.png) |

## Design

- **Free-standing** next to the server: no mounting ears, four shallow pockets
  (Ø 9 × 1 mm) in the floor for 8 × 2 mm self-adhesive rubber feet.
- The board sits on **four 5 mm standoffs** — room for solder joints and the
  perfboard wiring underneath — and is held by **M3 × 8 screws** driven from above
  into Ø 2.6 mm pilot holes (the screw cuts its own thread in PETG).
- The lid is held by **four M3 × 8 screws** in corner bosses that sit outside the
  board outline, so they never collide with components. A 1.5 mm lip centres it.
- Openings: the Pico's micro-USB in the left wall (12 × 8 mm, room for the plug's
  overmould); three 12 × 9 mm openings in the lid above the fan headers (the fan
  plugs go in from the top); a Ø 6 mm entry for the probe cable (front wall on
  Pro, right wall on Lite); a Ø 5 mm window above the Pico's LED; vent slots above
  the 12 V converter.
- Engraved labels on the lid: "FanCtrl3 Pro" / "FanCtrl3 Lite" and the fan
  numbers 1–3.
- 2 mm walls, floor and lid.

8 × M3 × 8 screws per enclosure (4 for the board, 4 for the lid).

## Printing

- **PETG**, no supports, any infill.
- The base prints **bottom down**. The lid STL is already flipped: print it **top
  down** as it comes.
- The probe entry is teardrop-shaped and the top of the USB opening is a 12 mm
  bridge, so neither needs supports.

> [!IMPORTANT]
> **Lite only:** the position of the PC-3 perfboard's mounting holes (3.0 mm from
> the edge, Ø 3.5 mm) was taken from the distributor's product photo, not from a
> drawing. Measure your board with calipers before printing the base; if it
> differs, change `hole_inset` / `hole_d` in the `.scad` file and rebuild.

## Checked

- **Collision test:** the file has a `part="collisions"` mode that intersects the
  enclosure with simplified bodies of every component (heights included). The
  result must be empty, and it is for both variants. The test was checked with a
  deliberately oversized component, which it does report.
- The USB opening lines up with the Pico's socket in both variants.

Assumed, not yet measured on real parts: the height of the electrolytic
capacitors (11–12 mm), the fan headers with a plug inserted (12 mm), the Pico
standing in its sockets on Lite (11 mm above the board), and the position of the
Pico's LED.

## Rebuilding

```bash
hardware/tools/build_enclosure.sh
```

Needs [OpenSCAD](https://openscad.org/) 2024 or newer (Manifold backend). The
Lite component positions come from
[`FanCtrl3-lite-geometry.scad`](../hardware/enclosure/FanCtrl3-lite-geometry.scad),
which `build_lite.sh` generates from the perfboard design — run that first if you
change the Lite layout. See [development.md](development.md).
