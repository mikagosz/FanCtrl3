"""Build the FanCtrl3 Pro board with KiCad's pcbnew API (run with KiCad's Python).

  place  - new board: outline, footprints, nets, text      -> <out>.kicad_pcb
  geom   - dump pads / obstacles for the router             -> <out>.geom.json
  finish - add routed tracks, GND stitching, zones, fill    -> <out>.kicad_pcb
"""
import json
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(__file__))
import design_pro as D  # noqa: E402

FPLIB = os.path.join(os.environ.get("KICAD_SHARE", "/Applications/KiCad/KiCad.app/Contents/SharedSupport"), "footprints")
OX, OY = 100.0, 100.0          # board origin on the KiCad page
W, H = 90.0, 60.0              # board size, mm
CORNER = 3.0                   # outline corner radius

MM = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


# board-local placement: ref -> (x, y, rotation_deg, side)
PLACE = {
    "U1": (25.7, 21.0, 90),
    # USB current limiter
    "C1": (54.0, 8.0, 90), "U2": (58.5, 8.0, 0),
    "R1": (63.0, 12.0, 90), "R2": (54.5, 14.5, 90), "R3": (57.5, 14.5, 90),
    # boost
    "C2": (66.0, 13.0, 90), "R4": (66.5, 7.0, 0), "U3": (71.0, 8.0, 180),
    "L1": (71.0, 15.5, 0), "D1": (79.0, 15.5, 180),
    "R5": (77.0, 5.0, 0), "R6": (77.0, 10.0, 0), "C3": (80.5, 7.5, 90),
    "C4": (85.5, 12.5, 90), "C5": (85.5, 18.5, 90),
    # fan channels (header pin 1 at x, y=55)
    "J1": (9.0, 55.0, 0), "J2": (23.0, 55.0, 0), "J3": (37.0, 55.0, 0),
    "C6": (60.0, 50.0, 0), "C7": (54.0, 50.0, 90),
    # ambient sensor
    "J4": (74.0, 55.0, 0), "R16": (72.0, 46.0, 90),
}
for n, hx in enumerate((9.0, 23.0, 37.0), 1):
    PLACE[f"Q{n}"] = (hx + 9.0, 44.0, 90)       # SOT-23
    PLACE[f"R{6 + n}"] = (hx + 4.5, 44.0, 90)   # gate pull-down
    PLACE[f"R{9 + n}"] = (hx + 4.5, 37.5, 90)   # tach pull-up
    PLACE[f"R{12 + n}"] = (hx + 9.0, 37.5, 90)  # tach series
for n, (hx, hy) in enumerate(((3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)), 1):
    PLACE[f"H{n}"] = (hx, hy, 0)

SILK = [
    # text, x, y, size, rotation
    ("FanCtrl3 Pro v1.0", 66.0, 26.5, 1.5, 0),
    ("FAN1", 12.8, 59.0, 1.0, 0), ("FAN2", 26.8, 59.0, 1.0, 0),
    ("FAN3", 40.8, 59.0, 1.0, 0), ("3V3 DQ GND", 76.5, 50.6, 0.8, 0),
    ("TEMP", 76.5, 49.0, 0.9, 0),
]

NETCLASS_POWER = {"VBUS": 0.6, "+5V_FAN": 0.8, "SW": 0.8, "+12V": 0.6, "GND": 0.5}


REF_POS = {  # board-local override for crowded spots: ref -> (x, y, angle)
    "J4": (70.3, 55.0, 90), "U1": (46.0, 21.0, 0), "C6": (61.25, 44.6, 0),
    "C1": (52.2, 8.0, 90), "R2": (54.5, 17.0, 0), "R3": (57.5, 17.0, 0),
}


def pcb_net(net):
    """Schematic label nets are sheet-local ('/NAME'); power symbols are global."""
    return net if net in ("GND", "+3V3", "+12V", "VBUS") else f"/{net}"


