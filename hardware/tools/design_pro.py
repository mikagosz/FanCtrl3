"""FanCtrl3 Pro - single source of truth for schematic and PCB.

Every part lists its symbol, footprint and pin -> net mapping. gen_sch.py and
gen_pcb.py both read this file, so schematic and board cannot drift apart.
"""

R0805 = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
C0805 = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
C1206 = "Capacitor_SMD:C_1206_3216Metric_Pad1.33x1.80mm_HandSolder"
FAN_FP = "Connector_Molex:Molex_KK-254_AE-6410-04A_1x04_P2.54mm_Vertical"

TITLE = "FanCtrl3 Pro"
REV = "1.0"

# ref: (lib_id, value, footprint, {pin: net}, extra fields)
PARTS = {}


def part(ref, lib_id, value, fp, pins, tme="", note=""):
    PARTS[ref] = dict(lib_id=lib_id, value=value, footprint=fp, pins=pins,
                      tme=tme, note=note)


# --- MCU ------------------------------------------------------------------
# One GPIO pair per fan, in board order, so fan tracks never cross:
# GP0/GP1 fan 1, GP2/GP3 fan 2, GP4/GP5 fan 3 (PWM on slice 0/1/2 channel A).
pico = {
    "1": "PWM1", "2": "TACH1", "4": "PWM2",
    "5": "TACH2", "6": "PWM3", "7": "TACH3",
    "9": "DQ", "10": "FAULT", "11": "FAN_EN",
    "36": "+3V3", "40": "VBUS",
}
for p in ("3", "8", "13", "18", "23", "28", "38"):
    pico[p] = "GND"
for p in ("12", "14", "15", "16", "17", "19", "20", "21", "22", "24", "25",
          "26", "27", "29", "30", "31", "32", "33", "34", "35", "37", "39"):
    pico[p] = None  # no-connect (33 = AGND: ADC unused)
part("U1", "MCU_Module:RaspberryPi_Pico", "Raspberry Pi Pico",
     "Module:RaspberryPi_Pico_SMD_HandSolder", pico, tme="SC0915")

# --- USB current limiter ---------------------------------------------------
part("U2", "FanCtrl3:TPS2553DBV", "TPS2553DBV",
     "Package_TO_SOT_SMD:SOT-23-6_Handsoldering",
     {"1": "VBUS", "2": "GND", "3": "FAN_EN", "4": "FAULT", "5": "ILIM",
      "6": "+5V_FAN"}, tme="TPS2553DBVR")
part("C1", "Device:C", "100n", C0805, {"1": "VBUS", "2": "GND"},
     tme="0805B104K500CT")
part("R1", "Device:R", "51k", R0805, {"1": "ILIM", "2": "GND"},
     tme="SMD0805-51K-1%", note="current limit 465-570 mA")
part("R2", "Device:R", "10k", R0805, {"1": "+3V3", "2": "FAULT"},
     tme="SMD0805-10K-1%")
part("R3", "Device:R", "100k", R0805, {"1": "+3V3", "2": "FAN_EN"},
     tme="SMD0805-100K-1%", note="fans powered by default")

# --- 5 V -> 12 V boost ------------------------------------------------------
part("U3", "FanCtrl3:LM27313XMF", "LM27313XMF",
     "Package_TO_SOT_SMD:SOT-23-5_HandSoldering",
     {"1": "SW", "2": "GND", "3": "FB", "4": "SHDN", "5": "+5V_FAN"},
     tme="LM27313XMF/NOPB")
part("C2", "Device:C", "10u 25V", C1206, {"1": "+5V_FAN", "2": "GND"},
     tme="TMK316AB7106KLHT")
part("R4", "Device:R", "51k", R0805, {"1": "+5V_FAN", "2": "SHDN"},
     tme="SMD0805-51K-1%")
part("L1", "Device:L", "10u", "Inductor_SMD:L_Changjiang_FNR5040S",
     {"1": "+5V_FAN", "2": "SW"}, tme="DJNR5040-100-S")
