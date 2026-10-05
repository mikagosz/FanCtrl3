#!/usr/bin/env bash
# FanCtrl3 enclosure: 2 variants x (base, lid) -> STL, collision check against the
# component bodies, PNG preview. Needs OpenSCAD with the Manifold backend (2024.x or newer).
set -e
cd "$(dirname "$0")/../enclosure"
SCAD=FanCtrl3-enclosure.scad
mkdir -p stl preview
for v in pro lite; do
  for p in base lid; do
    openscad --backend=Manifold -D "variant=\"$v\"" -D "part=\"$p\"" -o stl/FanCtrl3-$v-$p.stl $SCAD 2>&1 \
      | grep -E "WARNING|ERROR|Volumes|Simple|Genus" | sed "s/^/  $v-$p: /"
  done
  # the intersection of the enclosure and the component bodies must be empty
  out=$(openscad --backend=Manifold -D "variant=\"$v\"" -D 'part="collisions"' -o ${TMPDIR:-/tmp}/fanctrl3-collisions-$v.stl $SCAD 2>&1 || true)
  if printf '%s\n' "$out" | grep -q "top level object is empty"; then echo "  $v: collisions 0"
  else echo "  $v: COLLISION"; printf '%s\n' "$out" | tail -3; fi
  openscad --backend=Manifold -D "variant=\"$v\"" -D 'part="assembly"' --imgsize=1600,1100 \
    --camera=0,0,0,55,0,25,0 --viewall --autocenter --colorscheme=Tomorrow -o preview/$v-assembly.png $SCAD >/dev/null 2>&1
done
ls -la stl
