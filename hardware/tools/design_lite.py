"""FanCtrl3 Lite - single source of truth for the perfboard build.

Board: SCI PC-3 (TME PC-3), 72 x 47 mm, 25 x 15 holes on 2.54 mm, single-sided,
four corner holes missing (371 holes; counted on the TME product photo).

Coordinates are holes seen from the COMPONENT side: column 1..25 left to right,
row A..O top to bottom. USB of the Pico faces the left edge, fan headers the
bottom edge, the DS18B20 terminal the right edge - same sides as the Pro board.

Same pinout as Pro, so one firmware:
GP0/GP1 fan 1 PWM/TACH, GP2/GP3 fan 2, GP4/GP5 fan 3, GP6 DS18B20.
GP7 (FAULT) and GP8 (FAN_EN) go to the same current limiter as on Pro: a TPS2553
on a SparkFun BOB-00717 adapter (SOT-23-6 -> DIP-6, 2 x 3 pins, rows 7.62 mm
apart), RILIM 51k -> 465-570 mA. It sits UNDER the Pico (the Pico stands 11 mm up
on its sockets, the adapter is ~5 mm), with flat-mounted resistors. The Pico
itself stays on raw VBUS, only the fan converter is behind the limiter.

PWM output is an NPN open collector, so the logic matches the Pro 2N7002:
GPIO high -> transistor on -> fan PWM pulled low. MCU dead -> base pulled to
GND by 10k -> transistor off -> fan PWM floats high inside the fan -> 100 %.

build(a, lim) places everything for a given set of fan-channel columns and a
limiter block position; gen_lite.py tries the combinations below and keeps the
one needing the fewest insulated wires.
"""

COLS, ROWS = 25, 15
ROW_NAMES = "ABCDEFGHIJKLMNO"
MISSING = {(1, 1), (25, 1), (1, 15), (25, 15)}
PITCH = 2.54
BOARD_W, BOARD_H = 72.0, 47.0
MARGIN_X = (BOARD_W - (COLS - 1) * PITCH) / 2
MARGIN_Y = (BOARD_H - (ROWS - 1) * PITCH) / 2

TITLE = "FanCtrl3 Lite"
REV = "1.0"

# Channel columns tried by gen_lite.py (a = column of the header PWM pin)
CHANNEL_CHOICES = [(3, 4, 5), (8, 9, 10, 11), (14, 15, 16, 17)]
# Minimum header pitch in holes: fan plugs are ~11 mm wide and the lid needs a
# bridge between their openings (6 holes = 15.24 mm)
MIN_PITCH = 6
# Current-limiter block under the Pico: (column, row, rotation) of the adapter pin 1.
# The whole block (pads 5 left .. 8 right of pin 1, rows -0.7 .. +2.7) has to stay
# between the socket rows B and I and inside columns 1..20; turned by 180 degrees
# it grows the other way, hence other rows and columns.
LIMITER_CHOICES = ([(c, r, 0) for c in range(6, 13) for r in (4, 5)]
                   + [(c, r, 180) for c in range(9, 16) for r in (6, 7)])
# Parts this low may sit under the Pico (it stands 11 mm up); the sockets stay free
LOW_KINDS = {"adapter6", "res_flat", "cap_small"}
SOCKET_ZONES = [("rect", 0.46, 1.5, 20.54, 2.5), ("rect", 0.46, 8.5, 20.54, 9.5)]

# Nets wired with insulated wire by design (low current, pads far apart)
INSULATED = {"+3V3", "+12V"}
# Bare GND rail along the bottom row
RAIL = {"GND": [f"O{c}" for c in range(2, 25)]}
# Longest bare wire allowed, as a multiple of the straight distance; beyond
# that an insulated wire is shorter and easier to follow.
MAX_DETOUR = 1.8
# ...but a hop this short (in holes) stays bare even on an INSULATED net
SHORT_BARE = 3


def h(name):
    """'L12' -> (12, 12): column number, row index 1..15."""
    return int(name[1:]), ROW_NAMES.index(name[0]) + 1


def hname(hole):
    c, r = hole
    return f"{ROW_NAMES[r - 1]}{c}"


# ref -> dict(kind, value, tme, pads {pad: (hole, net)}, body, note)
# body: ("rect", x0, y0, x1, y1) or ("circle", cx, cy, r) in hole units
PARTS = {}
PRECONNECTED = []


