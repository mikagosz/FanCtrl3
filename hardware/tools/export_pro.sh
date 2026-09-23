#!/bin/zsh
# Fabrication outputs for FanCtrl3 Pro: Gerbers + drill files -> ZIP for a PCB fab, BOM CSV
set -e
cd "${0:A:h}/.."
KC=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
O=pro/FanCtrl3-Pro
OUT=pro/fabrication
G=$OUT/gerbers
setopt pipefail
q() { grep -vi "fontconfig\|stdpbase\|memory leak" || true; }
rm -rf $G && mkdir -p $G
$KC pcb export gerbers --check-zones --subtract-soldermask \
  -l F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  -o $G $O.kicad_pcb 2>&1 | q
$KC pcb export drill --excellon-separate-th --generate-map --map-format pdf \
  -u mm -o $G/ $O.kicad_pcb 2>&1 | q
rm -f $OUT/FanCtrl3-Pro-gerbers.zip
(cd $G && zip -q -9 ../FanCtrl3-Pro-gerbers.zip *.g* *.drl)
$KC sch export bom --fields 'Reference,Value,Footprint,TME,${QUANTITY},Note' \
  --labels 'References,Value,Footprint,TME,Qty,Note' \
  --group-by 'Footprint,TME' --ref-range-delimiter '' \
  -o $OUT/FanCtrl3-Pro-BOM.csv $O.kicad_sch 2>&1 | q
$KC sch export pdf -o $O-schematic.pdf $O.kicad_sch 2>&1 | q
$KC sch export svg --exclude-drawing-sheet -o ../docs/images $O.kicad_sch 2>&1 | q
unzip -l $OUT/FanCtrl3-Pro-gerbers.zip | tail -n +4 | sed '$d' | sed '$d'
