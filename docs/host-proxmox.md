# FanCtrl3 on a Proxmox VE host

This document covers the host side of FanCtrl3: the `fanctl` tool and daemon, its udev
rule and its systemd service. For the controller firmware and the full serial protocol,
see [firmware.md](firmware.md).

> [!NOTE]
> **Status:** the hardware has not been tested yet. The firmware logic and the host daemon
> pass automated tests against a simulator. Hardware testing is coming soon.

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Installed files](#installed-files)
- [The fanctl command](#the-fanctl-command)
- [Calibrating the minimum duty](#calibrating-the-minimum-duty)
- [Troubleshooting](#troubleshooting)
- [Uninstalling](#uninstalling)

## How it works

The host runs one small service, `fanctl daemon` ([`host/fanctl`](../host/fanctl)). Every
5 seconds it:

1. reads the CPU package temperature from the kernel's hwmon interface,
2. sends it to the controller as `TEMP <t>`,
3. requests `STATUS` and keeps the reply for `fanctl status`.

**The fan curve runs in the controller, not on the host.** The host only supplies the
CPU temperature. If the host stops sending it for any reason (the daemon crashes, the
host hangs or reboots), the controller keeps driving the fans on its own:

- **Clean stop.** When the daemon receives SIGTERM (`systemctl stop`, host shutdown), it
  sends `BYE`. The controller then rests at 20 % instead of treating the silence as a
  failure.
- **Silence without `BYE`.** After 30 s without a temperature, the controller switches
  to failsafe and runs all fans at 100 %.
- **Daemon restart.** The service restarts the daemon automatically. On connecting it
  sends `HELLO`; when temperatures arrive again, the controller returns to the curve.

A host restart therefore never stops the cooling.

The daemon owns the serial port. The other `fanctl` commands talk to the daemon through
a Unix socket. When the daemon is not running, they open the serial port directly.

## Requirements

- **Proxmox VE** (Debian). `fanctl` itself runs on any Linux host; `install.sh` needs
  systemd and udev. Run the installer and the `fanctl` commands as root.
- **Python 3, standard library only.** No other packages are needed.
- **An Intel CPU.** The daemon reads the CPU temperature from the hwmon device named
  **`coretemp`**, using the sensor labelled **`Package id 0`**. If that device has no
  sensor with this label, the daemon uses the hottest reading of the device. Only the
  first `coretemp` device found is read. The device is found by name every time,
  because hwmon numbers can change between boots.

> [!WARNING]
> **Only Intel CPUs (`coretemp`) are supported for now.** Other temperature sensors,
> such as AMD **`k10temp`**, are not supported yet. Without a `coretemp` device the
> daemon sends no temperature to the controller, so the controller runs the fans at
> 100 % (failsafe).

To check that the host has a `coretemp` device:

```sh
cat /sys/class/hwmon/hwmon*/name
```

## Installation

1. Flash the controller as described in [firmware.md](firmware.md) and connect it to
   the host over USB.
2. Copy the [`host/`](../host/) directory to the host.
3. On the host, run the installer as root:

   ```sh
   sh install.sh
   ```

[`host/install.sh`](../host/install.sh) performs these steps:

| Step | Command |
|---|---|
| 1. Install the tool | `install -m 755 fanctl /usr/local/bin/fanctl` |
| 2. Install the udev rule | `install -m 644 99-fanctl.rules /etc/udev/rules.d/99-fanctl.rules` |
| 3. Install the systemd unit | `install -m 644 fanctl.service /etc/systemd/system/fanctl.service` |
| 4. Load the rule and apply it to existing serial devices | `udevadm control --reload` and `udevadm trigger --subsystem-match=tty` |
| 5. Load the unit, then enable and start the service | `systemctl daemon-reload` and `systemctl enable --now fanctl` |
| 6. Show the result | The first lines of `systemctl status fanctl`, then `ls -l /dev/fanctl` |

If the controller is not plugged in, the last step prints:

```text
No /dev/fanctl - the controller is not plugged in (the daemon is waiting).
```

This is not an error. The daemon connects as soon as the device appears.

When the installation is complete, check the controller:

```sh
fanctl status
```

## Installed files

| File | Source | Purpose |
|---|---|---|
| `/usr/local/bin/fanctl` | [`host/fanctl`](../host/fanctl) | The daemon and the command-line tool |
| `/etc/udev/rules.d/99-fanctl.rules` | [`host/99-fanctl.rules`](../host/99-fanctl.rules) | Stable device name `/dev/fanctl` |
| `/etc/systemd/system/fanctl.service` | [`host/fanctl.service`](../host/fanctl.service) | Runs `fanctl daemon` as a service |

While it runs, the daemon also creates the Unix socket `/run/fanctl.sock` (mode `0660`).
It removes the socket when it stops cleanly.

### udev rule

```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0005", SYMLINK+="fanctl", MODE="0660", ENV{ID_MM_DEVICE_IGNORE}="1"
```

- USB vendor `2e8a`, product `0005` is a Raspberry Pi Pico running MicroPython.
- The rule creates the symlink **`/dev/fanctl`**. The underlying `/dev/ttyACMx` name can
  change when the USB device is reconnected, but the symlink always points to the
  controller.
- `MODE="0660"` restricts access to the device's owner and group.
- `ENV{ID_MM_DEVICE_IGNORE}="1"` tells ModemManager to leave the port alone, so it does
  not probe the controller as a modem.

### systemd service

| Setting | Value | Effect |
|---|---|---|
| `ExecStart` | `/usr/local/bin/fanctl daemon` | Runs the daemon |
| `After` | `systemd-udevd.service` | Starts after udev |
| `KillSignal` | `SIGTERM` | On stop, the daemon sends `BYE` and the controller rests at 20 % instead of going to failsafe |
| `TimeoutStopSec` | `10` | Time allowed for a clean stop |
| `Restart` | `always` | Restarts the daemon whenever it exits |
| `RestartSec` | `5` | Waits 5 s before a restart |
| `WantedBy` | `multi-user.target` | Starts at boot |

The daemon logs to standard output, so its messages go to the systemd journal:

```sh
journalctl -u fanctl -f
```

## The fanctl command

```text
fanctl [--device PATH] [--socket PATH] [--reply-timeout S] {daemon,status,send,calibrate} ...
```

Global options go **before** the subcommand.

| Option | Default | Description |
|---|---|---|
| `--device` | `/dev/fanctl`, or the `FANCTL_DEVICE` environment variable | Serial device of the controller |
| `--socket` | `/run/fanctl.sock`, or the `FANCTL_SOCKET` environment variable | Unix socket of the daemon |
| `--reply-timeout` | `2.0` | Seconds to wait for a reply from the controller |

### fanctl daemon

Runs the service loop. You normally start it through systemd, not by hand.

| Option | Default | Description |
|---|---|---|
| `--interval` | `5` | Seconds between updates |
| `--hwmon` | `/sys/class/hwmon` | hwmon directory (used by the tests) |

Behaviour:

- **Startup.** The daemon logs `fanctl daemon: /dev/fanctl, every 5 s`.
- **Controller missing.** If the device cannot be opened, the daemon logs
  `no controller at /dev/fanctl (<reason>) - waiting` once and retries at every
  interval.
- **Controller found.** The daemon logs `connected to /dev/fanctl`, sends `VER` and logs
  the reply, for example `VER FanCtrl3 <version>`, then sends `HELLO`. `HELLO` takes the
  controller out of rest mode left by an earlier `BYE`, so a daemon that cannot read a
  temperature still ends in failsafe (100 %) instead of leaving the fans at 20 %.
- **Controller lost.** The daemon logs `lost the controller: <reason>` and returns to
  waiting.
- **No temperature.** If no `coretemp` reading is found, the daemon does not send
  `TEMP` and logs this at every interval.
- **Controller messages.** `ALARM`, `INFO` and `ERR` lines from the controller are
  written to the log. The daemon also keeps the 20 most recent ones, with timestamps,
  for `fanctl status`.
- **Stopping.** On SIGTERM or SIGINT the daemon sends `BYE`, logs the reply
  (`BYE -> OK REST`), removes the socket and logs `fanctl daemon: stopped`.

### fanctl status

Shows the controller's state in readable form.

If the daemon is running, the command shows the status the daemon collected at its last
update (at most one interval old), followed by the five most recent controller
messages. If the daemon is running but the controller is not connected, it prints
`the daemon is running, but the controller is not connected`. If the daemon is not
running, the command asks the controller directly.

Example:

```text
mode:        curve
CPU:         54.0 °C (3 s ago)
ambient:     27.5 °C
USB overload: no
fan 1:        54%    728 rpm
fan 2:        54%    728 rpm (manual)
fan 3:        54%    728 rpm
recent messages:
  <HH:MM:SS> <message>
```

| Line | Source ([STAT fields](firmware.md#the-stat-line)) |
|---|---|
| `mode` | `curve` (`auto`), `start (waiting for the first temperature)`, `rest after BYE` or `FAILSAFE 100% (no temperature)` |
| `CPU` | Last temperature sent to the controller and its age. Shows `-` if none has been sent. |
| `ambient` | DS18B20 reading. Shows `-` if there is no probe or no valid reading. |
| `USB overload` | `YES` while the TPS2553 power switch reports a fault |
| `fan N` | Output duty and measured speed. `(manual)` marks a fan set with `SET`. |

### fanctl send

Sends one raw protocol command and prints the controller's reply. See
[firmware.md](firmware.md#serial-protocol) for the full command list.

```sh
fanctl send PING                         # PONG
fanctl send SET 1 40                     # OK   (fan 1 manual at 40 %)
fanctl send SET 1 AUTO                   # OK
fanctl send CURVE 35:20 50:35 65:60 75:100
fanctl send SAVE                         # OK SAVE
fanctl send CONF                         # CONF {"curve": [[35, 20], ...], ...}
```

If the controller does not reply within the reply timeout, the command prints `None`.
If the daemon is running but has no controller connected, it exits with
`error: no controller`.

### fanctl calibrate

```text
fanctl calibrate [N] [--settle S] [--margin M]
```

| Argument | Default | Description |
|---|---|---|
| `N` | all fans | Fan to calibrate: 1, 2 or 3 |
| `--settle` | `6` | Seconds to wait at each step before reading the speed |
| `--margin` | `5` | Percentage points added above the lowest working duty |

See the next section for details.

## Calibrating the minimum duty

A fan can stop turning when its PWM duty is too low. The controller never drives a fan
below its `min_duty` (default 20 %). `fanctl calibrate` measures the real minimum of each fan
and stores it on the controller.

Run it with the daemon active, so the controller keeps receiving temperatures during
the measurement:

```sh
fanctl calibrate        # all three fans
fanctl calibrate 2      # fan 2 only
```

For each fan, the tool:

1. reads the current configuration with `CONF`, to keep the old minimum,
2. sets the fan's minimum to 0 (`MIN n 0`) so the controller allows low duties,
3. steps the fan's duty down from 60 % to 0 % in 5 % steps (`SET n <duty>`):
   - waits until the controller's output reaches the requested duty (up to 30 s,
     because the controller ramps down at 2 % per second),
   - waits `--settle` seconds, then reads the fan speed,
   - stops at the first step where the fan reports 0 rpm,
4. returns the fan to automatic control (`SET n AUTO`),
5. sets the minimum to the lowest duty at which the fan still turned, plus the margin
   (at most 100 %).

When all fans are done, the tool sends `SAVE` so the new minimums survive a restart.

If the fan does not turn even at 60 %, or the measurement is interrupted, the tool
restores the fan's previous minimum.

Example output:

```text
fan 1: stepping the duty down 60% -> 0% in 5% steps, 6 s per step
   60% -> <rpm> rpm
   55% -> <rpm> rpm
   ...
   20% -> <rpm> rpm
   15% -> 0 rpm
  lowest working duty: 20% -> MIN 25% (margin 5)
save: OK SAVE
```

For a fan that does not turn:

```text
  fan 3 does not spin even at 60% - is it connected? MIN stays at 20%
```

> [!NOTE]
> The controller's safety rules still apply during calibration. If the ambient
> temperature is at or above 40 °C, or the controller is in failsafe, it raises the duty
> regardless of the requested value, and the result does not reflect the fan's real
> minimum.

> [!NOTE]
> `SAVE` stores the controller's complete configuration, including any other unsaved
> changes made with `CURVE`, `MIN` or `ENABLE`.

## Troubleshooting

### The daemon logs "no controller at /dev/fanctl … - waiting"

The daemon cannot open `/dev/fanctl`. It retries at every interval and connects
automatically when the device appears.

- Check that the controller is connected: `ls -l /dev/fanctl`.
- The udev rule matches only a Pico running MicroPython (USB `2e8a:0005`). A Pico in
  BOOTSEL mode, or one without MicroPython, does not get the `/dev/fanctl` link.
- If you installed the rule while the controller was already connected, run
  `udevadm trigger --subsystem-match=tty` or reconnect the controller.

### All fans run at 100 % and the mode is FAILSAFE

The controller has not received a temperature for more than 30 s.

- Check that the service is running: `systemctl status fanctl`.
- Check the log with `journalctl -u fanctl`. If it shows
  `no coretemp reading - not sending TEMP`, the host has no `coretemp` hwmon device.
  Only Intel CPUs are supported for now (see [Requirements](#requirements)).
- As soon as temperatures arrive again, the controller returns to the curve.

A controller that has received `BYE` stays in rest mode (20 %) until the next
temperature, and does not switch to failsafe.

### The fans stay at 20 % after the service was stopped

This is expected. On `systemctl stop fanctl` the daemon sends `BYE`, and the controller
stays at rest duty until it receives a temperature again.

### A second Pico is connected to the same host

The udev rule matches every Pico running MicroPython. If the host has more than one,
tie the rule to the controller's USB serial number. Read the serial number:

```sh
udevadm info -a -n /dev/ttyACM0 | grep serial
```

Then add `ATTRS{serial}=="<serial>"` to `/etc/udev/rules.d/99-fanctl.rules`:

```text
SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0005", ATTRS{serial}=="<serial>", SYMLINK+="fanctl", MODE="0660", ENV{ID_MM_DEVICE_IGNORE}="1"
```

Reload the rule with `udevadm control --reload` and
`udevadm trigger --subsystem-match=tty`.

### A header without a fan raises stall alarms

Disable stall detection for that header and save the change:

```sh
fanctl send ENABLE 3 0
fanctl send SAVE
```

### Updating the controller firmware

The daemon holds the serial port open. Stop it with `systemctl stop fanctl` before you
use `mpremote`, then follow [firmware.md](firmware.md#copying-the-firmware). Start the
daemon again with `systemctl start fanctl`.

## Uninstalling

`install.sh` puts these three files in place:

- `/usr/local/bin/fanctl`
- `/etc/udev/rules.d/99-fanctl.rules`
- `/etc/systemd/system/fanctl.service`

To remove them, run as root:

```sh
systemctl disable --now fanctl
rm /etc/systemd/system/fanctl.service
rm /etc/udev/rules.d/99-fanctl.rules
rm /usr/local/bin/fanctl
systemctl daemon-reload
udevadm control --reload
```

The daemon removes `/run/fanctl.sock` when it stops. The `/dev/fanctl` symlink disappears
the next time you disconnect the controller.

> [!WARNING]
> Stopping the service sends `BYE`, so the controller keeps the fans at rest duty (20 %)
> with no further temperature input. After a power cycle without a host daemon, the
> controller starts at 60 % and switches to failsafe (100 %) after 30 s.

The configuration saved on the controller (`/fanctrl3.json`) is not affected.