def ref_text(fp, ref):
    t = fp.Reference()
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
    t.SetTextThickness(MM(0.12))
    if ref.startswith("H") or ref in ("J1", "J2", "J3"):  # FANn silk labels instead
        t.SetVisible(False)
        return
    if ref in REF_POS:
        x, y, a = REF_POS[ref]
    else:
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        x = pcbnew.ToMM(bb.GetCenter().x) - OX
        y = pcbnew.ToMM(bb.GetBottom()) - OY + 0.55
        a = 0
    t.SetPosition(P(x, y))
    t.SetTextAngleDegrees(a)


def lib_fp(fpid):
    lib, name = fpid.split(":")
    return pcbnew.FootprintLoad(f"{FPLIB}/{lib}.pretty", name)


def place(out):
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    board.SetCopperLayerCount(2)
    ds.m_MinClearance = MM(0.2)
    ds.m_TrackMinWidth = MM(0.2)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)
    ds.m_HoleClearance = MM(0.25)
    ds.m_HoleToHoleMin = MM(0.5)
    ds.m_SolderMaskMinWidth = MM(0.1)

    # outline with rounded corners
    r = CORNER
    segs = [((r, 0), (W - r, 0)), ((W, r), (W, H - r)), ((W - r, H), (r, H)), ((0, H - r), (0, r))]
    for (a, b) in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)
    k = r * (1 - 0.70710678)
    for (sx, sy), (mx, my), (ex, ey) in (
            ((0, r), (k, k), (r, 0)), ((W - r, 0), (W - k, k), (W, r)),
            ((W, H - r), (W - k, H - k), (W - r, H)), ((r, H), (k, H - k), (0, H - r))):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(P(sx, sy), P(mx, my), P(ex, ey))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)

    nets = {}
    for ref, p in D.PARTS.items():
        for net in p["pins"].values():
            if net and net not in nets:
                ni = pcbnew.NETINFO_ITEM(board, pcb_net(net))
                board.Add(ni)
                nets[net] = ni

    sym = json.load(open(os.path.join(os.path.dirname(out), ".sym_uuids.json")))
    for ref, p in D.PARTS.items():
        fp = lib_fp(p["footprint"])
        fp.SetFPID(pcbnew.LIB_ID(*p["footprint"].split(":")))
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        x, y, rot = PLACE[ref][:3]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH(f"/{sym['symbols'][ref]}"))
        fp.SetSheetname("/")
        fp.SetSheetfile(f"{os.path.basename(out)}.kicad_sch")
        for k, v in (("TME", p["tme"]), ("Note", p["note"])):
            if v:
                fp.SetField(k, v)
                fp.GetField(k).SetVisible(False)
        for pad in fp.Pads():
            num = pad.GetNumber()
            net = p["pins"].get(num)
            if net:
                pad.SetNet(nets[net])
            elif f"{ref}.{num}" in sym.get("nc", {}):
                # schematic gives every no-connect pin its own net; mirror it for parity
                ni = pcbnew.NETINFO_ITEM(board, sym["nc"][f"{ref}.{num}"])
                board.Add(ni)
                pad.SetNet(ni)
        board.Add(fp)
        ref_text(fp, ref)

    for text, x, y, size, rot in SILK:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text); t.SetPosition(P(x, y)); t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size))); t.SetTextThickness(MM(size * 0.15))
        t.SetTextAngleDegrees(rot)
        board.Add(t)

    board.Save(f"{out}.kicad_pcb")
    print("placed", len(D.PARTS), "footprints,", len(nets), "nets")


