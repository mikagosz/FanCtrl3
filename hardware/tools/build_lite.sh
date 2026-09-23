#!/bin/zsh
# FanCtrl3 Lite: perfboard (placement, wiring, checks, SVG, connection table, enclosure
# geometry) + schematic from the same data (ERC, PDF)
set -e
cd "${0:A:h}/.."
KC=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
setopt pipefail
q() { grep -vi "fontconfig\|stdpbase\|memory leak" || true; }
python3 tools/gen_lite.py lite
python3 tools/gen_sch.py lite
$KC sch erc --severity-all -o lite/FanCtrl3-Lite-erc.rpt lite/FanCtrl3-Lite.kicad_sch 2>&1 | q
$KC sch export pdf -o lite/FanCtrl3-Lite-schematic.pdf lite/FanCtrl3-Lite.kicad_sch 2>&1 | q
$KC sch export svg --exclude-drawing-sheet -o ../docs/images lite/FanCtrl3-Lite.kicad_sch 2>&1 | q
