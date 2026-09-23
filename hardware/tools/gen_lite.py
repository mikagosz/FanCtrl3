"""Route and draw FanCtrl3 Lite on a PC-3 perfboard.

    python3 gen_lite.py <out_dir>

Reads design_lite.py. Bare wires on the solder side run hole to hole along the
grid and never share a hole with another net; what cannot be routed that way
becomes an insulated wire on the solder side, soldered straight to the pads. Then it checks the result
(every net connected, no hole with two nets, no bodies on top of each other)
and writes:
  <out>/FanCtrl3-Lite-perfboard.svg      component side + solder side (mirrored)
  <out>/FanCtrl3-Lite-wiring.md   connection table and wire list
"""
import heapq
import importlib.util
import itertools
import math
import os
import random
import sys

import design_lite as D

OUT = sys.argv[1]
NAME = "FanCtrl3-Lite"
TRIES_FIRST = int(os.environ.get("LITE_TRIES_FIRST", "20"))  # every placement
KEEP = int(os.environ.get("LITE_KEEP", "5"))                     # best placements ...
TRIES = int(os.environ.get("LITE_TRIES", "120"))                 # ... get this many orders

HOLES = {(c, r) for c in range(1, D.COLS + 1) for r in range(1, D.ROWS + 1)} - D.MISSING
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def fail(msg):
    print("ERROR:", msg)
    sys.exit(1)


def check_placement():
    """Pads on real holes, one pad per hole, bodies apart and on the board."""
    pad_at, net_pads, errors = {}, {}, []
    for ref, p in D.PARTS.items():
        for pad, (hole, net) in p["pads"].items():
            if hole not in HOLES:
                errors.append(f"{ref}.{pad} at {D.hname(hole)} - no such hole")
            elif hole in pad_at:
                errors.append(f"{ref}.{pad} and {pad_at[hole][0]} share hole {D.hname(hole)}")
            pad_at[hole] = (ref, pad, net)
            net_pads.setdefault(net, []).append((ref, pad, hole))
    errors += [f"bodies of {x} and {y} overlap"
               for x, y in itertools.combinations(D.PARTS, 2)
               if not under_pico(x, y) and overlap(D.PARTS[x]["body"], D.PARTS[y]["body"])]
    errors += [f"{ref} sits on a Pico socket"
               for ref, p in D.PARTS.items() if p["kind"] in D.LOW_KINDS
               for z in D.SOCKET_ZONES if overlap(p["body"], z)]
    ex, ey = D.MARGIN_X / D.PITCH, D.MARGIN_Y / D.PITCH
    for ref, p in D.PARTS.items():
        x0, y0, x1, y1 = bbox(p["body"])
        if x0 < 1 - ex or y0 < 1 - ey or x1 > D.COLS + ex or y1 > D.ROWS + ey:
            errors.append(f"{ref} sticks out of the board")
    return pad_at, net_pads, errors


def under_pico(x, y):
    """A low part may sit under the Pico: it stands 11 mm up on its sockets."""
    kinds = {D.PARTS[x]["kind"], D.PARTS[y]["kind"]}
    return "pico" in kinds and bool(kinds & D.LOW_KINDS)


def bbox(b):
    if b[0] == "rect":
        return b[1:]
    _, cx, cy, r = b
    return cx - r, cy - r, cx + r, cy + r


