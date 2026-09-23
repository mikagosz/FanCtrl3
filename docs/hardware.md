# Hardware design

FanCtrl3 comes in two variants built from the same circuit blocks: **Lite**
(ready-made modules on a perfboard) and **Pro** (everything on a custom PCB). They
share the pinout, so one firmware runs on both.

> [!NOTE]
> The hardware has not been tested yet — hardware testing is coming soon. The
> schematics pass ERC, the Pro PCB passes DRC and schematic parity, and the Lite
> perfboard layout passes its own connectivity check. See the
> [project status](../README.md#project-status).

Schematics: [Pro (PDF)](../hardware/pro/FanCtrl3-Pro-schematic.pdf) ·
[Lite (PDF)](../hardware/lite/FanCtrl3-Lite-schematic.pdf) — also as SVG in
[`docs/images/`](images/).

## Block diagram

```
USB VBUS (5 V) ──┬──────────────────────────────► Pico VBUS (the Pico makes its own 3.3 V)
                 │
                 └─► TPS2553 ─► +5V_FAN ─► 5 V → 12 V boost ─► +12V ─► fan headers J1–J3 (pin 2)
                     │    │
          FAULT → GP7    EN ← GP8 (pulled up: on by default)

Pico GP0/GP2/GP4 ─► NPN / N-MOSFET ─► fan PWM (pin 4, open collector / open drain)
Pico GP1/GP3/GP5 ◄── 10 kΩ ◄──┬── fan tach (pin 3)
                              └── 4.7 kΩ to 3.3 V
Pico GP6 ◄──► DS18B20 probe (1-Wire, 4.7 kΩ pull-up) on a 3-pole screw terminal
```

## Pinout (both variants)

| Pico pin | GPIO | Function |
|---|---|---|
| 1 | GP0 | fan 1 PWM |
| 2 | GP1 | fan 1 tach |
| 4 | GP2 | fan 2 PWM |
| 5 | GP3 | fan 2 tach |
| 6 | GP4 | fan 3 PWM |
| 7 | GP5 | fan 3 tach |
| 9 | GP6 | DS18B20 data (1-Wire) |
| 10 | GP7 | TPS2553 `FAULT` (open drain, active low, 10 kΩ pull-up) |
| 11 | GP8 | TPS2553 `EN` (active high, pulled up) |
| 36 | 3V3 | tach pull-ups, 1-Wire, limiter pull-ups |
| 40 | VBUS | 5 V from the host |
| — | GP25 | on-board LED: status |

Fan header (standard 4-pin PC fan, Molex KK 254): **1** GND · **2** +12 V ·
**3** tach · **4** PWM. The DS18B20 terminal: **1** 3.3 V (red) · **2** DQ (yellow) ·
**3** GND (black).

## Power

### Budget

The controller takes everything from one USB port. A USB 2.0 device — the Pico is
one — may draw **500 mA**. FanCtrl3 is sized for three fans of up to **0.6 W** each:

| | |
|---|---|
| Fans at 100 % | 3 × 0.6 W = 1.8 W at 12 V |
| From 5 V, 85 % converter efficiency | ≈ 2.1 W |
| Pico | ≈ 0.15 W |
| **Total from the port** | **≈ 0.45 A** |

Heavier fans do not fit: the current limiter will hold the fan side at its limit
and report `FAULT`, and the fans will not reach full speed.

### Current limiter — TPS2553

The fan side sits behind a **TI TPS2553** current-limited power switch. The Pico
itself stays on raw VBUS, so it keeps running and can report the problem when the
fans are shorted or overloaded.

- **RILIM = 51 kΩ** → current limit **465–570 mA** (TI datasheet, equation 1).
- **`FAULT`** (open drain, 10 kΩ pull-up to 3.3 V) goes to GP7. The firmware reports
  `ALARM FAULT` / `INFO FAULT OK`. The TPS2553 filters short events such as inrush
  at start-up.
- **`EN`** (active high) is pulled up to 3.3 V, so the fans are powered even
  before the firmware runs and when the Pico is dead. GP8 drives it high.
- 100 nF at the `IN` pin.

On **Pro** the TPS2553 is on the board (SOT-23-6). On **Lite** it sits on a
**SparkFun BOB-00717** SOT-23 → DIP-6 adapter (8.6 × 11.7 mm, rows 7.62 mm apart),
together with C3 and the flat-mounted resistors R14–R16, **under** the Pico — the Pico
stands 11 mm above the perfboard in its sockets and the adapter is about 6 mm tall.

### 12 V

| | Lite | Pro |
|---|---|---|
| Converter | **Pololu U3V16F12** module, fixed 12 V ± 4 % | **TI LM27313** boost, SOT-23-5 |
| Output | 12 V | 12.4 V (divider 91 kΩ / 10 kΩ: 1.23 V × (1 + 91/10)) |
| Parts | 47 µF at the module input (Pololu recommends ≥ 33 µF), 100 µF on the 12 V rail | 10 µH inductor, SS14 Schottky diode, 220 pF feed-forward across the top divider resistor, 2 × 10 µF + 100 µF + 100 nF on the output, 10 µF at the input; `SHDN` pulled up (51 kΩ) |
| Basis | module datasheet | TI's typical 5 V → 12 V / 250 mA application |

A fixed output was chosen on purpose: no trimmer that could drift or be set wrong.
12.4 V is within the normal tolerance of 12 V fans.

## Fan channels

### PWM output

4-pin fans pull their PWM input up internally and expect an **open-collector /
open-drain** driver at **25 kHz**. Pulling the line low slows the fan down.

| | Lite | Pro |
|---|---|---|
| Transistor | BC547B (NPN, TO-92) | 2N7002 (N-MOSFET, SOT-23) |
| Drive | GPIO → 4.7 kΩ → base, 10 kΩ base to GND | GPIO → gate, 100 kΩ gate to GND |

Because the transistor pulls the line low, the logic is **inverted**: GPIO high →
transistor on → fan slower. The firmware takes care of it.

**Fail-safe by construction:** when the Pico is dead, unplugged from its socket or
still booting, the pull-down resistor keeps the transistor off, the fan pulls its
own PWM line high, and the fan runs at **100 %**. The same applies at power-up —
all three fans start at full speed until the firmware takes over.

A BC547 is used on Lite rather than a 2N7000 because a 2N7000 is only marginally
on with 3.3 V at the gate.

### Tachometer

The fan's tach output is an open collector, 2 pulses per revolution. It is pulled
up to **3.3 V with 4.7 kΩ on the fan side** and then goes through **10 kΩ in
series** to the GPIO. The series resistor protects the Pico if a fan (or a wrong
cable) drives the tach line to 12 V. The order matters: with the 10 kΩ first and
the pull-up at the GPIO, the low level would not go below about 2.2 V.

## Ambient temperature

A **DS18B20 probe on a cable** (waterproof version) sticks out of the enclosure
and measures the air in the cabinet, not the heat of the board. It connects to a
3-pole screw terminal — no crimping. 4.7 kΩ pull-up on DQ.

The controller uses it on its own, whatever the host says: from **40 °C** the fans
run at least **60 %**, from **45 °C** at **100 %**.

## Layout notes

### Pro PCB

- 2 layers, 90 × 60 mm, 1.6 mm, four M3 mounting holes in the corners.
- Smallest track 0.25 mm, vias 0.3/0.6 mm, smallest hole 0.3 mm — standard
  capabilities of common low-cost PCB fabs.
- Hand-solderable footprints only: 0805/1206 with "HandSolder" pads, SOT-23, SMA,
  no parts with pads underneath.
- The Pico is soldered flat by its castellated edge; its micro-USB socket overhangs
  the board edge by about 1 mm for the enclosure opening.
- Ground pour on both layers. Power tracks (VBUS, the limited 5 V, the converter
  switch node and 12 V) are 0.4–0.6 mm wide, signals 0.25 mm.

### Lite perfboard

- SCI PC-3: 25 × 15 holes on 2.54 mm, 72 × 47 mm, single-sided, the four corner
  positions are mounting holes (371 holes).
- The Pico sits in two 20-pin sockets along rows B and I, USB to the left. Fan
  headers along the bottom edge, at least 15.24 mm apart so the lid openings do not
  merge. The probe terminal and the Pololu module are on the right.
- Ground is a bare rail along row O. Everything else is bare wire on the solder
  side, plus 15 insulated wires where a bare route would be too long or impossible
  (3.3 V and 12 V are always insulated).
- The layout, the wiring and the checks are generated — see
  [development.md](development.md).
- Wiring table: [`hardware/lite/FanCtrl3-Lite-wiring.md`](../hardware/lite/FanCtrl3-Lite-wiring.md).

## Known limitations

- **Not tested on hardware yet.** Footprints of the Molex header and the screw
  terminal were checked against drawings; the SparkFun adapter dimensions come from
  the SparkFun product page; nothing has been built yet.
- The fans start at 100 % when USB is plugged in, before the firmware runs. That
  is intentional (fail-safe) and stays within the current limit, but it is audible.
- Only fans up to about 0.6 W each fit the USB power budget.