def part(ref, kind, value, pads, body, tme="", note=""):
    PARTS[ref] = dict(kind=kind, value=value, tme=tme, note=note, body=body,
                      pads={p: (h(hole), net) for p, (hole, net) in pads.items()})


def channel(n, a, rb, rbe, rs, rpu):
    """Fan channel n; header pins on row N from column a:
    a PWM (pin 4), a+1 TACH (3), a+2 +12V (2), a+3 GND (1) - pin 1 on the right.
    GND drops straight onto the rail on row O."""
    col = lambda c, row: f"{row}{c}"
    part(f"J{n}", "fan", f"FAN{n}",
         {"4": (col(a, "N"), f"FAN{n}_PWM"), "3": (col(a + 1, "N"), f"FAN{n}_TACH"),
          "2": (col(a + 2, "N"), "+12V"), "1": (col(a + 3, "N"), "GND")},
         ("rect", a - 0.5, 14 - 0.82, a + 3.5, 14 + 1.55), tme="MX-47053-1000",
         note="pin 1 (GND) on the right")
    # TO-92 flat side facing up (towards the Pico): C, B, E right to left
    part(f"Q{n}", "to92", "BC547B",
         {"C": (col(a, "L"), f"FAN{n}_PWM"), "B": (col(a - 1, "L"), f"B{n}"),
          "E": (col(a - 2, "L"), "GND")},
         ("rect", a - 2.45, 12 - 0.5, a + 0.45, 12 + 0.95), tme="BC547B-DIO",
         note="flat side towards the Pico")
    # standing resistors: the body sits over the first listed pad
    part(f"R{rb}", "res", "4k7", {"1": (col(a - 1, "K"), f"B{n}"),
                                  "2": (col(a - 1, "J"), f"PWM{n}")},
         ("circle", a - 1, 11, 0.47), tme="CF1/4W-4K7", note="base resistor")
    part(f"R{rbe}", "res", "10k", {"1": (col(a - 1, "N"), "GND"),
                                   "2": (col(a - 1, "M"), f"B{n}")},
         ("circle", a - 1, 14, 0.47), tme="CF1/4W-10K", note="base to GND")
    part(f"R{rs}", "res", "10k", {"1": (col(a + 1, "K"), f"TACH{n}"),
                                  "2": (col(a + 1, "L"), f"FAN{n}_TACH")},
         ("circle", a + 1, 11, 0.47), tme="CF1/4W-10K", note="in series with the GPIO")
    part(f"R{rpu}", "res", "4k7", {"1": (col(a + 2, "L"), "+3V3"),
                                   "2": (col(a + 2, "M"), f"FAN{n}_TACH")},
         ("circle", a + 2, 12, 0.47), tme="CF1/4W-4K7",
         note="tach pull-up to 3V3")


def limiter(c, r, rot):
    """TPS2553 on the BOB-00717 adapter + RILIM, pull-ups and input cap, laid out
    around the adapter pin 1 at (c, r); rot 0 or 180 degrees."""
    s = 1 if rot == 0 else -1

    def at(dx, dy):
        return f"{ROW_NAMES[r + s * dy - 1]}{c + s * dx}"

    def box(x0, y0, x1, y1):
        xs = sorted((c + s * x0, c + s * x1))
        ys = sorted((r + s * y0, r + s * y1))
        return ("rect", xs[0], ys[0], xs[1], ys[1])

    # SOT-23-6 pads sit opposite their DIP holes: 1-3 down one side, 4-6 up the other.
    # Adapter board 0.34 x 0.46 in (8.6 x 11.7 mm), rows 0.300 in apart - SparkFun product page.
    part("U3", "adapter6", "TPS2553DBV",
         {"1": (at(0, 0), "VBUS"), "2": (at(0, 1), "GND"), "3": (at(0, 2), "FAN_EN"),
          "4": (at(3, 2), "FAULT"), "5": (at(3, 1), "ILIM"), "6": (at(3, 0), "+5V_FAN")},
         box(-0.8, -0.7, 3.8, 2.7), tme="TPS2553DBVR",
         note="on a SparkFun BOB-00717 adapter, 6 pins cut from a ZL201-20G header; "
              "chip pin 1 = adapter hole 1")
    # AVX SR20: leads 2.54 mm, body 5.08 wide along the leads x 3.175 thick, 5.08 high
    part("C3", "cap_small", "100n", {"1": (at(-2, 0), "VBUS"), "2": (at(-3, 0), "GND")},
         box(-3.5, -0.63, -1.5, 0.63), tme="SR205C104KAR", note="at the IN pin")
    # DIN0207 lying flat: body 6.3 mm long, 2.5 mm thick, leads bent at 10.16 mm
    part("R14", "res_flat", "51k", {"1": (at(4, 1), "ILIM"), "2": (at(8, 1), "GND")},
         box(4.76, 0.51, 7.24, 1.49), tme="CF1/4W-51K", note="limit 465-570 mA")
    part("R15", "res_flat", "10k", {"1": (at(4, 2), "FAULT"), "2": (at(8, 2), "+3V3")},
         box(4.76, 1.51, 7.24, 2.49), tme="CF1/4W-10K", note="FAULT pull-up")
    part("R16", "res_flat", "10k", {"1": (at(-1, 2), "FAN_EN"), "2": (at(-5, 2), "+3V3")},
         box(-4.24, 1.51, -1.76, 2.49), tme="CF1/4W-10K",
         note="EN on by default - a dead Pico does not switch the fans off")