def overlap(a, b):
    if a[0] == b[0] == "circle":
        return math.dist(a[1:3], b[1:3]) < a[3] + b[3]
    ax0, ay0, ax1, ay1 = bbox(a)
    bx0, by0, bx1, by1 = bbox(b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class Layout:
    """Bare wires (solder side, hole to hole) + insulated wires for one placement."""

    def __init__(self, pad_at, net_pads):
        self.pad_at, self.net_pads = pad_at, net_pads
        self.nets = {n for n in net_pads if not n.startswith("NC_")}
        self.owner = {hh: n for hh, (_, _, n) in pad_at.items()}
        self.wires, self.jumpers, self.parent = [], [], {}
        for net, holes in D.RAIL.items():
            self.add_wire(net, [D.h(x) for x in holes])
        for group in D.PRECONNECTED:
            hs = [D.PARTS[r]["pads"][p][0] for r, p in (i.split(".") for i in group)]
            for a, b in zip(hs, hs[1:]):
                self.union(a, b)

    def find(self, x):
        par = self.parent
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)

    def add_wire(self, net, path):
        for a, b in zip(path, path[1:]):
            self.union(a, b)
        for x in path:
            self.owner[x] = net
        self.wires.append((net, path))

    def route(self, net, sources, targets):
        """Dijkstra over holes: one step = 1, a bend costs extra."""
        best, pq = {}, []
        for s in sources:
            for d in DIRS:
                heapq.heappush(pq, (0.0, s, d, None))
        prev = {}
        while pq:
            cost, hole, d, frm = heapq.heappop(pq)
            if best.get((hole, d), 1e9) <= cost:
                continue
            best[(hole, d)] = cost
            prev[(hole, d)] = frm
            if hole in targets:
                path, k = [], (hole, d)
                while k:
                    path.append(k[0])
                    k = prev[k]
                return path[::-1]
            for nd in DIRS:
                nxt = (hole[0] + nd[0], hole[1] + nd[1])
                if nxt not in HOLES or self.owner.get(nxt, net) != net:
                    continue
                step = 1.0 + (0.6 if nd != d else 0.0)
                heapq.heappush(pq, (cost + step, nxt, nd, (hole, d)))
        return None

    def group(self, net, root):
        return [x for x, n in self.owner.items() if n == net and self.find(x) == root]

    def connect(self, net, bare=True):
        pads = [hole for _, _, hole in self.net_pads[net]]
        while len({self.find(x) for x in pads}) > 1:
            root = self.find(pads[0])
            src = self.group(net, root)
            dst = {x for x in pads if self.find(x) != root}
            path = self.route(net, src, dst)
            direct = min(manhattan(a, b) for a in src for b in dst)
            limit = D.MAX_DETOUR * direct + 2 if bare else D.SHORT_BARE
            if path and len(path) - 1 <= limit:
                self.add_wire(net, path)
                continue
            # insulated wire between the closest holes of the two groups
            b0 = min(dst, key=lambda b: min(math.dist(a, b) for a in src))
            a, b = min(itertools.product(src, self.group(net, self.find(b0))),
                       key=lambda ab: math.dist(*ab))
            self.union(a, b)
            self.jumpers.append((net, a, b))

    def run(self, order):
        for net in order:
            self.connect(net, bare=net not in D.INSULATED)
        for net in sorted(D.INSULATED):
            self.connect(net, bare=False)
        return self

    def verify(self):
        problems = []
        for net in self.nets:
            roots = {self.find(hole) for _, _, hole in self.net_pads[net]}
            if len(roots) != 1:
                problems.append(f"net {net} not connected ({len(roots)} groups)")
        seen = {}
        for net, path in self.wires:
            for a, b in zip(path, path[1:]):
                if manhattan(a, b) != 1:
                    problems.append(f"{net}: jump {D.hname(a)}-{D.hname(b)}")
            for x in path:
                if x in self.pad_at and self.pad_at[x][2] != net:
                    problems.append(f"{net} runs through a pad of {self.pad_at[x][0]} ({D.hname(x)})")
                if seen.setdefault(x, net) != net:
                    problems.append(f"{D.hname(x)}: {seen[x]} and {net} in one hole")
        for net, a, b in self.jumpers:
            for x in (a, b):
                if self.owner.get(x) != net:
                    problems.append(f"wire {net} ends in a foreign hole {D.hname(x)}")
        return problems

    def score(self):
        signal = sum(1 for n, _, _ in self.jumpers if n not in D.INSULATED)
        ins_len = sum(math.dist(a, b) for _, a, b in self.jumpers)
        bare = sum(len(p) - 1 for _, p in self.wires)
        return signal * 100 + ins_len * 1.0 + bare * 0.3


# --- search: channel columns x limiter position x routing order ------------------------
# Two passes: a few routing orders for every placement, then many for the best few.
# Every placement has its own seeded generator, so the result does not depend on
# how many placements came before it.
tried = 0


def best_routing(a, lim, tries, tag):
    global tried
    D.build(a, lim)
    pad_at, net_pads, errors = check_placement()
    if errors:
        return None
    nets = sorted(n for n in net_pads if not n.startswith("NC_") and n not in D.INSULATED)
    rng = random.Random(f"{a}/{lim}/{tag}")
    best = None
    for _ in range(tries):
        order = nets[:]
        rng.shuffle(order)
        lay = Layout(pad_at, net_pads).run(order)
        tried += 1
        if lay.verify():
            continue
        sc = round(lay.score(), 6)
        if best is None or sc < best[0]:
            best = (sc, a, lim, order)
    return best


