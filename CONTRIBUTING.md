# Contributing to FanCtrl3

Thank you for your interest in FanCtrl3. Ideas, improvements and questions are
genuinely welcome — especially from anyone who builds one.

FanCtrl3 is a hobby project, developed in spare time. Replies and updates may take
a while — thank you for your patience.

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
- **Other hosts and sensors.** The host side reads Intel `coretemp` and AMD
  `k10temp` / `zenpower`. Reports from AMD hosts are especially welcome, as are
  other temperature sources.

## Versions

`VERSION` in [`firmware/logic.py`](firmware/logic.py) is the version of the project
and what `fanctl send VER` reports. It changes only with the firmware, host software
or hardware — changes to the documentation alone go into the `Unreleased` section of
the [CHANGELOG](CHANGELOG.md) and ship with the next release. Every release gets a
`vX.Y.Z` tag and a GitHub release.

## Pull requests

1. For anything larger than a typo, open an issue first so we can agree on the
   approach.
2. Hardware changes go into the design files —
   [`hardware/tools/design_pro.py`](hardware/tools/design_pro.py) or
   [`hardware/tools/design_lite.py`](hardware/tools/design_lite.py) — never into the
   generated KiCad files. Run the matching build script and commit the regenerated
   outputs together with the change. See [docs/development.md](docs/development.md).
3. Firmware and host changes: run `tests/run_all.sh`; all tests must pass (GitHub
   Actions runs it on every pull request). New behaviour in `firmware/logic.py` comes
   with a test in `tests/test_logic.py`, new behaviour in `host/fanctl` with one in
   `tests/test_host.py` or `tests/test_e2e.py`.
4. The host side stays on the Python standard library.

By contributing you agree that your contribution is licensed under the
[MIT License](LICENSE) of this project.
