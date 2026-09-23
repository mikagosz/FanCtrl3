#!/bin/zsh
# render.sh <board.kicad_pcb> <out.png> [layers]
KC=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
L=${3:-"F.Cu,B.Cu,F.SilkS,Edge.Cuts,F.CrtYd"}
T=${2%.png}
$KC pcb export pdf --layers "$L" --mode-single --drill-shape-opt 2 -o "$T.pdf" "$1" >/dev/null 2>&1
pdftoppm -r 300 -singlefile -png "$T.pdf" "$T" && rm "$T.pdf"
# crop to the board (page origin 100,100 mm; board 90x60 mm; 300 dpi = 11.811 px/mm)
sips -c $(( 70 * 11811 / 1000 )) $(( 100 * 11811 / 1000 )) --cropOffset $(( 95 * 11811 / 1000 )) $(( 95 * 11811 / 1000 )) "$T.png" >/dev/null