placements = [(a, lim) for a in itertools.product(*D.CHANNEL_CHOICES)
              if min(y - x for x, y in zip(a, a[1:])) >= D.MIN_PITCH
              for lim in D.LIMITER_CHOICES]
first = sorted(r for r in (best_routing(a, lim, TRIES_FIRST, 1) for a, lim in placements) if r)
if not first:
    fail("no placement passed the checks")
second = [best_routing(a, lim, TRIES, 2) for _, a, lim, _ in first[:KEEP]]
_, A, LIM, ORDER = min(first + [r for r in second if r])
D.build(A, LIM)
PAD_AT, NET_PADS, placement_errors = check_placement()
L = Layout(PAD_AT, NET_PADS).run(ORDER)
NETS = L.nets
WIRES, JUMPERS = L.wires, L.jumpers
problems = placement_errors + L.verify()
bare = sum(len(p) - 1 for _, p in WIRES)
signal_jumpers = [j for j in JUMPERS if j[0] not in D.INSULATED]
print(f"searched {tried} layouts ({len(placements)} placements); fan channels in columns {A}, "
      f"limiter: pin 1 at {D.hname(LIM[:2])}, rotated {LIM[2]} deg")
print(f"parts {len(D.PARTS)}, nets {len(NETS)}")
print(f"bare wire on the solder side: {len(WIRES)} runs, {bare} steps of 2.54 mm")
print(f"insulated wires: {len(JUMPERS)} (signal/GND/5V among them: {len(signal_jumpers)})")
for n, a_, b_ in JUMPERS:
    print(f"   {n:10s} {D.hname(a_)} - {D.hname(b_)}")
print(f"problems: {len(problems)}")
for p in problems:
    print("  -", p)

# --- languages ----------------------------------------------------------------------
# The documents are written in English. A local translation can be dropped in as
# <project>/pl/lang_pl.py (see the end of this file); it is not part of the project.
LANG = "en"
TEXT = {
    "en": dict(
        top="COMPONENT SIDE (top view)", bottom="SOLDER SIDE (bottom view - mirrored)",
        wire="W", legend=["12 V", "5 V USB", "3.3 V", "ground", "1-Wire", "signals"],
        legend_wire="W = insulated wire", res="resistor", under="dashed outline = sits under the Pico",
        title="PC-3 perfboard (72 × 47 mm, 2.54 mm pitch)",
        kind={"pico": "microcontroller", "pololu": "5→12 V boost module", "cap": "electrolytic capacitor",
              "terminal": "screw terminal", "res": "resistor, standing", "fan": "fan header",
              "to92": "NPN transistor", "adapter6": "current limiter on an adapter",
              "res_flat": "resistor, lying flat (under the Pico)", "cap_small": "ceramic capacitor"},
        notes={},
        head=None),
}


def t(key):
    return TEXT[LANG][key]


def note(text):
    return TEXT[LANG]["notes"].get(text, text)


# --- drawing -------------------------------------------------------------------------
S = 10.0  # px per mm
PAD_R = 0.9
PALETTE = {
    "GND": "#4a4a4a", "+3V3": "#d9480f", "+12V": "#c92a2a", "VBUS": "#a61e4d",
    "DQ": "#2b8a3e",
}
SIGNAL_COLORS = ["#1c7ed6", "#7048e8", "#0b7285", "#364fc7", "#9c36b5", "#1098ad"]


def color(net):
    if net in PALETTE:
        return PALETTE[net]
    return SIGNAL_COLORS[sum(map(ord, net)) % len(SIGNAL_COLORS)]


def xy(hole, mirror=False):
    c, r = hole
    x = D.MARGIN_X + (c - 1) * D.PITCH
    if mirror:
        x = D.BOARD_W - x
    return x * S, (D.MARGIN_Y + (r - 1) * D.PITCH) * S


def gx(v, mirror=False):  # hole-units x -> px
    x = D.MARGIN_X + (v - 1) * D.PITCH
    return (D.BOARD_W - x if mirror else x) * S


