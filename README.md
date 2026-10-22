# INHECO Incubator Shaker MP · SiLA 2 connector

[![Offline tests](https://github.com/SissiFeng/inheco-incubator-shaker/actions/workflows/tests.yml/badge.svg)](https://github.com/SissiFeng/inheco-incubator-shaker/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Control an **INHECO Incubator Shaker MP (PN 7300013, device type 1)** through
SiLA 2, with a local browser panel, a hardware-free simulator and a native
USB virtual serial backend. Built with [UniteLabs CDK](https://docs.unitelabs.io/connector-development/getting-started/installation/).

An independent community implementation, not an official INHECO or UniteLabs
product or a claim of SiLA certification. **Simulation is the default.**

## What it does

- Select and control multiple configured floors through one USB stack connection.
- Read device identity, temperature, target temperature, drawer, shaker, heater,
  initialization and error status.
- Initialize explicitly, open/close the drawer, configure shaking and start/stop it.
- Set temperature, enable/disable heating and wait for a stable temperature.
- Operate through the browser panel or a SiLA 2 client.

**Validation status:** read-only identity and status communication has been
verified on macOS with two physical units running `IncShak_C_V3.50_04/2012`.
Physical drawer, shaking and heating acceptance tests remain pending.
A third floor returned `RTS: firmware error 14`; its integration remains unresolved.
Offline tests cover protocol handling, serial transport, discovery and the
browser-to-SiLA-to-simulator path. CI runs on Linux and macOS.

## Quick start: simulator and browser panel

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
git clone https://github.com/SissiFeng/inheco-incubator-shaker.git
cd inheco-incubator-shaker
uv sync --python 3.12 --extra ui --locked
uv run --extra ui shaker-ui --simulation --port 0
```

This starts a simulated SiLA server and opens the panel. If the browser does not
open, use the URL printed in the terminal. `--port 0` chooses a free web port.
The SiLA server uses `127.0.0.1:50052`; add `--sila-port 50053` if it is occupied.

The panel provides floor selection, live status, drawer controls, shaking and
heating controls, temperature stability waiting and command results. Its
**SIMULATION / HARDWARE** badge comes from the connected server.

## Connect physical hardware

### 1. Find the USB serial port

Use **Serial** when choosing a Connector Factory transport. USB is the physical
connection; the instrument exposes an FTDI virtual serial port (VCP). This
connector uses `pyserial` at **19200 baud, 8N1**, without a Windows vendor DLL.

Connect the existing stack's master USB connection and list ports:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools ports
```

On macOS a port typically looks like `/dev/cu.usbserial-1110`. Replace the example
port below with the one reported on your computer. Only one process can own it.

### 2. Discover identities without moving the device

Stop any running connector or vendor software that owns the serial port, then run:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools detect \
  --port /dev/cu.usbserial-1110
```

Allow up to 45 seconds. Discovery reports the master ID, floor identities and
reply device IDs. It does not initialize, move, heat or change configuration.
Use `--floors 0 1` to scan specific floors. Do not change wiring or DIP switches
to match an example.

### 3. Create and configure the connector

```sh
uv run config create --app unitelabs.inheco_incubator_shaker:create_app
```

Use the identities returned by discovery. This example is for **master 0,
floors 0 and 1, reply IDs 0 and 1**; other stacks may differ:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools configure \
  --hardware --port /dev/cu.usbserial-1110 \
  --master-id 0 --floors 0 1 --reply-ids 0 1
uv run python -m unitelabs.inheco_incubator_shaker.tools probe
```

`configure` validates and backs up `config.json`. `probe` reads identity and
status only. Include additional floors after their identities have been confirmed.

### 4. Start the server and panel

In the first terminal:

```sh
uv run connector start --app unitelabs.inheco_incubator_shaker:create_app
```

In a second terminal, from the same project directory:

```sh
uv run --extra ui shaker-ui --port 0
```

This panel attaches to the running SiLA server; it does not open the USB port.
Check the **HARDWARE** badge and selected floor before issuing commands.
Startup never initializes or moves the instrument. Initialization is explicit,
may close the drawer and stops heating/shaking; the panel requests confirmation.

Closing the browser, stopping the server or cancelling a temperature wait does
not guarantee that heating or shaking stops. Use the corresponding stop controls
and verify the reported state before ending a hardware session.

To switch the saved configuration back to simulation, stop the connector and run:

```sh
uv run python -m unitelabs.inheco_incubator_shaker.tools configure --simulation
```

## SiLA 2 interface

Custom feature: `org.sissifeng/incubation/ShakerController`.
`Address` is a configured floor, separate from the master transport ID.

| Command | Result / completion |
| --- | --- |
| `ReadStatus` | Sequential live readings as `StatusJson`; not an atomic snapshot |
| `InitializeDevice` | Initialization complete, no initialization error and drawer closed |
| `OpenDrawer` / `CloseDrawer` | Requested drawer state confirmed |
| `ConfigureShaking` | Equal X/Y settings read back; does not start shaking |
| `StartShaking` / `StopShaking` | Shaker enabled / fully stopped state confirmed |
| `SetTargetTemperature` | Target read back; actual temperature is not awaited |
| `EnableHeating` / `DisableHeating` | Heater state confirmed |
| `WaitForTemperature` | Main sensor stays within tolerance for the requested duration |

Read properties: `Simulation` and `ConfiguredAddresses`.
Shaking accepts 6.6–30.0 Hz, 0.0–3.0 mm (0.1 resolution) and integer phase
0–360 degrees. Temperature targets are limited by 0–80 °C, the configured
maximum and the device-reported limit. These bounds do not establish suitability
for a particular plate or load. Temperature waiting reports the main sensor,
not the liquid temperature; heater and target settings must remain unchanged.
An enabled shaker state does not establish steady speed or mixing performance.

The connector checks initialization, drawer and labware conditions before
starting shaking. Faults block normal mutations while stop commands remain
available. Operations are serialized per floor and serial transactions per stack.
An ambiguous transport timeout invalidates the session; writes are not blindly
retried and actions are not replayed after restart. Stop timing under stack
vibration still requires hardware validation. There is no software emergency-stop
guarantee, firmware update, calibration or raw-command endpoint.

A Python client example is included:

```sh
uv run python scripts/client_demo.py
uv run python scripts/client_demo.py --demo  # simulation only
```

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Web port already in use | Start the panel with `--port 0` |
| SiLA port 50052 already in use | Reuse the existing server, or choose another server port and point the client to it; embedded simulation accepts `--sila-port 50053` |
| Could not exclusively lock serial port | Stop the process owning USB; on macOS inspect it with `lsof /dev/cu.usbserial-1110` |
| `detect` or `probe` fails while server is running | Stop the server first; these tools access serial directly |
| Panel shows simulation | Check the server configuration and restart the intended server |
| A floor returns a firmware error | Preserve the error and check the manufacturer's documentation; verify that floor's identity before configuring it |

The panel binds to localhost. The default SiLA setup is local with TLS disabled;
remote deployment needs separate configuration and validation.

## Development

Python 3.12 is the tested development environment; package metadata requires
Python 3.10 or newer. No physical device is needed for the test suite.

```sh
uv sync --python 3.12 --extra test --extra dev --locked
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest -q
uv build
```

Keep SiLA features, device operations and wire transport separate. Include
regression coverage and readback semantics when changing device behavior.
For bug reports, include OS, firmware, floor mapping, expected behavior and a
minimal reproduction; remove identifying information from logs and distinguish
simulation results from hardware observations.

## References and license

The native implementation follows INHECO Firmware Command Set 900334-002,
V1.5 (August 2024). Manufacturer manuals and vendor software are not redistributed.

- [INHECO support and manuals](https://www.inheco.com/single-plate-incubator-shaker-support.html)
- [UniteLabs connector development](https://docs.unitelabs.io/connector-development/getting-started/installation/)
- [UniteLabs Connector Factory](https://gitlab.com/unitelabs/cdk/connector-factory)

Original code is released under the [MIT license](LICENSE). Dependencies retain
their own licenses; resolved versions are recorded in `uv.lock`.