part("D1", "Device:D_Schottky", "SS14", "Diode_SMD:D_SMA_Handsoldering",
     {"1": "+12V", "2": "SW"}, tme="SS14-FAI")
part("R5", "Device:R", "91k", R0805, {"1": "+12V", "2": "FB"},
     tme="SMD0805-91K-1%", note="Vout = 1.23 * (1 + 91/10) = 12.4 V")
part("R6", "Device:R", "10k", R0805, {"1": "FB", "2": "GND"},
     tme="SMD0805-10K-1%")
part("C3", "Device:C", "220p", C0805, {"1": "+12V", "2": "FB"},
     tme="0805N221J500CT", note="feed-forward, fz ~ 8 kHz")
part("C4", "Device:C", "10u 25V", C1206, {"1": "+12V", "2": "GND"},
     tme="TMK316AB7106KLHT")
part("C5", "Device:C", "10u 25V", C1206, {"1": "+12V", "2": "GND"},
     tme="TMK316AB7106KLHT")
part("C6", "Device:C_Polarized", "100u 25V",
     "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", {"1": "+12V", "2": "GND"},
     tme="CE-100/25PHT-Y")
part("C7", "Device:C", "100n", C0805, {"1": "+12V", "2": "GND"},
     tme="0805B104K500CT")

# --- fan channels -----------------------------------------------------------
# 4-pin PC fan: 1 GND, 2 +12V, 3 TACH (open collector), 4 PWM (pulled up in fan)
for n, (rq, rpu, rs) in enumerate(((7, 10, 13), (8, 11, 14), (9, 12, 15)), 1):
    part(f"Q{n}", "Transistor_FET:Q_NMOS_GSD", "2N7002",
         "Package_TO_SOT_SMD:SOT-23_Handsoldering",
         {"1": f"PWM{n}", "2": "GND", "3": f"FAN{n}_PWM"}, tme="2N7002-DIO")
    part(f"R{rq}", "Device:R", "100k", R0805, {"1": f"PWM{n}", "2": "GND"},
         tme="SMD0805-100K-1%", note="MCU dead -> MOSFET off -> fan 100%")
    part(f"R{rpu}", "Device:R", "4k7", R0805,
         {"1": "+3V3", "2": f"FAN{n}_TACH"}, tme="SMD0805-4K7-1%",
         note="pull-up on fan side")
    part(f"R{rs}", "Device:R", "10k", R0805,
         {"1": f"FAN{n}_TACH", "2": f"TACH{n}"}, tme="SMD0805-10K-1%",
         note="limits current if fan tach is pulled up to 12 V")
    part(f"J{n}", "Connector_Generic:Conn_01x04", f"FAN{n}", FAN_FP,
         {"1": "GND", "2": "+12V", "3": f"FAN{n}_TACH", "4": f"FAN{n}_PWM"},
         tme="MX-47053-1000")

# --- ambient sensor (DS18B20 probe on screw terminal) ------------------------
part("J4", "Connector_Generic:Conn_01x03", "DS18B20",
     "TerminalBlock:TerminalBlock_Xinya_XY308-2.54-3P_1x03_P2.54mm_Horizontal",
     {"1": "+3V3", "2": "DQ", "3": "GND"}, tme="DG308-2.54-03P",
     note="probe: red VDD, yellow DQ, black GND")
part("R16", "Device:R", "4k7", R0805, {"1": "+3V3", "2": "DQ"},
     tme="SMD0805-4K7-1%")

# --- mechanics ----------------------------------------------------------------
for n in range(1, 5):
    part(f"H{n}", "Mechanical:MountingHole", "M3",
         "MountingHole:MountingHole_3.2mm_M3", {})

# Nets that need a PWR_FLAG in the schematic (driven only by passives).
PWR_FLAGS = ["+12V"]

POWER_NETS = {"GND", "VBUS", "+5V_FAN", "SW", "+12V"}