def gy(v):
    return (D.MARGIN_Y + (v - 1) * D.PITCH) * S


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def board(mirror, title):
    o = []
    W, H = D.BOARD_W * S, D.BOARD_H * S
    o.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="12" class="pcb"/>')
    for (hx, hy) in ((3.2, 3.2), (D.BOARD_W - 3.2, 3.2), (3.2, D.BOARD_H - 3.2),
                     (D.BOARD_W - 3.2, D.BOARD_H - 3.2)):
        o.append(f'<circle cx="{hx * S}" cy="{hy * S}" r="{1.6 * S}" class="mhole"/>')
    for c in range(1, D.COLS + 1):
        x, _ = xy((c, 1), mirror)
        o.append(f'<text x="{x}" y="{gy(0.05)}" class="grid">{c}</text>')
    for r in range(1, D.ROWS + 1):
        _, y = xy((1, r), mirror)
        lx = gx(0.25, mirror)
        o.append(f'<text x="{lx}" y="{y + 4}" class="grid">{D.ROW_NAMES[r - 1]}</text>')
    for hole in sorted(HOLES):
        x, y = xy(hole, mirror)
        o.append(f'<circle cx="{x}" cy="{y}" r="{PAD_R * S}" class="hole"/>')
    o.append(f'<text x="{W / 2}" y="{H + 34}" class="title">{esc(title)}</text>')
    return o


def pico_label_y():
    """Row for the Pico caption: the wider free band under the Pico, above or below
    the low parts sitting there."""
    lows = [bbox(p["body"]) for p in D.PARTS.values() if p["kind"] in D.LOW_KINDS]
    if not lows:
        return 5.5
    top, bot = min(b[1] for b in lows), max(b[3] for b in lows)
    return max((top - 2.5, (2.5 + top) / 2), (8.5 - bot, (bot + 8.5) / 2))[1]


RES_CLASS = {"4k7": " r4k7", "10k": " r10k", "51k": " r51k"}
ADAPTER_PINS = {"1": "IN", "2": "GND", "3": "EN", "4": "FLT", "5": "ILIM", "6": "OUT"}


def top_side():
    o = board(False, t("top"))
    for ref, p in D.PARTS.items():
        b = p["body"]
        val = RES_CLASS.get(p["value"], "") if p["kind"] in ("res", "res_flat") else ""
        if p["kind"] == "res_flat":  # leads under the body, bent down into both pads
            (h1, _), (h2, _) = p["pads"].values()
            (x1, y1), (x2, y2) = xy(h1), xy(h2)
            o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="lead"/>')
        if b[0] == "rect":
            x0, x1 = gx(b[1]), gx(b[3])
            y0, y1 = gy(b[2]), gy(b[4])
            o.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
                     f'rx="4" class="body {p["kind"]}{val}"/>')
            tx, ty = (x0 + x1) / 2, (y0 + y1) / 2
        else:
            _, cx, cy, r = b
            o.append(f'<circle cx="{gx(cx)}" cy="{gy(cy)}" r="{r * D.PITCH * S}" '
                     f'class="body {p["kind"]}{val}"/>')
            tx, ty = gx(cx), gy(cy)
        for pad, (hole, net) in p["pads"].items():
            x, y = xy(hole)
            cls = "pad nc" if net.startswith("NC_") else "pad"
            o.append(f'<circle cx="{x}" cy="{y}" r="{PAD_R * S * 0.8}" class="{cls}"/>')
        if p["kind"] == "res":  # standing resistor: lead from body to the other pad
            (h1, _), (h2, _) = p["pads"].values()
            (x1, y1), (x2, y2) = xy(h1), xy(h2)
            o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="lead"/>')
        if p["kind"] == "to92":
            x0, y0 = gx(b[1]), gy(b[2])
            o.append(f'<line x1="{x0}" y1="{y0 + 2}" x2="{gx(b[3])}" y2="{y0 + 2}" class="flat"/>')
        label = ref if p["kind"] != "pico" else "U1  Raspberry Pi Pico"
        size = "lbl big" if p["kind"] in ("pico", "pololu") else "lbl"
        if p["kind"] == "res":
            o.append(f'<text x="{tx}" y="{ty + 3.5}" class="rlbl">{ref[1:]}</text>')
        elif p["kind"] in ("res_flat", "cap_small"):
            o.append(f'<text x="{tx}" y="{ty + 3.5}" class="rlbl">{ref} {esc(p["value"])}</text>')
        elif p["kind"] == "adapter6":
            # caption between the pad rows, pin names next to the pads inside the body
            pys = sorted({xy(hh)[1] for hh, _ in p["pads"].values()})
            o.append(f'<text x="{tx}" y="{(pys[0] + pys[1]) / 2 + 4}" class="lbl">{ref}</text>')
            o.append(f'<text x="{tx}" y="{(pys[1] + pys[2]) / 2 + 4}" class="val">TPS2553</text>')
            for pad, (hole, _) in p["pads"].items():
                x, y = xy(hole)
                left = x < tx
                o.append(f'<text x="{x + (9 if left else -9)}" y="{y + 3}" class="pin" '
                         f'style="text-anchor:{"start" if left else "end"}">{ADAPTER_PINS[pad]}</text>')
        elif p["kind"] == "pico":
            ly = gy(pico_label_y())
            o.append(f'<text x="{tx}" y="{ly + 5}" class="{size}">{label}</text>')
            o.append(f'<text x="{gx(2.2)}" y="{ly + 4}" class="val">◀ USB</text>')
        elif p["kind"] in ("fan", "terminal"):
            o.append(f'<text x="{tx}" y="{gy(b[4]) + 13}" class="lbl">{ref} {esc(p["value"])}</text>')
        else:
            o.append(f'<text x="{tx}" y="{ty - 2}" class="{size}">{ref}</text>')
            o.append(f'<text x="{tx}" y="{ty + 10}" class="val">{esc(p["value"])}</text>')
        # pin names on connectors, transistors and the Pololu
        if p["kind"] in ("fan", "to92", "pololu", "terminal", "cap"):
            names = {"fan": {"1": "GND", "2": "12V", "3": "TACH", "4": "PWM"},
                     "terminal": {"1": "3V3", "2": "DQ", "3": "GND"}}.get(p["kind"], {})
            for pad, (hole, net) in p["pads"].items():
                x, y = xy(hole)
                dy = -14 if p["kind"] == "fan" else -11
                if p["kind"] == "terminal":
                    o.append(f'<text x="{x + 14}" y="{y + 4}" class="pin" style="text-anchor:start">{names.get(pad, pad)}</text>')
                else:
                    o.append(f'<text x="{x}" y="{y + dy}" class="pin">{names.get(pad, pad)}</text>')
    return o