def pad_record(pad):
    bb = pad.GetBoundingBox()
    layers = []
    if pad.IsOnLayer(pcbnew.F_Cu):
        layers.append(0)
    if pad.IsOnLayer(pcbnew.B_Cu):
        layers.append(1)
    drill = pad.GetDrillSize()
    return dict(
        ref=pad.GetParentFootprint().GetReference(), num=pad.GetNumber(),
        net=pad.GetNetname(), layers=layers,
        x0=pcbnew.ToMM(bb.GetLeft()) - OX, y0=pcbnew.ToMM(bb.GetTop()) - OY,
        x1=pcbnew.ToMM(bb.GetRight()) - OX, y1=pcbnew.ToMM(bb.GetBottom()) - OY,
        cx=pcbnew.ToMM(pad.GetPosition().x) - OX, cy=pcbnew.ToMM(pad.GetPosition().y) - OY,
        drill=pcbnew.ToMM(max(drill.x, drill.y)),
        npth=pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
        shape={pcbnew.PAD_SHAPE_CIRCLE: "circle", pcbnew.PAD_SHAPE_OVAL: "oval"}.get(
            pad.GetShape(pcbnew.F_Cu), "rect"),
    )


def geom(out):
    board = pcbnew.LoadBoard(f"{out}.kicad_pcb")
    pads = [pad_record(p) for p in board.GetPads()]
    keepouts = []
    zones = list(board.Zones())
    for fp in board.GetFootprints():
        zones += list(fp.Zones())
    for z in zones:
        if z.GetIsRuleArea() and (z.GetDoNotAllowTracks() or z.GetDoNotAllowVias()):
            bb = z.GetBoundingBox()
            keepouts.append(dict(
                x0=pcbnew.ToMM(bb.GetLeft()) - OX, y0=pcbnew.ToMM(bb.GetTop()) - OY,
                x1=pcbnew.ToMM(bb.GetRight()) - OX, y1=pcbnew.ToMM(bb.GetBottom()) - OY,
                tracks=z.GetDoNotAllowTracks(), vias=z.GetDoNotAllowVias(),
                layers=[i for i, L in enumerate((pcbnew.F_Cu, pcbnew.B_Cu)) if z.IsOnLayer(L)]))
    json.dump(dict(w=W, h=H, pads=pads, keepouts=keepouts, widths=NETCLASS_POWER),
              open(f"{out}.geom.json", "w"), indent=0)
    print("pads", len(pads), "keepouts", len(keepouts))


def finish(out):
    board = pcbnew.LoadBoard(f"{out}.kicad_pcb")
    routes = json.load(open(f"{out}.routes.json"))
    nets = {str(n.GetNetname()): n for n in board.GetNetsByName().values()}
    for t in routes["tracks"]:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P(t["x0"], t["y0"])); tr.SetEnd(P(t["x1"], t["y1"]))
        tr.SetWidth(MM(t["w"])); tr.SetLayer(pcbnew.F_Cu if t["layer"] == 0 else pcbnew.B_Cu)
        tr.SetNet(nets[t["net"]])
        board.Add(tr)
    for v in routes["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(P(v["x"], v["y"])); via.SetWidth(MM(0.6)); via.SetDrill(MM(0.3))
        via.SetNet(nets[v["net"]])
        board.Add(via)

    gnd = nets["GND"]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetAssignedPriority(0)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0.2, 0.2), (W - 0.2, 0.2), (W - 0.2, H - 0.2), (0.2, H - 0.2)):
            ol.Append(MM(OX + x), MM(OY + y))
        board.Add(z)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    set_title(board)
    board.Save(f"{out}.kicad_pcb")
    print("tracks", len(routes["tracks"]), "vias", len(routes["vias"]))


def set_title(board):
    """Title block of the board - it ends up in the Gerber job file."""
    tb = board.GetTitleBlock()
    tb.SetTitle(D.TITLE)
    tb.SetRevision(D.REV)
    tb.SetCompany("mikagosz")
    tb.SetComment(0, "USB-powered 3-channel PWM fan controller for a Proxmox host")


def title(out):
    """Set the title block on an existing board without touching anything else."""
    board = pcbnew.LoadBoard(f"{out}.kicad_pcb")
    set_title(board)
    board.Save(f"{out}.kicad_pcb")


if __name__ == "__main__":
    {"place": place, "geom": geom, "finish": finish, "title": title}[sys.argv[1]](sys.argv[2])
