#!/bin/zsh
# Full rebuild of FanCtrl3 Pro: schematic -> ERC -> board -> route -> DRC
set -e
cd "${0:A:h}/.."
# KiCad's bundled Python (it has the pcbnew module)
KPY=${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3}
KC=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
O=pro/FanCtrl3-Pro
setopt pipefail
q() { grep -vi "fontconfig\|stdpbase\|memory leak" || true; }
python3 tools/gen_sch.py pro
$KC sch erc --severity-all -o $O-erc.rpt $O.kicad_sch 2>&1 | q
$KPY tools/gen_pcb.py place $O 2>&1 | q
$KPY tools/gen_pcb.py geom $O 2>&1 | q
python3 tools/router.py $O | tail -3
$KPY tools/gen_pcb.py finish $O 2>&1 | q
$KC pcb drc --severity-all --schematic-parity -o $O-drc.rpt $O.kicad_pcb 2>&1 | q
grep -E "^\*\*|^\[" $O-drc.rpt | sort | uniq -c | sort -rn | head -30
