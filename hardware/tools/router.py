"""Small two-layer grid router for FanCtrl3 Pro.

Reads <out>.geom.json (from gen_pcb.py geom), routes every net except GND
(GND is carried by copper pours on both layers plus stitching vias) and writes
<out>.routes.json for gen_pcb.py finish.

Clearance is checked against real copper geometry (pad rectangles, track
segments, vias, holes, board edge), not against grid occupancy, so the result
is meant to pass KiCad DRC as-is. DRC is still run afterwards.
"""
import heapq
import json
import math
import sys
from collections import defaultdict

OUT = sys.argv[1]
G = json.load(open(f"{OUT}.geom.json"))

RES = 0.1            # grid, mm
CLR = 0.2            # copper clearance, mm
MARGIN = 0.03        # extra safety on top of CLR
EDGE = 0.35          # copper to board edge
HOLE_CLR = 0.3       # copper to NPTH hole edge
VIA_D, VIA_DRILL = 0.6, 0.3
SIGNAL_W = 0.25
NECK_W = 0.4         # width into fine-pitch pads
BOTTOM_COST = 3.0    # keep the bottom GND plane as whole as possible
VIA_COST = 40.0
W_BOARD, H_BOARD = G["w"], G["h"]
NX, NY = int(W_BOARD / RES) + 1, int(H_BOARD / RES) + 1

WIDTH = {"VBUS": 0.5, "/+5V_FAN": 0.6, "/SW": 0.6, "+12V": 0.5}
# Pico body: no top copper tracks or vias between its pad rows
NO_TOP = [(0.0, 12.95, 51.2, 29.05)]


class Item:
    __slots__ = ("kind", "net", "layers", "a", "r")

    def __init__(self, kind, net, layers, a, r):
        self.kind, self.net, self.layers, self.a, self.r = kind, net, layers, a, r
        # rect: a=(x0,y0,x1,y1) r=0 ; seg: a=(x0,y0,x1,y1) r=half width ; circ: a=(x,y) r


def dist_rect(x, y, a):
    dx = max(a[0] - x, 0.0, x - a[2])
    dy = max(a[1] - y, 0.0, y - a[3])
    return math.hypot(dx, dy)


def dist_seg(x, y, a):
    x0, y0, x1, y1 = a
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / L2))
    return math.hypot(x - (x0 + t * vx), y - (y0 + t * vy))


def item_dist(it, x, y):
    if it.kind == "rect":
        return dist_rect(x, y, it.a)
    if it.kind == "seg":
        return dist_seg(x, y, it.a) - it.r
    return math.hypot(x - it.a[0], y - it.a[1]) - it.r


BUCKET = 1.0
buckets = defaultdict(list)


