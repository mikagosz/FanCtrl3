#!/bin/zsh
# SERVICE on real firmware/main.py (unix MicroPython + tests/stubs/machine.py).
# The Pico watchdog cannot be stopped, so SERVICE must not drop to the REPL with the
# watchdog running: it leaves a flag file and resets; the next boot sees the flag,
# removes it, puts the fans at 100 % and stays at the REPL without a watchdog.
ROOT=${0:A:h:h}
tmp=$(mktemp -d)
cd $tmp
run() { MICROPYPATH=$ROOT/tests/stubs:$ROOT/firmware micropython $ROOT/firmware/main.py 2>&1; }
fail=0
check() { print -r -- "$2" | grep -q -- "$3" && echo "OK: $1" || { echo "MISSING: $1 ($3)"; fail=1; } }
check_not() { print -r -- "$2" | grep -q -- "$3" && { echo "UNEXPECTED: $1 ($3)"; fail=1; } || echo "OK: $1"; }

out1=$( (sleep 3.5; printf 'SERVICE\n'; sleep 1) | run )
check "SERVICE is acknowledged" "$out1" "OK SERVICE"
check "SERVICE resets the board" "$out1" "RESET"
[[ -e fanctrl3.service ]] && echo "OK: service flag written" || { echo "MISSING: service flag file"; fail=1; }

out2=$( (sleep 1) | run )
check "next boot enters service mode" "$out2" "service mode"
check_not "no watchdog in service mode" "$out2" "WDT START"
check "fans at 100 % in service mode (pins low)" "$out2" "EXIT pwm=\[(0, 0), (2, 0), (4, 0)\]"
[[ ! -e fanctrl3.service ]] && echo "OK: service flag removed" || { echo "MISSING: flag not removed"; fail=1; }

out3=$( (sleep 3.5; printf 'PING\n'; sleep 0.5) | run )
check "the boot after that is normal again" "$out3" "WDT START 8000"
cd /
rm $tmp/*(N) 2>/dev/null
rmdir $tmp
exit $fail
