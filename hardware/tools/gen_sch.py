"""Generate the KiCad 10 schematic and symbol library for FanCtrl3.

    python3 tools/gen_sch.py pro     -> pro/FanCtrl3-Pro.kicad_sch
    python3 tools/gen_sch.py lite    -> lite/FanCtrl3-Lite.kicad_sch

Every pin gets a short stub ending in a net label or power symbol, so the
drawing is readable and every connection is explicit. Nets come from
design_pro.py (the same file gen_pcb.py uses) or, for the perfboard variant,
from design_lite.py through design_lite_sch.py.
"""
import json
import os
import sys
import uuid
from datetime import date

import sexp
from sexp import Sym
KICAD = os.environ.get("KICAD_SHARE", "/Applications/KiCad/KiCad.app/Contents/SharedSupport")
OUT = sys.argv[1]
VARIANT = os.path.basename(os.path.normpath(OUT))
if VARIANT == "lite":
    import design_lite_sch as D
else:
    import design_pro as D
NAME = "FanCtrl3-" + VARIANT.capitalize()
ROOT_UUID = str(uuid.uuid5(uuid.NAMESPACE_URL, f"fanctrl3-{VARIANT}-root"))
_uid_n = [0]


def uid(tag=None):
    _uid_n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"fanctrl3-{VARIANT}/{tag or _uid_n[0]}"))


def font(size=1.27, **kw):
    f = [Sym("font"), [Sym("size"), size, size]]
    if kw.get("italic"):
        f.append([Sym("italic"), Sym("yes")])
    return f


def effects(hide=False, justify=None, size=1.27):
    e = [Sym("effects"), font(size)]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    return e


