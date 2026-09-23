# Bill of materials

Everything needed to build one controller, for each variant. Part numbers are
**TME order codes** because TME stocks nearly the whole list in one place and ships
across Europe.

> [!NOTE]
> The shop links are **only a suggestion** of where most of the parts can be bought
> in one order. They are not affiliate links, and nothing here depends on a
> particular shop — any part with the same value, rating and footprint will do.
> Availability and prices change; check the page before you order.

"Qty" is what one controller uses. "Buy" is a sensible order quantity where the
shop sells in packs or where a spare is worth having (small SMD chips are easy to
overheat by hand).

## FanCtrl3 Lite — modules on a perfboard

Through-hole parts and ready-made modules, no custom PCB. Wiring:
[`hardware/lite/FanCtrl3-Lite-wiring.md`](../hardware/lite/FanCtrl3-Lite-wiring.md).

| # | Part | Used for | Ref | Qty | Buy | Order code / link |
|---|---|---|---|---|---|---|
| 1 | Raspberry Pi Pico | microcontroller | U1 | 1 | 1 | [SC0915](https://www.tme.eu/en/details/sc0915/raspberry-pi-embedded/raspberry-pi/raspberry-pi-pico/) |
| 2 | Pololu U3V16F12, fixed 12 V step-up | 5 V → 12 V for the fans | U2 | 1 | 1 | [POLOLU-4945](https://www.tme.eu/en/details/pololu-4945/converter-modules/pololu/12v-step-up-voltage-regulator-u3v16f12/) · [Pololu](https://www.pololu.com/product/4945) |
| 3 | TPS2553DBVR current-limited switch, SOT-23-6 | protects the host USB port, reports overload | U3 | 1 | 2 | [TPS2553DBVR](https://www.tme.eu/en/details/tps2553dbvr/power-switches-integrated-circuits/texas-instruments/) |
| 4 | SparkFun SOT-23 to DIP-6 adapter, BOB-00717 | carries the TPS2553 on the perfboard | U3 | 1 | 1 | [SparkFun](https://www.sparkfun.com/sparkfun-sot23-to-dip-adapter.html) · [Botland](https://botland.store/adapters-smd-dip/1760-adapter-sot23-to-dip-6-pin-sparkfun-bob-00717-5904422369965.html) — not stocked by TME |
| 5 | BC547B NPN transistor, TO-92 | open-collector PWM output | Q1–Q3 | 3 | 5 | [BC547B-DIO](https://www.tme.eu/en/details/bc547b-dio/npn-tht-transistors/diotec-semiconductor/bc547b/) |
| 6 | Resistor 4.7 kΩ, 0.25 W, axial | base resistors, tach and 1-Wire pull-ups | R1, R4, R5, R8, R9, R12, R13 | 7 | 100 | [CF1/4W-4K7](https://www.tme.eu/en/details/cf1_4w-4k7/tht-resistors/sr-passives/) |
| 7 | Resistor 10 kΩ, 0.25 W, axial | base pull-downs, tach series, limiter pull-ups | R2, R3, R6, R7, R10, R11, R15, R16 | 8 | 100 | [CF1/4W-10K](https://www.tme.eu/en/details/cf1_4w-10k/tht-resistors/sr-passives/) |
| 8 | Resistor 51 kΩ, 0.25 W, axial | current limit setting (465–570 mA) | R14 | 1 | 100 | [CF1/4W-51K](https://www.tme.eu/en/details/cf1_4w-51k/tht-resistors/sr-passives/) |
| 9 | Ceramic capacitor 100 nF 50 V X7R, 2.54 mm leads (AVX SR20) | limiter input | C3 | 1 | 1 | [SR205C104KAR](https://www.tme.eu/en/details/sr205c104kar/mlcc-tht-capacitors/kyocera-avx/) |
| 10 | Electrolytic 47 µF 25 V, Ø5 × 11 mm | converter input (Pololu recommends ≥ 33 µF) | C1 | 1 | 20 | [CE-47/25PHT-Y](https://www.tme.eu/en/details/ce-47_25pht-y/tht-electrolytic-capacitors/aishi/ewh1ev470d11ot/) |
| 11 | Electrolytic 100 µF 25 V, Ø6.3 × 11 mm | 12 V rail | C2 | 1 | 20 | [CE-100/25PHT-Y](https://www.tme.eu/en/details/ce-100_25pht-y/tht-electrolytic-capacitors/aishi/ewh1ev101e11ot/) |
| 12 | Molex KK 254 4-pin header 47053-1000 | fan connectors (standard 4-pin PWM) | J1–J3 | 3 | 3 | [MX-47053-1000](https://www.tme.eu/en/details/mx-47053-1000/raster-signal-connectors-2-54mm/molex/47053-1000/) |
| 13 | 3-pole screw terminal, 2.54 mm | DS18B20 probe | J4 | 1 | 2 | [DG308-2.54-03P](https://www.tme.eu/en/details/dg308-2.54-03p/pcb-terminal-blocks/degson-electronics/dg308-2-54-03p-14-00ah/) |
| 14 | DS18B20 waterproof probe on a cable (DFRobot DFR0198) | ambient temperature | — | 1 | 1 | [DF-DFR0198](https://www.tme.eu/en/details/df-dfr0198/environmental-sensors/dfrobot/dfr0198/) |
| 15 | Perfboard SCI PC-3, 72 × 47 mm, single-sided | the board | — | 1 | 2 | [PC-3](https://www.tme.eu/en/details/pc-3/universal-pcbs/sci/) |
| 16 | Pin header 1 × 20, 2.54 mm | soldered to the Pico; 6 pins for the adapter | — | 2 + 6 pins | 10 | [ZL201-20G](https://www.tme.eu/en/details/zl201-20g/pin-headers/connfly/ds1021-1-20sf11-b/) |
| 17 | Socket 1 × 20, 2.54 mm | makes the Pico removable | — | 2 | 2 | [ZL262-20SG](https://www.tme.eu/en/details/zl262-20sg/pin-headers/connfly/ds1023-1-20s21/) |
| 18 | Jumper wire kit, 140 pcs (MIKROE-2022) | insulated and bare wiring on the board | — | 1 | 1 | [MIKROE-2022](https://www.tme.eu/en/details/mikroe-2022/development-kits-accessories/mikroe/) |
| 19 | USB-A to micro-USB cable, 1 m | to the host | — | 1 | 1 | [QOLTEC-50214](https://www.tme.eu/en/details/qoltec-50214/usb-cables-and-adapters/qoltec/50214/) |
| 20 | Self-adhesive rubber foot, 8 × 2 mm | enclosure | — | 4 | 10 | [RF8-2A](https://www.tme.eu/en/details/rf8-2a/feet/fix-fasten/) |
| 21 | Socket-head screw M3 × 8 (DIN 912) | board and lid | — | 8 | 100 | [B3X8/BN612](https://www.tme.eu/en/details/b3x8_bn612/bolts/bossard/1233793/) |

Plus the printed enclosure — see [enclosure.md](enclosure.md).

> [!TIP]
> Use a USB cable that carries data, not a charge-only one. Items 19–21 are
> generic: any data-capable micro-USB cable, any small rubber feet and any M3 × 8
> screws will do.

## FanCtrl3 Pro — custom PCB, hand-soldered

Two-layer PCB (90 × 60 mm), all parts chosen for a soldering iron: 0805/1206
passives, SOT-23 packages, no QFN or exposed pads. The Pico is soldered flat by its
castellated edge. The list below matches the KiCad BOM,
[`hardware/pro/fabrication/FanCtrl3-Pro-BOM.csv`](../hardware/pro/fabrication/FanCtrl3-Pro-BOM.csv).

| # | Part | Used for | Ref | Qty | Buy | Order code / link |
|---|---|---|---|---|---|---|
| 1 | Raspberry Pi Pico | microcontroller | U1 | 1 | 1 | [SC0915](https://www.tme.eu/en/details/sc0915/raspberry-pi-embedded/raspberry-pi/raspberry-pi-pico/) |
| 2 | TPS2553DBVR current-limited switch, SOT-23-6 | protects the host USB port, reports overload | U2 | 1 | 2 | [TPS2553DBVR](https://www.tme.eu/en/details/tps2553dbvr/power-switches-integrated-circuits/texas-instruments/) |
| 3 | LM27313XMF boost converter, SOT-23-5 | 5 V → 12.4 V for the fans | U3 | 1 | 2 | [LM27313XMF/NOPB](https://www.tme.eu/en/details/lm27313xmf_nopb/voltage-regulators-dc-dc-circuits/texas-instruments/) |
| 4 | Inductor 10 µH, 5 × 5 mm | boost converter | L1 | 1 | 5 | [DJNR5040-100-S](https://www.tme.eu/en/details/djnr5040-100-s/inductors/ferrocore/) |
| 5 | Schottky diode SS14, 40 V 1 A, SMA | boost converter | D1 | 1 | 2 | [SS14-FAI](https://www.tme.eu/en/details/ss14-fai/smd-schottky-diodes/onsemi/ss14/) |
| 6 | N-MOSFET 2N7002, SOT-23 | open-drain PWM output | Q1–Q3 | 3 | 5 | [2N7002-DIO](https://www.tme.eu/en/details/2n7002-dio/smd-n-channel-transistors/diotec-semiconductor/2n7002/) |
| 7 | Ceramic 10 µF 25 V X7R, 1206 | converter input and output | C2, C4, C5 | 3 | 5 | [TMK316AB7106KLHT](https://www.tme.eu/en/details/tmk316ab7106klht/mlcc-smd-capacitors/taiyo-yuden/) |
| 8 | Ceramic 100 nF 50 V X7R, 0805 | decoupling | C1, C7 | 2 | 5 | [0805B104K500CT](https://www.tme.eu/en/details/0805b104k500ct/mlcc-smd-capacitors/walsin/) |
| 9 | Ceramic 220 pF 50 V C0G, 0805 | converter feed-forward | C3 | 1 | 2 | [0805N221J500CT](https://www.tme.eu/en/details/0805n221j500ct/mlcc-smd-capacitors/walsin/) |
| 10 | Electrolytic 100 µF 25 V, Ø6.3 × 11 mm | 12 V rail | C6 | 1 | 20 | [CE-100/25PHT-Y](https://www.tme.eu/en/details/ce-100_25pht-y/tht-electrolytic-capacitors/aishi/ewh1ev101e11ot/) |
| 11 | Resistor 10 kΩ 1 %, 0805 | divider (bottom), tach series, FAULT pull-up | R2, R6, R13–R15 | 5 | 100 | [SMD0805-10K-1%](https://www.tme.eu/en/details/smd0805-10k-1%25/smd-resistors/royalohm/0805s8f1002t5e/) |
| 12 | Resistor 4.7 kΩ 1 %, 0805 | tach and 1-Wire pull-ups | R10–R12, R16 | 4 | 100 | [SMD0805-4K7-1%](https://www.tme.eu/en/details/smd0805-4k7-1%25/smd-resistors/royalohm/0805s8f4701t5e/) |
| 13 | Resistor 100 kΩ 1 %, 0805 | gate pull-downs, EN pull-up | R3, R7–R9 | 4 | 100 | [SMD0805-100K-1%](https://www.tme.eu/en/details/smd0805-100k-1%25/smd-resistors/royalohm/0805s8f1003t5e/) |
| 14 | Resistor 91 kΩ 1 %, 0805 | divider (top) → 12.4 V | R5 | 1 | 100 | [SMD0805-91K-1%](https://www.tme.eu/en/details/smd0805-91k-1%25/smd-resistors/royalohm/0805s8f9102t5e/) |
| 15 | Resistor 51 kΩ 1 %, 0805 | current limit, converter shutdown pull-up | R1, R4 | 2 | 100 | [SMD0805-51K-1%](https://www.tme.eu/en/details/smd0805-51k-1%25/smd-resistors/royalohm/0805s8f5102t5e/) |
| 16 | Molex KK 254 4-pin header 47053-1000 | fan connectors | J1–J3 | 3 | 3 | [MX-47053-1000](https://www.tme.eu/en/details/mx-47053-1000/raster-signal-connectors-2-54mm/molex/47053-1000/) |
| 17 | 3-pole screw terminal, 2.54 mm | DS18B20 probe | J4 | 1 | 2 | [DG308-2.54-03P](https://www.tme.eu/en/details/dg308-2.54-03p/pcb-terminal-blocks/degson-electronics/dg308-2-54-03p-14-00ah/) |
| 18 | DS18B20 waterproof probe on a cable | ambient temperature | — | 1 | 1 | [DF-DFR0198](https://www.tme.eu/en/details/df-dfr0198/environmental-sensors/dfrobot/dfr0198/) |
| 19 | USB-A to micro-USB cable, 1 m | to the host | — | 1 | 1 | [QOLTEC-50214](https://www.tme.eu/en/details/qoltec-50214/usb-cables-and-adapters/qoltec/50214/) |
| 20 | Self-adhesive rubber foot, 8 × 2 mm | enclosure | — | 4 | 10 | [RF8-2A](https://www.tme.eu/en/details/rf8-2a/feet/fix-fasten/) |
| 21 | Socket-head screw M3 × 8 (DIN 912) | board and lid | — | 8 | 100 | [B3X8/BN612](https://www.tme.eu/en/details/b3x8_bn612/bolts/bossard/1233793/) |
| 22 | Bare PCB, 2 layers, 1.6 mm, 90 × 60 mm | the board | — | 1 | 5 | any PCB fab — see [build-pro.md](build-pro.md) |

Plus the printed enclosure — see [enclosure.md](enclosure.md).

## Datasheets

| Part | Datasheet |
|---|---|
| Raspberry Pi Pico | [pico-datasheet.pdf](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf) |
| TI TPS2553 | [ti.com/lit/gpn/TPS2553](https://www.ti.com/lit/gpn/TPS2553) |
| TI LM27313 | [ti.com/lit/ds/symlink/lm27313.pdf](https://www.ti.com/lit/ds/symlink/lm27313.pdf) |
| Pololu U3V16F12 | [pololu.com/product/4945](https://www.pololu.com/product/4945) |
| SparkFun BOB-00717 | [schematic (PDF)](https://cdn.sparkfun.com/datasheets/BreakoutBoards/SparkFun_SOT23-DIP-Adapter-v10.pdf) · [design files](https://github.com/sparkfun/SOT23_DIP_Adapter) |
| KYOCERA AVX SkyCap SR | [SR-Series.pdf](https://datasheets.kyocera-avx.com/SR-Series.pdf) |
