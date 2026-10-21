# INHECO Incubator Shaker MP · SiLA 2 connector

[![Offline tests](https://github.com/SissiFeng/inheco-incubator-shaker/actions/workflows/tests.yml/badge.svg)](https://github.com/SissiFeng/inheco-incubator-shaker/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Version 0.3.0 targets PN 7300013 / device type 1. Native serial backend implemented;
**physical hardware and macOS commissioning pending**. Default is simulation.
An independent community implementation; not an official INHECO or UniteLabs product.
No physical-device validation is claimed.

## Documentation

- [API and completion semantics](docs/API.md)
- [Validation evidence and limitations](VALIDATION.md)
- [中文入门教程](docs/TUTORIAL.zh-CN.md) · [standalone HTML](docs/TUTORIAL.zh-CN.html) (download and open locally)
- [Contributing](CONTRIBUTING.md) · [Third-party references](THIRD_PARTY_NOTICES.md)

## Supported scope

Drawer open/close, explicit initialization, equal-axis shaking configuration,
shaker start/stop, temperature target, heater enable/disable and temperature stability
wait. Multiple configured floors share one serial connection. The current backend
accepts **Incubator Shaker MP / device type 1 only**.

**Choose Serial when using Connector Factory.** The physical cable is USB, but the
instrument exposes an FTDI virtual serial port (VCP): 19200 baud, 8N1. This connector
uses pyserial rather than raw USB endpoints. Linux and macOS offline tests pass in CI.
Physical hardware commissioning remains pending on both platforms.

## Browser control panel

The optional panel runs on your own computer and talks to the connector through
SiLA 2. It is not a hosted website and does not access the serial port directly.

One command starts a simulated connector and opens the panel:

```sh
uv run --extra ui shaker-ui --simulation
```

Open `http://127.0.0.1:8765` if the browser does not open automatically. Do not run
another connector on the same SiLA port at the same time. Use `--sila-port 50053`
when the default 50052 is occupied.

To control an already-running connector, start it using the configuration below,
then run this in another terminal:

```sh
uv run --extra ui shaker-ui
```

The panel includes floor selection, live readings, initialization, drawer controls,
shaking parameters, start/stop, heating controls, temperature stability waiting,
and execution results. **SIMULATION / HARDWARE** is read from the connected server.
Hardware initialization requires confirmation. Closing the panel does not stop
heating/shaking. Commands remain subject to connector interlocks. The panel binds
to localhost only; no remote access or cloud account is needed.

[Panel usage and feature map](docs/CONTROL_PANEL.md)

## Install and run simulation (uv + Python 3.12)

```sh
uv sync --python 3.12 --extra test --locked
uv run pytest -q
uv run config create --app unitelabs.inheco_incubator_shaker:create_app
uv run connector start --app unitelabs.inheco_incubator_shaker:create_app
```

In another terminal in this directory:

```sh
uv run python scripts/client_demo.py
uv run python scripts/client_demo.py --demo
```

The server defaults to localhost:50052, TLS off. Demo refuses hardware mode.
No mDNS discovery is required by the provided client. LAN/TLS deployment requires
separate configuration and validation; do not expose the local test port publicly.

## Hardware preparation (when device is available)

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools ports
```

Find the correct serial port, release it in other control software, then run
read-only identity discovery (no initialization, motion or heating commands):

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools detect --port /dev/cu.usbserial-EXAMPLE
```

Allow up to 45 seconds. This scans the master ID and reports each configured
floor's reply ID, type, firmware and serial number; it does not change config.json.

Identify the correct USB serial port, master DIP ID, floor identity and per-floor
reply DIP IDs. The example below is **not** an assertion that your master ID is 2:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools configure --hardware --port /dev/cu.usbserial-EXAMPLE --master-id 2 --floors 0 1 2 --reply-ids 2 2 2
uv run python -m unitelabs.inheco_incubator_shaker.tools probe
```

Probe reads only. Startup never initializes or moves hardware. Stop the server
before running probe, and release the port in existing vendor software first.
Only the master should own the USB stack connection; do not alter existing
stack wiring or DIP settings to fit an example configuration.

Then start the server as above. Use an explicitly chosen SiLA client operation
for hardware commissioning. InitializeDevice may close the drawer and stops
heating/shaking. A simulation demo is not an approved hardware test sequence.

Restore simulation with:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools configure --simulation
```

## Implementation

Separate SiLA feature, device operations, shared serial transport, framing/parser,
and simulator. One transaction in flight per physical stack; one operation lock
per floor. Transport uses 19200/8N1 via pyserial, not a Windows vendor DLL.
No PyLabRobot or Omnibus dependency. Code independently implements the public
INHECO protocol; follows the UniteLabs CDK structure/API rather than claiming
an unmodified factory-generated project.

Timeouts poison the session to prevent stale replies from matching later commands.
No automatic motion retry, state replay, or initialization after reconnect.
Service shutdown and client disconnection do not guarantee physical stopping.
Read [API.md](docs/API.md) and [VALIDATION.md](VALIDATION.md) for exact scope and residual limitations.

Sources:
- https://docs.unitelabs.io/connector-development/getting-started/installation/
- https://gitlab.com/unitelabs/cdk/connector-factory
- https://www.inheco.com/single-plate-incubator-shaker-support.html
- https://www.inheco.com/data/pdf/single-plate-incubators-firmware-command-202408-0522-1050-58.pdf

## Development and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for lint, tests, builds and tutorial rendering.
Original code and documentation are available under the [MIT license](LICENSE).


If the web port is occupied, let the OS choose a free port:

```sh
uv run --extra ui shaker-ui --port 0
```

The browser opens the assigned URL; the same URL is printed in the terminal.
This changes only the HTTP panel port, not the SiLA server port.