def bottom_side():
    o = board(True, t("bottom"))
    for net, path in WIRES:
        pts = " ".join(f"{x},{y}" for x, y in (xy(hh, True) for hh in path))
        o.append(f'<polyline points="{pts}" class="wire" stroke="{color(net)}"/>')
    for hole, (ref, pad, net) in PAD_AT.items():
        x, y = xy(hole, True)
        cls = "spad nc" if net.startswith("NC_") else "spad"
        o.append(f'<circle cx="{x}" cy="{y}" r="{PAD_R * S * 0.95}" class="{cls}"/>')
    for i, (net, a, b) in enumerate(JUMPERS, 1):
        (x1, y1), (x2, y2) = xy(a, True), xy(b, True)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 14
        o.append(f'<path d="M{x1},{y1} Q{mx},{my} {x2},{y2}" class="jumper" '
                 f'stroke="{color(net)}"/>')
        for x, y in ((x1, y1), (x2, y2)):
            o.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color(net)}"/>')
        u = 0.3 if i % 2 else 0.7  # label point on the curve, alternating
        lx = (1 - u) ** 2 * x1 + 2 * u * (1 - u) * mx + u ** 2 * x2
        ly = (1 - u) ** 2 * y1 + 2 * u * (1 - u) * my + u ** 2 * y2
        o.append(f'<text x="{lx}" y="{ly - 5}" class="jlbl" fill="{color(net)}">{t("wire")}{i}</text>')
    return o


def legend():
    items = list(zip(("+12V", "VBUS", "+3V3", "GND", "DQ", "PWM1"), t("legend")))
    o = []
    x = 0
    for net, label in items:
        o.append(f'<line x1="{x}" y1="10" x2="{x + 22}" y2="10" stroke="{color(net)}" stroke-width="5"/>')
        o.append(f'<text x="{x + 27}" y="14" class="leg">{label}</text>')
        x += 27 + 8 * len(label) + 18
    o.append(f'<line x1="{x}" y1="10" x2="{x + 22}" y2="10" class="jumper" stroke="#555"/>')
    o.append(f'<text x="{x + 27}" y="14" class="leg">{t("legend_wire")}</text>')
    x = 0
    for cls, val in (("r4k7", "4k7"), ("r10k", "10k"), ("r51k", "51k")):
        o.append(f'<circle cx="{x + 9}" cy="34" r="8" class="body res {cls}"/>')
        o.append(f'<text x="{x + 23}" y="38" class="leg">{t("res")} {val}</text>')
        x += 130
    o.append(f'<text x="{x}" y="38" class="leg">{t("under")}</text>')
    return o


