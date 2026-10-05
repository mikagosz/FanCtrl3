#!/usr/bin/env bash
# Every FanCtrl3 test (firmware + host) that runs without hardware. Stops at the first failure.
cd "$(dirname "$0")/.."
set -e
set -o pipefail
echo "== logic, CPython";      python3 tests/test_logic.py | tail -1
echo "== logic, MicroPython";  micropython tests/test_logic.py | tail -1
echo "== main.py on stubs";    ./tests/test_main_smoke.sh | tail -2
echo "== SERVICE and service mode"
out=$(./tests/test_main_service.sh) || { printf '%s\n' "$out"; exit 1; }
echo "$(printf '%s\n' "$out" | grep -c '^OK') checks OK"
echo "== host side";           python3 tests/test_host.py | tail -1
echo "== host <-> simulator";  python3 tests/test_e2e.py | grep -v "^   \|^  [0-9 ]\{3\}%"