def build(a, lim=(6, 4, 0)):
    """Place all parts; a = (a1, a2, a3) header columns of the fan channels,
    lim = (column, row, rotation) of the current limiter under the Pico."""
    PARTS.clear()
    # all Pico GND pins are one net inside the module
    PRECONNECTED[:] = [["U1.38", "U1.3", "U1.8", "U1.13", "U1.18", "U1.23", "U1.28"]]

    # Raspberry Pi Pico on two 1x20 sockets, USB to the left. Top view:
    # pins 40..21 along row B (40 at column 1), pins 1..20 along row I.
    nets = {40: "VBUS", 38: "GND", 36: "+3V3", 28: "GND", 23: "GND", 18: "GND", 13: "GND",
            1: "PWM1", 2: "TACH1", 3: "GND", 4: "PWM2", 5: "TACH2",
            6: "PWM3", 7: "TACH3", 8: "GND", 9: "DQ", 10: "FAULT", 11: "FAN_EN"}
    pico = {}
    for c in range(1, 21):
        for pin, row in ((41 - c, "B"), (c, "I")):
            pico[str(pin)] = (f"{row}{c}", nets.get(pin, f"NC_U1_{pin}"))
    # 51 x 21 mm module; pins 48.26 x 17.78 mm
    part("U1", "pico", "Raspberry Pi Pico", pico,
         ("rect", 1 - 0.54, 2 - 0.63, 20 + 0.54, 9 + 0.63), tme="SC0915",
         note="in two ZL262-20SG sockets; ZL201-20G headers soldered to the Pico")

    # 5 V -> 12 V: Pololu U3V16F12 lying flat on its 3-pin header, body to the
    # right (13.1 x 8.1 mm, header 1.27 mm from the short edge)
    part("U2", "pololu", "U3V16F12",
         {"VIN": ("F22", "+5V_FAN"), "GND": ("G22", "GND"), "VOUT": ("H22", "+12V")},
         ("rect", 21.5, 5.4, 26.66, 8.6), tme="POLOLU-4945",
         note="module lies flat above the board, overhangs to the right")
    part("C1", "cap", "47u 25V", {"+": ("D22", "+5V_FAN"), "-": ("D23", "GND")},
         ("circle", 22.5, 4, 0.98), tme="CE-47/25PHT-Y", note="converter input")
    part("C2", "cap", "100u 25V", {"+": ("K23", "+12V"), "-": ("K24", "GND")},
         ("circle", 23.5, 11, 1.24), tme="CE-100/25PHT-Y", note="12 V rail")

    # DS18B20 probe: 3-pole screw terminal, wires enter from the right edge
    part("J4", "terminal", "DS18B20",
         {"1": ("M24", "+3V3"), "2": ("N24", "DQ"), "3": ("O24", "GND")},
         ("rect", 22.7, 12.4, 25.3, 15.6), tme="DG308-2.54-03P",
         note="probe: red 3V3, yellow DQ, black GND")
    part("R13", "res", "4k7", {"1": ("N22", "DQ"), "2": ("M22", "+3V3")},
         ("circle", 22, 14, 0.47), tme="CF1/4W-4K7", note="1-Wire pull-up")

    for n, (col_a, refs) in enumerate(zip(a, ((1, 2, 3, 4), (5, 6, 7, 8),
                                               (9, 10, 11, 12))), 1):
        channel(n, col_a, *refs)
    limiter(*lim)
