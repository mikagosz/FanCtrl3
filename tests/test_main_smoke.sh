#!/bin/zsh
# Runs the real firmware/main.py under unix MicroPython with tests/stubs/machine.py.
# Expects: service-window banner, replies to commands, a control step, inverted PWM.
cd "${0:A:h}/.."
out=$( (sleep 3.5; printf 'PING\nTEMP 50\nSET 3 80\n'; sleep 1.5; printf 'STATUS\n'; sleep 3) \
  | MICROPYPATH=tests/stubs:firmware micropython firmware/main.py 2>&1)
print -r -- "$out"
fail=0
for want in "FanCtrl3 $(sed -n 's/^VERSION = "\(.*\)"/\1/p' firmware/logic.py) start" "PONG" "STAT mode=auto cpu=50.0" "f3=" "END"; do
  print -r -- "$out" | grep -q "$want" || { echo "MISSING: $want"; fail=1; }
done
# fan 3 manual 80 % -> pin high only 20 % of the time: (100-80) * 65535/100 = 13107
print -r -- "$out" | grep -q "(4, 13107)" && echo "OK: channel 3 PWM inverted (80% fan = 13107/65535 on the pin)" || { echo "MISSING: inverted PWM on channel 3"; fail=1; }
print -r -- "$out" | grep -q "freq=25000 wdt=8000" && echo "OK: 25 kHz, watchdog 8 s" || { echo "MISSING: 25 kHz / watchdog"; fail=1; }
exit $fail
