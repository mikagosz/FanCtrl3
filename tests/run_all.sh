#!/bin/zsh
# Every FanCtrl3 test (firmware + host) that runs without hardware. Stops at the first failure.
cd "${0:A:h}/.."
set -e
setopt pipefail
echo "== logic, CPython";      python3 tests/test_logic.py | tail -1
echo "== logic, MicroPython";  micropython tests/test_logic.py | tail -1
echo "== main.py on stubs";    ./tests/test_main_smoke.sh | tail -2
echo "== SERVICE and service mode"
out=$(./tests/test_main_service.sh) || { print -r -- "$out"; exit 1; }
echo "$(print -r -- "$out" | grep -c '^OK') checks OK"
echo "== host <-> simulator";  python3 tests/test_e2e.py | grep -v "^   \|^  [0-9 ]\{3\}%"