CSS = """
:root { --pcb:#f0d9a8; --hole:#b87333; --ink:#222; --body:#fff; --muted:#666; --bg:#fbfaf7; }
@media (prefers-color-scheme: dark) {
  :root { --pcb:#6b5635; --hole:#d9a066; --ink:#eee; --body:#2a2a2a; --muted:#aaa; --bg:#1b1b1b; }
}
svg { background: var(--bg); font-family: -apple-system, Helvetica, Arial, sans-serif; }
.pcb { fill: var(--pcb); stroke: #8a6d3b; stroke-width: 2; }
.mhole { fill: var(--bg); stroke: #8a6d3b; stroke-width: 1.5; }
.hole { fill: none; stroke: var(--hole); stroke-width: 1.2; opacity: .55; }
.pad { fill: var(--hole); }
.pad.nc { fill: none; stroke: var(--hole); stroke-width: 2; }
.spad { fill: #c0c0c0; stroke: #555; stroke-width: 1.2; }
.spad.nc { fill: #e3e3e3; }
.body { fill: var(--body); fill-opacity: .82; stroke: var(--ink); stroke-width: 1.6; }
.body.pico { fill: #2f9e44; fill-opacity: .25; }
.body.pololu { fill: #1971c2; fill-opacity: .22; stroke-dasharray: 6 3; }
.body.fan, .body.terminal { fill: #f1f3f5; }
.body.cap { fill: #1c3d7a; fill-opacity: .35; }
.body.r4k7 { fill: #ffd43b; fill-opacity: 1; }
.body.r10k { fill: #74c0fc; fill-opacity: 1; }
.body.r51k { fill: #8ce99a; fill-opacity: 1; }
.body.adapter6 { fill: #862e9c; fill-opacity: .18; stroke-dasharray: 4 2; }
.body.res_flat, .body.cap_small { stroke-dasharray: 4 2; }
.body.cap_small { fill: #ffc078; fill-opacity: 1; }
.rlbl { font-size: 9px; font-weight: 700; fill: #111; }
.lead { stroke: var(--ink); stroke-width: 1.4; }
.flat { stroke: var(--ink); stroke-width: 3; }
.wire { fill: none; stroke-width: 5; stroke-linecap: round; stroke-linejoin: round; opacity: .9; }
.jumper { fill: none; stroke-width: 3.2; stroke-dasharray: 9 5; }
text { fill: var(--ink); text-anchor: middle; }
.grid { font-size: 11px; fill: var(--muted); }
.lbl { font-size: 11px; font-weight: 700; }
.lbl.big { font-size: 15px; }
.val { font-size: 9.5px; fill: var(--muted); }
.pin { font-size: 8.5px; fill: var(--muted); }
.jlbl { font-size: 12px; font-weight: 700; }
.title { font-size: 16px; font-weight: 700; }
.leg { font-size: 12px; text-anchor: start; }
"""


def svg():
    W, H = D.BOARD_W * S, D.BOARD_H * S
    pad = 30
    tw, th = W + 2 * pad, 2 * (H + 60) + 94
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {tw} {th}" '
             f'width="{tw}" height="{th}">', f"<style>{CSS}</style>",
             f'<text x="{tw / 2}" y="24" class="title">{D.TITLE} v{D.REV} — {t("title")}</text>',
             f'<g transform="translate({pad},{38})">', *legend(), "</g>",
             f'<g transform="translate({pad},{94})">', *top_side(), "</g>",
             f'<g transform="translate({pad},{94 + H + 60})">', *bottom_side(), "</g>",
             "</svg>"]
    return "\n".join(parts)


# --- connection table ------------------------------------------------------------
def segments(path):
    """Collapse a hole path into straight runs."""
    runs, start = [], path[0]
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            runs.append((start, b))
            start = b
    runs.append((start, path[-1]))
    return runs


def who(hole):
    if hole in PAD_AT:
        ref, pad, _ = PAD_AT[hole]
        return f"{D.hname(hole)} ({ref}.{pad})"
    return D.hname(hole)