def add_item(it):
    if it.kind in ("rect", "seg"):
        x0, y0, x1, y1 = it.a
        x0, x1 = min(x0, x1) - it.r, max(x0, x1) + it.r
        y0, y1 = min(y0, y1) - it.r, max(y0, y1) + it.r
    else:
        x0, y0, x1, y1 = it.a[0] - it.r, it.a[1] - it.r, it.a[0] + it.r, it.a[1] + it.r
    for bx in range(int(x0 // BUCKET) - 1, int(x1 // BUCKET) + 2):
        for by in range(int(y0 // BUCKET) - 1, int(y1 // BUCKET) + 2):
            buckets[(bx, by)].append(it)


def near(x, y, reach):
    seen = set()
    for bx in range(int((x - reach) // BUCKET), int((x + reach) // BUCKET) + 1):
        for by in range(int((y - reach) // BUCKET), int((y + reach) // BUCKET) + 1):
            for it in buckets.get((bx, by), ()):
                if id(it) not in seen:
                    seen.add(id(it))
                    yield it


pads = G["pads"]
for p in pads:
    if p["npth"]:
        add_item(Item("circ", None, (0, 1), (p["cx"], p["cy"]), p["drill"] / 2 + HOLE_CLR - CLR))
        continue
    if not p["layers"]:
        continue
    add_item(Item("rect", p["net"] or f"~{p['ref']}.{p['num']}", tuple(p["layers"]),
                  (p["x0"], p["y0"], p["x1"], p["y1"]), 0.0))
    if p["drill"]:
        add_item(Item("circ", p["net"] or "~", (0, 1), (p["cx"], p["cy"]), p["drill"] / 2))

keepouts = [(k["x0"], k["y0"], k["x1"], k["y1"], set(k["layers"])) for k in G["keepouts"]]


def blocked_factory(net, w):
    cache = {}
    half = w / 2

    def blocked(layer, ix, iy):
        key = (layer, ix, iy)
        v = cache.get(key)
        if v is not None:
            return v
        x, y = ix * RES, iy * RES
        v = False
        if (x < EDGE + half or y < EDGE + half or x > W_BOARD - EDGE - half
                or y > H_BOARD - EDGE - half):
            v = True
        if not v and layer == 0:
            for (x0, y0, x1, y1) in NO_TOP:
                if x0 - half <= x <= x1 + half and y0 - half <= y <= y1 + half:
                    v = True
                    break
        if not v:
            for (x0, y0, x1, y1, ls) in keepouts:
                if layer in ls and dist_rect(x, y, (x0, y0, x1, y1)) < half + CLR:
                    v = True
                    break
        if not v:
            lim = CLR + MARGIN + half
            for it in near(x, y, lim + 1.5):
                if it.net == net or layer not in it.layers:
                    continue
                if item_dist(it, x, y) < lim:
                    v = True
                    break
        cache[key] = v
        return v

    vcache = {}

    def via_blocked(ix, iy):
        key = (ix, iy)
        v = vcache.get(key)
        if v is not None:
            return v
        x, y = ix * RES, iy * RES
        r = VIA_D / 2
        v = (x < EDGE + r or y < EDGE + r or x > W_BOARD - EDGE - r or y > H_BOARD - EDGE - r)
        if not v:
            for (x0, y0, x1, y1) in NO_TOP:
                if x0 - r <= x <= x1 + r and y0 - r <= y <= y1 + r:
                    v = True
        if not v:
            for (x0, y0, x1, y1, ls) in keepouts:
                if dist_rect(x, y, (x0, y0, x1, y1)) < r + CLR:
                    v = True
        if not v:
            for it in near(x, y, r + CLR + 2.0):
                if it.net == net:
                    continue
                if item_dist(it, x, y) < r + CLR + MARGIN:
                    v = True
                    break
        vcache[key] = v
        return v

    return blocked, via_blocked


def pad_cells(p, blocked):
    out = []
    # stay clear of rounded corners: only the inner part of the pad counts
    ins = min(0.3, min(p["x1"] - p["x0"], p["y1"] - p["y0"]) / 2 - 0.1)
    ix0, ix1 = math.ceil((p["x0"] + ins) / RES), math.floor((p["x1"] - ins) / RES)
    iy0, iy1 = math.ceil((p["y0"] + ins) / RES), math.floor((p["y1"] - ins) / RES)
    for L in p["layers"]:
        for ix in range(ix0, ix1 + 1):
            for iy in range(iy0, iy1 + 1):
                if p["shape"] in ("circle", "oval"):
                    a_, b_ = (p["x1"] - p["x0"]) / 2 - 0.08, (p["y1"] - p["y0"]) / 2 - 0.08
                    ex, ey = (ix * RES - p["cx"]) / a_, (iy * RES - p["cy"]) / b_
                    if ex * ex + ey * ey > 1.0:
                        continue
                if not blocked(L, ix, iy):
                    out.append((L, ix, iy))
    return out


DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def astar(sources, goal_set, goal_xy, blocked, via_blocked, allow_bottom=True, max_exp=600000):
    gx, gy = goal_xy
    openh = []
    best = {}
    parent = {}
    for s in sources:
        best[s] = 0.0
        parent[s] = None
        h = math.hypot(s[1] - gx, s[2] - gy)
        heapq.heappush(openh, (h, 0.0, s))
    exp = 0
    while openh:
        f, gcost, cur = heapq.heappop(openh)
        if gcost > best.get(cur, 1e18):
            continue
        if cur in goal_set:
            path = []
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            return path[::-1]
        exp += 1
        if exp > max_exp:
            return None
        L, ix, iy = cur
        lc = 1.0 if L == 0 else BOTTOM_COST
        nbrs = []
        for dx, dy, c in DIRS:
            nx, ny = ix + dx, iy + dy
            if blocked(L, nx, ny):
                continue
            if dx and dy and (blocked(L, ix + dx, iy) or blocked(L, ix, iy + dy)):
                continue
            nbrs.append(((L, nx, ny), c * lc))
        if allow_bottom and not via_blocked(ix, iy) and not blocked(1 - L, ix, iy):
            nbrs.append(((1 - L, ix, iy), VIA_COST))
        for nxt, c in nbrs:
            ng = gcost + c
            if ng < best.get(nxt, 1e18):
                best[nxt] = ng
                parent[nxt] = cur
                h = math.hypot(nxt[1] - gx, nxt[2] - gy) * 1.02
                heapq.heappush(openh, (ng + h, ng, nxt))
    return None


def line_free(a, b, L, blocked):
    """Straight 0/45/90 degree run between grid points a and b on layer L."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    if not (dx == 0 or dy == 0 or abs(dx) == abs(dy)):
        return False
    n = max(abs(dx), abs(dy))
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    for k in range(1, n + 1):
        x, y = x0 + sx * k, y0 + sy * k
        if blocked(L, x, y):
            return False
        if sx and sy and (blocked(L, x - sx, y) or blocked(L, x, y - sy)):
            return False
    return True


def simplify(run, L, blocked):
    pts = [(c[1], c[2]) for c in run]
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not line_free(pts[i], pts[j], L, blocked):
            j -= 1
        out.append(pts[j])
        i = j
    return out


tracks, vias = [], []


def commit(net, path, w, blocked):
    runs = [[path[0]]]
    for c in path[1:]:
        if c[0] != runs[-1][-1][0]:
            vias.append(dict(x=round(c[1] * RES, 4), y=round(c[2] * RES, 4), net=net))
            add_item(Item("circ", net, (0, 1), (c[1] * RES, c[2] * RES), VIA_D / 2))
            runs.append([c])
        else:
            runs[-1].append(c)
    cells = []
    for run in runs:
        L = run[0][0]
        pts = simplify(run, L, blocked) if len(run) > 1 else []
        for (a, b) in zip(pts, pts[1:]):
            t = dict(x0=round(a[0] * RES, 4), y0=round(a[1] * RES, 4),
                     x1=round(b[0] * RES, 4), y1=round(b[1] * RES, 4), w=w, layer=L, net=net)
            tracks.append(t)
            add_item(Item("seg", net, (L,), (t["x0"], t["y0"], t["x1"], t["y1"]), w / 2))
        cells += run
    return cells


def conn_width(net, pa, pb):
    w = WIDTH.get(net, SIGNAL_W)
    minor = min(min(p["x1"] - p["x0"], p["y1"] - p["y0"]) for p in (pa, pb))
    if minor < 0.9:
        w = min(w, NECK_W)
    return w


by_net = defaultdict(list)
for p in pads:
    if p["net"] and not p["npth"]:
        by_net[p["net"]].append(p)

# --- GND stitching: every SMD GND pad gets its own via to the bottom plane ---
gnd_smd = [p for p in by_net["GND"] if p["layers"] == [0]]
gnd_smd.sort(key=lambda p: p["ref"] != "U1")  # Pico first: tightest spots
for p in gnd_smd:
    w = min(0.4, min(p["x1"] - p["x0"], p["y1"] - p["y0"]))
    blocked, via_blocked = blocked_factory("GND", w)
    src = set(pad_cells(p, blocked))

    class ViaGoal:
        def __contains__(self, c, p=p):
            x, y = c[1] * RES, c[2] * RES
            if dist_rect(x, y, (p["x0"], p["y0"], p["x1"], p["y1"])) < 0.5:
                return False  # no via-in-pad: it wicks solder away from the joint
            return c[0] == 0 and not via_blocked(c[1], c[2]) and not blocked(1, c[1], c[2])
    path = astar(src, ViaGoal(), (p["cx"] / RES, p["cy"] / RES), blocked, via_blocked,
                 allow_bottom=False, max_exp=20000) if src else None
    if not path:
        failed.append(f"GND stitch {p['ref']}.{p['num']}")
        continue
    end = path[-1]
    commit("GND", path + [(1, end[1], end[2])], w, blocked)


ORDER = ["/SW", "/+5V_FAN", "/FB", "/SHDN", "/ILIM", "VBUS",
         "/FAN1_PWM", "/FAN2_PWM", "/FAN3_PWM", "/PWM1", "/PWM2", "/PWM3",
         "/FAN1_TACH", "/FAN2_TACH", "/FAN3_TACH", "/TACH1", "/TACH2", "/TACH3",
         "/DQ", "/FAULT", "/FAN_EN", "+3V3", "+12V"]
missing = {n for n in set(by_net) - set(ORDER) - {"GND"} if not n.startswith("unconnected-")}
assert not missing, f"nets not in ORDER: {missing}"
failed = []
for net in ORDER:
    ps = by_net[net]
    if len(ps) < 2:
        continue
    done = [ps[0]]
    todo = ps[1:]
    tree_cells = None
    while todo:
        # nearest pad to anything already connected
        todo.sort(key=lambda q: min(math.hypot(q["cx"] - d["cx"], q["cy"] - d["cy"]) for d in done))
        tgt = todo.pop(0)
        src_pad = min(done, key=lambda d: math.hypot(tgt["cx"] - d["cx"], tgt["cy"] - d["cy"]))
        w = conn_width(net, src_pad, tgt)
        blocked, via_blocked = blocked_factory(net, w)
        sources = set()
        for d in done:
            sources.update(pad_cells(d, blocked))
        if tree_cells:
            sources.update(c for c in tree_cells if not blocked(*c))
        goal = set(pad_cells(tgt, blocked))
        path = None
        if sources and goal:
            path = astar(sources, goal, (tgt["cx"] / RES, tgt["cy"] / RES), blocked, via_blocked)
        if not path:
            failed.append(f"{net}: {src_pad['ref']}.{src_pad['num']} -> {tgt['ref']}.{tgt['num']}"
                          f" (src {len(sources)} goal {len(goal)})")
        else:
            cells = commit(net, path, w, blocked)
            tree_cells = (tree_cells or []) + cells
        done.append(tgt)
    print(f"{net:10} ok" if not any(f.startswith(net + ":") for f in failed) else f"{net:10} FAILED")

# --- GND stitching grid: ties top and bottom pours together, keeps top islands alive ---
_, gnd_via_blocked = blocked_factory("GND", 0.4)
STITCH = 6.0
n_stitch = 0
yy = 2.0
while yy < H_BOARD - 1.5:
    xx = 2.0
    while xx < W_BOARD - 1.5:
        ix, iy = round(xx / RES), round(yy / RES)
        # a little search so the grid still lands between parts
        for dx, dy in ((0, 0), (5, 0), (-5, 0), (0, 5), (0, -5), (5, 5), (-5, -5), (5, -5), (-5, 5)):
            jx, jy = ix + dx, iy + dy
            x, y = jx * RES, jy * RES
            if gnd_via_blocked(jx, jy):
                continue
            # keep 0.6 mm between the stitching via and any other copper of any net
            if any(item_dist(it, x, y) < VIA_D / 2 + 0.6 for it in near(x, y, 2.5)):
                continue
            vias.append(dict(x=round(x, 4), y=round(y, 4), net="GND"))
            add_item(Item("circ", "GND", (0, 1), (x, y), VIA_D / 2))
            n_stitch += 1
            break
        xx += STITCH
    yy += STITCH
print(f"stitching vias {n_stitch}")

json.dump(dict(tracks=tracks, vias=vias, failed=failed), open(f"{OUT}.routes.json", "w"), indent=0)
print(f"tracks {len(tracks)}  vias {len(vias)}  failed {len(failed)}")
for f in failed:
    print("  FAILED", f)
