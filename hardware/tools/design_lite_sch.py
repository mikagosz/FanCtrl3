"""FanCtrl3 Lite in the shape gen_sch.py expects (like design_pro.py).

Nothing is typed in twice: parts, values, TME symbols and every pin -> net come
from design_lite.py, the file the perfboard drawing is generated from. This only
adds the KiCad symbol and footprint for each kind of part.
"""
import design_lite as T

# nets do not depend on where the channels sit on the perfboard - any placement will do
T.build(tuple(c[0] for c in T.CHANNEL_CHOICES))

TITLE = T.TITLE
REV = T.REV

R_FP = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical"
SYMBOL = {  # kind -> (lib_id, footprint)
    "pico": ("MCU_Module:RaspberryPi_Pico", "Module:RaspberryPi_Pico_Common_THT"),
    "pololu": ("FanCtrl3:U3V16F12", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"),
    "res": ("Device:R", R_FP),
    "to92": ("Transistor_BJT:Q_NPN_CBE", "Package_TO_SOT_THT:TO-92_Inline"),
    "fan": ("Connector_Generic:Conn_01x04",
            "Connector_Molex:Molex_KK-254_AE-6410-04A_1x04_P2.54mm_Vertical"),
    "terminal": ("Connector_Generic:Conn_01x03",
                 "TerminalBlock:TerminalBlock_Xinya_XY308-2.54-3P_1x03_P2.54mm_Horizontal"),
    # TPS2553 on the SparkFun BOB-00717: DIP hole n = SOT-23-6 pin n
    "adapter6": ("FanCtrl3:TPS2553DBV", "Package_DIP:DIP-6_W7.62mm"),
    "res_flat": ("Device:R", "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal"),
    # AVX SR20: 5.08 x 3.175 mm, leads 2.54 mm - the nearest KiCad disc footprint
    "cap_small": ("Device:C", "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm"),
}
CAP_FP = {"47u 25V": "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm",
          "100u 25V": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm"}
PIN_NUMBER = {  # perfboard pad name -> symbol pin number
    "cap": {"+": "1", "-": "2"},
    "pololu": {"VIN": "1", "GND": "2", "VOUT": "3"},
    "to92": {"C": "1", "B": "2", "E": "3"},
}

PARTS = {}
for ref, p in T.PARTS.items():
    kind = p["kind"]
    lib_id, fp = ("Device:C_Polarized", CAP_FP[p["value"]]) if kind == "cap" else SYMBOL[kind]
    pins = {}
    for pad, (_, net) in p["pads"].items():
        pins[PIN_NUMBER.get(kind, {}).get(pad, pad)] = None if net.startswith("NC_") else net
    PARTS[ref] = dict(lib_id=lib_id, value="BC547B" if kind == "to92" else p["value"],
                      footprint=fp, pins=pins, tme=p["tme"], note=p["note"])

# Nets that need a PWR_FLAG in the schematic (driven only by passives)
PWR_FLAGS = []
POWER_NETS = {"GND", "VBUS", "+12V"}

NOTES = [
    (20.32, 170.18,
     "FanCtrl3 Lite - the same controller built from modules on a PC-3 perfboard\n"
     "Same pinout and firmware as Pro: GP0/1 fan 1, GP2/3 fan 2, GP4/5 fan 3, GP6 DS18B20\n"
     "U2 Pololu U3V16F12: fixed 12 V; C1 >= 33 uF at its input as Pololu recommends\n"
     "PWM: NPN open collector - GPIO high = transistor on = fan slower;\n"
     "MCU dead -> base pulled to GND by 10k -> fan runs 100% (safe)\n"
     "Tach pulled up to 3V3 on fan side, 10k series to GPIO\n"
     "U3 TPS2553 on a SparkFun BOB-00717 adapter under the Pico, as on Pro:\n"
     "limit 465-570 mA (R14 = 51k), ~FAULT -> GP7, EN <- GP8 (R16 keeps it on)\n"
     "Pico on raw VBUS; only the 12 V converter is behind the limiter\n"
     "Wiring on the board: lite/FanCtrl3-Lite-perfboard.svg + FanCtrl3-Lite-wiring.md"),
]
