# Contributing to FanCtrl3

Thank you for your interest in FanCtrl3. Ideas, improvements and questions are
genuinely welcome — especially from anyone who builds one.

## Get in touch

- **Issues** on this repository — bug reports, questions, build reports, ideas.
- **E-mail:** support@fractal8.eu — if you have an idea or a solution you would
  rather discuss first, or anything that does not fit an issue.

Useful things to share:

- **Build reports.** Which variant, which fans, what worked, what did not.
  Measurements are gold: current drawn from USB at 100 %, the 12 V rail under load,
  tach readings, temperatures.
- **Circuit or layout improvements.** A better part, a cheaper source, a footprint
  that does not match the real part.
- **Other hosts and sensors.** The host side currently reads Intel `coretemp`;
  support for other temperature sources (for example AMD `k10temp`) is a natural
  next step.

## Pull requests

1. For anything larger than a typo, open an issue first so we can agree on the
   approach.
2. Hardware changes go into the design files —
   [`hardware/tools/design_pro.py`](hardware/tools/design_pro.py) or
   [`hardware/tools/design_lite.py`](hardware/tools/design_lite.py) — never into the
   generated KiCad files. Run the matching build script and commit the regenerated
   outputs together with the change. See [docs/development.md](docs/development.md).
3. Firmware and host changes: run `tests/run_all.sh`; all tests must pass. New
   behaviour in `firmware/logic.py` comes with a test in `tests/test_logic.py`.
4. The host side stays on the Python standard library.

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE) of this project.