TABLE = {
    "en": dict(
        name=("perfboard", "wiring"),
        head=lambda svg: [
            f"# {D.TITLE} — wiring table", "",
            "Generated by `tools/gen_lite.py` from `tools/design_lite.py` — do not edit by hand.", "",
            "Holes are counted **from the component side**: columns 1–25 from the left, rows A–O from the top.",
            "The PC-3 board prints its column numbers on the copper side, so there they run from the right.",
            "Corner positions A1, A25, O1 and O25 do not exist (mounting holes sit there).", "",
            f"Drawing: `{svg}` — component side on top, solder side below, "
            "mirrored (the way you see the board when you turn it over).", "",
            "> [!NOTE]",
            "> Hook-up wire: the `MIKROE-2022` jumper wire kit from the bill of materials. "
            "W wires are insulated wires from the kit. Bare wire on the solder side is a kit wire with "
            "the insulation stripped completely; short bridges between neighbouring holes are "
            "cut-off resistor leads.", "",
            "Assembly order: first the parts that sit under the Pico (U3 on its adapter, C3, R14–R16), "
            "then the Pico sockets (without the Pico), resistors and transistors, "
            "connectors, capacitors, and the boost module last. Solder-side wires — see the tables below. "
            "Plug the Pico in only after checking with a multimeter that there is no short between "
            "VBUS (B1) and GND (B3), nor between the limited 5 V rail (D22) and GND (D23).", "",
            "> [!WARNING]",
            "> BOB-00717 adapter: board 8.6 × 11.7 mm, rows 7.62 mm apart (SparkFun product page). "
            "Solder the TPS2553 so that its pin 1 lands on adapter hole 1, and hold the adapter "
            "against the U3 holes before you solder it to the perfboard.", ""],
        parts=["## Parts", "", "| Ref | Part | Value | TME | Holes | Notes |"],
        nets=["## Nets (net → what it connects)", "", "| Net | Pins (hole) |"],
        bare=["## Bare wire on the solder side (stripped wire, resistor lead or a solder trail)", "",
              "Each row is one straight run from hole to hole, net by net.", "", "| # | Net | From | To |"],
        ins="## Insulated wires (solder side)",
        ins_text=["Insulated wire from the MIKROE-2022 kit on the solder side, "
                  "ends soldered straight to the pads. It may cross bare wires.", "",
                  "| Wire | Net | From | To | Length |"],
        none="None.",
        check=lambda n_parts, n_nets, runs, steps, n_ins, n_prob: [
            "## Check", "", f"- parts: {n_parts}, nets: {n_nets}",
            f"- bare wire on the solder side: {runs} runs, {steps} steps of 2.54 mm",
            f"- insulated wires: {n_ins}", f"- problems found by the checker: {n_prob}"]),
}


def rule(header):
    """Markdown separator row for a table header line."""
    return "|" + "---|" * (header.count("|") - 1)


def table():
    T = TABLE[LANG]
    L = T["head"](f"{NAME}-{T['name'][0]}.svg")
    L += T["parts"] + [rule(T["parts"][-1])]
    for ref, p in D.PARTS.items():
        if p["kind"] == "pico":
            holes = "B1–B20, I1–I20"
        else:
            holes = ", ".join(f"{pad}={D.hname(hh)}" for pad, (hh, _) in p["pads"].items())
        L.append(f"| {ref} | {t('kind')[p['kind']]} | {p['value']} | `{p['tme']}` | {holes} | {note(p['note'])} |")
    L += [""] + T["nets"] + [rule(T["nets"][-1])]
    for net in sorted(NETS):
        members = ", ".join(f"{ref}.{pad} {D.hname(hh)}" for ref, pad, hh in NET_PADS[net])
        L.append(f"| `{net}` | {members} |")
    L += [""] + T["bare"] + [rule(T["bare"][-1])]
    i = 0
    for net, path in WIRES:
        for a, b in segments(path):
            i += 1
            L.append(f"| {i} | `{net}` | {who(a)} | {who(b)} |")
    L += ["", T["ins"], ""]
    if JUMPERS:
        L += T["ins_text"] + [rule(T["ins_text"][-1])]
        for k, (net, a, b) in enumerate(JUMPERS, 1):
            L.append(f"| {t('wire')}{k} | `{net}` | {who(a)} | {who(b)} | ≈ {math.dist(a, b) * D.PITCH:.0f} mm |")
    else:
        L.append(T["none"])
    L += [""] + T["check"](len(D.PARTS), len(NETS), len(WIRES), bare, len(JUMPERS), len(problems))
    return "\n".join(L) + "\n"