# --- custom symbols ---------------------------------------------------------
def custom_symbol(name, ref, value, fp, ds, desc, pins, box):
    """pins: (number, name, type, x, y, angle)"""
    body = [Sym("symbol"), f"{name}_0_1",
            [Sym("rectangle"), [Sym("start"), -box[0], box[1]],
             [Sym("end"), box[0], -box[1]],
             [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
             [Sym("fill"), [Sym("type"), Sym("background")]]]]
    pl = [Sym("symbol"), f"{name}_1_1"]
    for num, pname, ptype, x, y, a in pins:
        pl.append([Sym("pin"), Sym(ptype), Sym("line"), [Sym("at"), x, y, a],
                   [Sym("length"), 2.54],
                   [Sym("name"), pname, effects()],
                   [Sym("number"), num, effects()]])
    return [Sym("symbol"), name,
            [Sym("pin_names"), [Sym("offset"), 1.016]],
            [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")],
            [Sym("on_board"), Sym("yes")],
            [Sym("property"), "Reference", ref, [Sym("at"), 0, box[1] + 2.54, 0], effects()],
            [Sym("property"), "Value", value, [Sym("at"), 0, -box[1] - 5.08, 0], effects()],
            [Sym("property"), "Footprint", fp, [Sym("at"), 0, 0, 0], effects(hide=True)],
            [Sym("property"), "Datasheet", ds, [Sym("at"), 0, 0, 0], effects(hide=True)],
            [Sym("property"), "Description", desc, [Sym("at"), 0, 0, 0], effects(hide=True)],
            body, pl, [Sym("embedded_fonts"), Sym("no")]]


CUSTOM = {
    "TPS2553DBV": custom_symbol(
        "TPS2553DBV", "U", "TPS2553DBV", "Package_TO_SOT_SMD:SOT-23-6",
        "https://www.ti.com/lit/ds/symlink/tps2553.pdf",
        "Current-limited USB power switch, adjustable limit, active-high EN",
        [("1", "IN", "power_in", -10.16, 5.08, 0),
         ("3", "EN", "input", -10.16, -5.08, 0),
         ("6", "OUT", "power_out", 10.16, 5.08, 180),
         ("4", "~{FAULT}", "open_collector", 10.16, 0, 180),
         ("5", "ILIM", "passive", 10.16, -5.08, 180),
         ("2", "GND", "power_in", 0, -10.16, 90)], (7.62, 7.62)),
    "LM27313XMF": custom_symbol(
        "LM27313XMF", "U", "LM27313XMF", "Package_TO_SOT_SMD:SOT-23-5",
        "https://www.ti.com/lit/ds/symlink/lm27313.pdf",
        "1.6 MHz boost converter, 30 V 800 mA switch",
        [("5", "VIN", "power_in", -10.16, 5.08, 0),
         ("4", "~{SHDN}", "input", -10.16, -5.08, 0),
         ("1", "SW", "passive", 10.16, 5.08, 180),
         ("3", "FB", "input", 10.16, -5.08, 180),
         ("2", "GND", "power_in", 0, -10.16, 90)], (7.62, 7.62)),
    "U3V16F12": custom_symbol(
        "U3V16F12", "U", "U3V16F12", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
        "https://www.pololu.com/product/4945",
        "Pololu 12 V step-up module, fixed output, pins VIN GND VOUT",
        [("1", "VIN", "power_in", -10.16, 2.54, 0),
         ("3", "VOUT", "power_out", 10.16, 2.54, 180),
         ("2", "GND", "power_in", 0, -7.62, 90)], (7.62, 5.08)),
}

_lib_cache = {}


def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib == "FanCtrl3":
        s = [x for x in CUSTOM[name]]
    else:
        if lib not in _lib_cache:
            _lib_cache[lib] = sexp.parse(open(f"{KICAD}/symbols/{lib}.kicad_sym",
                                              encoding="utf-8").read())
        s = next(x for x in sexp.find_all(_lib_cache[lib], "symbol") if x[1] == name)
        assert not sexp.find(s, "extends"), lib_id
        s = list(s)
    s[1] = lib_id
    return s


def pins_of(sym):
    out = {}
    for p in sexp.walk(sym, "pin"):
        at = sexp.find(p, "at")
        num = sexp.find(p, "number")[1]
        ptype = str(p[1])
        out.setdefault(num, []).append((float(at[1]), float(at[2]), int(float(at[3])), ptype))
    return out


# --- placement on the sheet (A3, mm, 1.27 grid) --------------------------------
G = 1.27


def g(v):
    return round(v / G) * G


PLACE_PRO = {
    "U1": (88.9, 106.68),
    # limiter
    "U2": (190.5, 50.8), "C1": (152.4, 71.12), "R1": (223.52, 71.12),
    "R2": (223.52, 35.56), "R3": (152.4, 35.56),
    # boost
    "U3": (279.4, 50.8), "C2": (241.3, 71.12), "R4": (241.3, 35.56),
    "L1": (309.88, 35.56), "D1": (325.12, 43.18), "R5": (342.9, 50.8),
    "C3": (358.14, 50.8), "R6": (342.9, 71.12), "C4": (358.14, 76.2),
    "C5": (373.38, 76.2), "C6": (388.62, 76.2), "C7": (403.86, 76.2),
    # sensor
    "J4": (190.5, 132.08, 90), "R16": (167.64, 137.16),
}
for n in range(3):
    x0 = 180.34 + n * 83.82
    y0 = 200.66
    PLACE_PRO.update({
        f"Q{n+1}": (x0, y0), f"R{7+n}": (x0 - 17.78, y0 + 7.62),
        f"J{n+1}": (x0 + 50.8, y0 - 5.08, 90), f"R{10+n}": (x0 + 25.4, y0 - 20.32),
        f"R{13+n}": (x0 + 12.7, y0 - 20.32),
    })
for n in range(4):
    PLACE_PRO[f"H{n+1}"] = (330.2 + n * 15.24, 137.16)

PLACE_LITE = {
    "U1": (88.9, 106.68),
    "U2": (203.2, 50.8), "C1": (167.64, 71.12), "C2": (241.3, 71.12),
    "J4": (190.5, 132.08, 90), "R13": (167.64, 137.16),
    # current limiter (on the adapter under the Pico); pull-ups turned so +3V3 is on top
    "U3": (132.08, 50.8), "C3": (99.06, 50.8), "R14": (147.32, 71.12),
    "R15": (154.94, 27.94, 180), "R16": (109.22, 27.94, 180),
}
for n in range(3):
    x0 = 180.34 + n * 83.82
    y0 = 200.66
    r = 1 + 4 * n  # Rb, Rbe, Rs, Rpu
    PLACE_LITE.update({
        f"Q{n+1}": (x0, y0), f"R{r}": (x0 - 20.32, y0), f"R{r+1}": (x0 - 10.16, y0 + 15.24),
        f"R{r+2}": (x0 + 12.7, y0 - 20.32), f"R{r+3}": (x0 + 25.4, y0 - 20.32),
        f"J{n+1}": (x0 + 40.64, y0 - 5.08, 90),
    })
PLACE = PLACE_LITE if VARIANT == "lite" else PLACE_PRO

POWER_SYM = {"GND": "power:GND", "+3V3": "power:+3V3", "+12V": "power:+12V",
             "VBUS": "power:VBUS"}
STUB = 2.54


# longer stubs where a power symbol would sit on a neighbouring label
STUB_LONG = {("J1", "2"): 12.7, ("J2", "2"): 12.7, ("J3", "2"): 12.7, ("J4", "1"): 12.7}


def prop(name, value, x, y, hide=False, angle=0, justify=None):
    return [Sym("property"), name, value, [Sym("at"), x, y, angle],
            effects(hide=hide, justify=justify)]


def symbol_instance(lib_id, ref, value, fp, x, y, rot=0, extra=None, pin_nums=(),
                    power=False, key=None):
    u = uid(f"sym/{key or ref}")
    s = [Sym("symbol"), [Sym("lib_id"), lib_id], [Sym("at"), x, y, rot],
         [Sym("unit"), 1], [Sym("exclude_from_sim"), Sym("no")],
         [Sym("in_bom"), Sym("no") if power or ref.startswith("H") else Sym("yes")],
         [Sym("on_board"), Sym("no") if power else Sym("yes")],
         [Sym("dnp"), Sym("no")], [Sym("uuid"), u]]
    if power:
        s.append(prop("Reference", ref, x, y + 6, hide=True))
        # value text beyond the tip: GND points down at 0 deg, the rails point up
        if rot in (0, 180):
            below = (lib_id == "power:GND") == (rot == 0)
            vy = y + 5.08 if below else y - 3.81
        else:
            vy = y
        s.append(prop("Value", value, x, vy, hide=lib_id == "power:PWR_FLAG" and False))
    elif lib_id.startswith("FanCtrl3:"):
        s.append(prop("Reference", ref, x, y - 12.7))
        s.append(prop("Value", value, x, y - 10.16))
    elif lib_id.startswith("Connector_Generic:"):
        s.append(prop("Reference", ref, x - 6.35, y - 3.81, angle=rot, justify="right"))
        s.append(prop("Value", value, x - 6.35, y - 1.27, angle=rot, justify="right"))
    elif lib_id == "Device:D_Schottky":
        s.append(prop("Reference", ref, x, y - 3.81))
        s.append(prop("Value", value, x, y + 3.81))
    elif lib_id == "MCU_Module:RaspberryPi_Pico":
        s.append(prop("Reference", ref, x + 12.7, y - 43.18, justify="left"))
        s.append(prop("Value", value, x + 12.7, y - 40.64, justify="left"))
    else:
        s.append(prop("Reference", ref, x + 3.81, y - 1.27, justify="left"))
        s.append(prop("Value", value, x + 3.81, y + 1.27, justify="left"))
    s.append(prop("Footprint", fp, x, y, hide=True))
    s.append(prop("Datasheet", "~", x, y, hide=True))
    for k, v in (extra or {}).items():
        s.append(prop(k, v, x, y, hide=True))
    for pn in pin_nums:
        s.append([Sym("pin"), pn, [Sym("uuid"), uid(f"pin/{key or ref}/{pn}")]])
    s.append([Sym("instances"), [Sym("project"), NAME,
              [Sym("path"), f"/{ROOT_UUID}", [Sym("reference"), ref], [Sym("unit"), 1]]]])
    return s, u


def main():
    os.makedirs(OUT, exist_ok=True)
    today = date.today().isoformat()
    items = []
    used = {}
    for ref, p in D.PARTS.items():
        used[p["lib_id"]] = lib_symbol(p["lib_id"])
    for ps in sorted(set(POWER_SYM.values()) | {"power:PWR_FLAG"}):
        used[ps] = lib_symbol(ps)

    sym_uuids = {}
    nc_nets = {}
    pwr_n = [0]

    def power_symbol(net, x, y, outward):
        lib_id = POWER_SYM[net]
        pwr_n[0] += 1
        if net == "GND":
            rot = {"down": 0, "up": 180, "left": 270, "right": 90}[outward]
        else:
            rot = {"up": 0, "down": 180, "left": 90, "right": 270}[outward]
        s, _ = symbol_instance(lib_id, f"#PWR{pwr_n[0]:03d}", net, "", x, y, rot,
                               pin_nums=["1"], power=True, key=f"pwr{pwr_n[0]}")
        items.append(s)

    for ref, p in D.PARTS.items():
        pl = PLACE[ref]
        x, y, rot = g(pl[0]), g(pl[1]), (pl[2] if len(pl) > 2 else 0)
        lsym = used[p["lib_id"]]
        pins = pins_of(lsym)
        extra = {"TME": p["tme"]} if p["tme"] else {}
        if p["note"]:
            extra["Note"] = p["note"]
        s, u = symbol_instance(p["lib_id"], ref, p["value"], p["footprint"], x, y, rot,
                               extra=extra, pin_nums=sorted(pins, key=lambda k: (len(k), k)))
        items.append(s)
        sym_uuids[ref] = u
        done_points = set()
        for num, geoms in pins.items():
            net = p["pins"].get(num, "__missing__")
            for px, py, a, _ in geoms:
                if rot:
                    c, sn = {90: (0, 1), 180: (-1, 0), 270: (0, -1)}[rot]
                    px, py = px * c - py * sn, px * sn + py * c
                    a = (a + rot) % 360
                cx, cy = round(x + px, 2), round(y - py, 2)
                if (cx, cy) in done_points:
                    continue
                done_points.add((cx, cy))
                if net == "__missing__":
                    continue
                if net is None:
                    pname = next(sexp.find(q, "name")[1] for q in sexp.walk(lsym, "pin")
                                 if sexp.find(q, "number")[1] == num)
                    nc_nets[f"{ref}.{num}"] = f"unconnected-({ref}-{pname}-Pad{num})"
                    items.append([Sym("no_connect"), [Sym("at"), cx, cy],
                                  [Sym("uuid"), uid(f"nc/{ref}/{num}")]])
                    continue
                outward = {0: "left", 180: "right", 90: "down", 270: "up"}[a]
                st = STUB_LONG.get((ref, num), STUB)
                dx, dy = {"left": (-st, 0), "right": (st, 0),
                          "down": (0, st), "up": (0, -st)}[outward]
                ex, ey = round(cx + dx, 2), round(cy + dy, 2)
                items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), cx, cy], [Sym("xy"), ex, ey]],
                              [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                              [Sym("uuid"), uid(f"w/{ref}/{num}/{cx}/{cy}")]])
                if net in POWER_SYM:
                    vert = outward if outward in ("up", "down") else (
                        "down" if net == "GND" else "up")
                    power_symbol(net, ex, ey, vert)
                else:
                    ang, just = {"left": (180, "right bottom"), "right": (0, "left bottom"),
                                 "down": (270, "right bottom"), "up": (90, "left bottom")}[outward]
                    items.append([Sym("label"), net, [Sym("at"), ex, ey, ang],
                                  effects(justify=just), [Sym("uuid"), uid(f"l/{ref}/{num}/{cx}")]])

    # PWR_FLAGs: flag and matching power symbol share one point
    for i, net in enumerate(D.PWR_FLAGS):
        x, y = g(40.64 + i * 12.7), g(30.48)
        s, _ = symbol_instance("power:PWR_FLAG", f"#FLG{i+1:02d}", "PWR_FLAG", "", x, y,
                               pin_nums=["1"], power=True, key=f"flg{i}")
        items.append(s)
        items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), x, y], [Sym("xy"), x, y + 7.62]],
                      [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                      [Sym("uuid"), uid(f"flgw{i}")]])
        power_symbol(net, x, y + 7.62, "down")

    notes = D.NOTES if hasattr(D, "NOTES") else [
        (20.32, 170.18, "FanCtrl3 Pro - USB-only 3x 4-pin PWM fan controller\n"
                        "Power budget: 3 fans of up to 0.6 W each -> ~0.45 A from USB\n"
                        "PWM 25 kHz open-drain; tach pulled up to 3V3 on fan side, 10k series to GPIO\n"
                        "MCU dead -> gates pulled low -> fans run 100% (safe)\n"
                        "U2 limits boost input to 465-570 mA (R1 = 51k, TI eq. 1)\n"
                        "U3: TI LM27313 typical 5V->12V/250mA circuit, Vout = 1.23 x (1 + R5/R6) = 12.4 V"),
    ]
    for i, (x, y, t) in enumerate(notes):
        items.append([Sym("text"), t, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), x, y, 0],
                      [Sym("effects"), font(1.524), [Sym("justify"), Sym("left"), Sym("top")]],
                      [Sym("uuid"), uid(f"note{i}")]])

    sch = [Sym("kicad_sch"), [Sym("version"), Sym("20250114")],
           [Sym("generator"), "eeschema"], [Sym("generator_version"), "9.0"],
           [Sym("uuid"), ROOT_UUID], [Sym("paper"), "A3"],
           [Sym("title_block"), [Sym("title"), D.TITLE], [Sym("date"), today],
            [Sym("rev"), D.REV], [Sym("company"), "mikagosz"],
            [Sym("comment"), 1, "USB-powered 3-channel PWM fan controller for a Proxmox host"]],
           [Sym("lib_symbols")] + list(used.values())]
    sch += items
    sch += [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]],
            [Sym("embedded_fonts"), Sym("no")]]
    open(f"{OUT}/{NAME}.kicad_sch", "w", encoding="utf-8").write(sexp.dump(sch) + "\n")

    lib = [Sym("kicad_symbol_lib"), [Sym("version"), Sym("20241209")],
           [Sym("generator"), "fanctrl3-gen"], [Sym("generator_version"), "1.0"]]
    lib += [CUSTOM[k] for k in CUSTOM if f"FanCtrl3:{k}" in used]
    open(f"{OUT}/FanCtrl3.kicad_sym", "w", encoding="utf-8").write(sexp.dump(lib) + "\n")
    open(f"{OUT}/sym-lib-table", "w").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "FanCtrl3")(type "KiCad")'
        '(uri "${KIPRJMOD}/FanCtrl3.kicad_sym")(options "")(descr "FanCtrl3 custom symbols"))\n)\n')
    pro_file = f"{OUT}/{NAME}.kicad_pro"
    if not os.path.exists(pro_file):
        # Pro gets its project from pcbnew; a schematic-only variant needs one so that
        # KiCad reads the local sym-lib-table (the FanCtrl3 symbols)
        json.dump({"meta": {"filename": f"{NAME}.kicad_pro", "version": 3},
                   "sheets": [[ROOT_UUID, "Root"]]}, open(pro_file, "w"), indent=2)
    json.dump({"symbols": sym_uuids, "root": ROOT_UUID, "nc": nc_nets},
              open(f"{OUT}/.sym_uuids.json", "w"), indent=1)
    print("schematic:", len(items), "items")


if __name__ == "__main__":
    main()
