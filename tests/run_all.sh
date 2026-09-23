#!/bin/zsh
# Every FanCtrl3 test (firmware + host) that runs without hardware.
cd "${0:A:h}/.."
set -e
echo "== logic, CPython";      python3 tests/test_logic.py | tail -1
echo "== logic, MicroPython";  micropython tests/test_logic.py | tail -1
echo "== main.py on stubs";    ./tests/test_main_smoke.sh | tail -2
echo "== host <-> simulator";  python3 tests/test_e2e.py | grep -v "^   \|^  [0-9 ]\{3\}%"