# English next to the design files. Optional local translations: <project>/<lang>/lang_<lang>.py
# defining strings(D) -> (text, table); their output goes into that folder.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(OUT)))
outputs = [("en", OUT)]
for code in ("pl",):
    lang_file = os.path.join(ROOT, code, f"lang_{code}.py")
    if os.path.exists(lang_file):
        spec = importlib.util.spec_from_file_location(f"lang_{code}", lang_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        TEXT[code], TABLE[code] = mod.strings(D)
        outputs.append((code, os.path.join(ROOT, code)))
for LANG, out_dir in outputs:
    os.makedirs(out_dir, exist_ok=True)
    svg_name, table_name = TABLE[LANG]["name"]
    with open(os.path.join(out_dir, f"{NAME}-{svg_name}.svg"), "w") as f:
        f.write(svg())
    with open(os.path.join(out_dir, f"{NAME}-{table_name}.md"), "w") as f:
        f.write(table())


# --- geometry for the enclosure (enclosure/FanCtrl3-lite-geometry.scad) --------------
def mm(c, r):
    return D.MARGIN_X + (c - 1) * D.PITCH, D.MARGIN_Y + (r - 1) * D.PITCH


def body_mm(b):
    x0, y0, x1, y1 = bbox(b)
    (a, c), (e, f) = mm(x0, y0), mm(x1, y1)
    return [round(a, 2), round(c, 2), round(e, 2), round(f, 2)]


HEIGHT = {"fan": 12, "res": 11, "to92": 8, "cap": 12, "terminal": 8.5, "pololu": 7,
          # under the Pico: adapter on header plastic ~5.6, flat resistor 2.5 + lift,
          # AVX SR20 5.08 + coating above the seating plane
          "adapter6": 6, "res_flat": 3, "cap_small": 6.5}
PICO_BOTTOM = 11.0   # 8,5 mm socket + 2,5 mm plastic of the pin header on the Pico
boxes = []
for ref, p in D.PARTS.items():
    if p["kind"] in HEIGHT:
        boxes.append(body_mm(p["body"]) + [0, HEIGHT[p["kind"]]])
pico = body_mm(D.PARTS["U1"]["body"])
usb_y = round((pico[1] + pico[3]) / 2, 2)
boxes.append(pico + [PICO_BOTTOM, PICO_BOTTOM + 1])                       # Pico board
for row in (2, 9):                                                            # sockets
    _, y = mm(1, row)
    boxes.append([round(mm(1, 1)[0] - 1.27, 2), round(y - 1.27, 2),
                  round(mm(20, 1)[0] + 1.27, 2), round(y + 1.27, 2), 0, PICO_BOTTOM])
boxes.append([round(pico[0] - 1, 2), round(usb_y - 4, 2), round(pico[0] + 5, 2), round(usb_y + 4, 2),
              PICO_BOTTOM + 1, PICO_BOTTOM + 3.6])                            # micro-USB
fans = [D.PARTS[f"J{n}"] for n in (1, 2, 3)]
fan_x = [round(sum(mm(*h)[0] for h, _ in f["pads"].values()) / 4, 2) for f in fans]
fan_y = round(mm(*fans[0]["pads"]["1"][0])[1], 2)
probe_y = round(mm(*D.PARTS["J4"]["pads"]["2"][0])[1], 2)
vent = body_mm(D.PARTS["U2"]["body"])
# Pico LED: 4,7 mm from the USB end, 5,8 mm from the centre towards pin 1 (read off
# the KiCad 3D model of the Pico on the Pro board)
led = [round(pico[0] + 4.7, 2), round(usb_y + 5.8, 2)]
geo = os.path.join(os.path.dirname(os.path.abspath(OUT)), "enclosure", "FanCtrl3-lite-geometry.scad")
with open(geo, "w") as f:
    f.write("// Generated by tools/gen_lite.py from design_lite.py - do not edit by hand.\n"
            "// PC-3 board coordinates in mm: x to the right, y down from the top edge.\n")
    f.write(f"lite_fan_x = {fan_x};\nlite_fan_y = {fan_y};\nlite_probe_y = {probe_y};\n")
    f.write(f"lite_usb_y = {usb_y};\nlite_led = {led};\nlite_vent = {vent};\n")
    f.write(f"lite_usb_z = {PICO_BOTTOM + 1 + 1.3};\n")
    f.write("lite_boxes = [\n" + ",\n".join(f"    {b}" for b in boxes) + "\n];\n")
print("enclosure geometry:", os.path.relpath(geo))
sys.exit(1 if problems else 0)
