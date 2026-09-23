#!/bin/zsh
# Copies the FanCtrl3 firmware onto a Pico that already runs MicroPython.
# Needs mpremote:  pipx install mpremote   (or: pip install --user mpremote)
# The firmware ignores Ctrl-C (so the host cannot stop the fans by accident), so
# mpremote only gets in during the first 3 s after power-up - or after
# `fanctl send SERVICE`.
set -e
cd "${0:A:h}"
mpremote connect auto cp logic.py :logic.py + cp main.py :main.py + reset
