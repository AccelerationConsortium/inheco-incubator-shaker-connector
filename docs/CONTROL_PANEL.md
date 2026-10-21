# Local control panel

## Start without hardware

From the project directory:

```sh
uv run --extra ui shaker-ui --simulation
```

The panel opens at **http://127.0.0.1:8765**. This command also starts a simulated
SiLA connector on port 50052. Both stop when you press Control+C in the terminal.
If 50052 is already in use, stop the existing connector or choose another port:

```sh
uv run --extra ui shaker-ui --simulation --sila-port 50053
```

For an existing connector (simulation or hardware), start the connector first and
run `uv run --extra ui shaker-ui`. Add `--no-browser` to avoid opening a browser.
`--port` changes the panel HTTP port; `--sila-port` chooses the SiLA server port.
The panel connects only to a connector running on the same computer.

## Features

The custom **ShakerController** SiLA feature exposes **11 commands and 2 properties**.
The CDK also provides its standard core service features.

| Panel control | SiLA endpoint | Meaning |
|---|---|---|
| Mode badge | Simulation | Shows real server mode, not a user-selected label |
| Floor buttons | ConfiguredAddresses | Switches the selected floor |
| Status cards / Device details | ReadStatus | Sequential device sensor/status reads |
| Initialize | InitializeDevice | Initializes device; can move drawer and stops heating/shaking |
| Drawer Open / Close | OpenDrawer / CloseDrawer | Confirms position readback |
| Apply settings | ConfigureShaking | Equal X/Y frequency and amplitude with phase |
| Start / Stop shaking | StartShaking / StopShaking | Confirms enabled or stopped status |
| Set target | SetTargetTemperature | Confirms target setpoint, not measured temperature |
| Enable / Disable heater | EnableHeating / DisableHeating | Confirms heater enable state |
| Start waiting | WaitForTemperature | Waits for main sensor tolerance/stability |

## First simulated workflow

1. Confirm the **SIMULATION** badge and choose Floor 00.
2. Click **Initialize**.
3. Enter 10 Hz, 1 mm, 90 degrees; click **Apply settings**.
4. Click **Start shaking**; wait for Activity to report success and Shaker to read Running.
5. Click **Stop shaking**, then Open and Close the drawer.
6. Set temperature target **25 C**, click Set target, then Enable heater.
7. Expand Wait for temperature; use tolerance 0.5 C, stable time 1 s, timeout 10 s.
8. Click Start waiting and read the result in Activity; disable heating afterward.

The simulator remains at 25 C. A wait at 37 C will not complete successfully unless
it times out or heating/target is changed, causing the wait to fail.

## Hardware behavior

Use the existing commissioning process to configure serial port, DIP and floor
mapping. The panel does not configure firmware or bypass labware detection.
Select the floor and verify **HARDWARE** before an operation. Initialize shows a
confirmation describing its physical effects; the HTTP backend also requires this
confirmation for hardware initialization.

A submitted operation is not yet a successful operation. Activity shows **running**,
**succeeded**, or **failed**, with the connector's reported error. State readings
refresh about every 1.5 seconds. Unavailable readings disable controls and mark the
last reading stale. Stop shaking and Disable heater remain available while a
temperature wait is running; they are normal connector calls, not a guaranteed
emergency stop. Closing the page/process does not guarantee stopping the instrument.

## Architecture and scope

Browser → localhost HTTP bridge → SiLA/gRPC client → connector → device backend.
There is no direct browser-to-USB path. Simulation and hardware use the same
SiLA endpoints. The web component is optional (`ui` extra); connector-only
installations do not require aiohttp. No CDN, login, remote hosting or external
font is used. The HTTP server binds to 127.0.0.1 and accepts same-origin JSON
command requests with a page-session token. This is a local operator tool, not a
multi-user authenticated remote control service.

Activity is a bounded in-memory history (up to 100 operations), cleared on restart.
Temperature waits run asynchronously; ordinary overlapping actions on the same
floor are rejected while stop controls remain available. The existing device and
serial interlocks remain authoritative. Long-term audit logging, remote access and
cross-device workflow orchestration are outside this panel's scope.


If the web port is occupied, let the OS choose a free port:

```sh
uv run --extra ui shaker-ui --port 0
```

The browser opens the assigned URL; the same URL is printed in the terminal.
This changes only the HTTP panel port, not the SiLA server port.


## USB port ownership

Only the connector owns the USB serial port. The panel connects to SiLA, so it
may run alongside the connector. The `detect` and `probe` tools open the serial
port themselves: stop the connector before running either, then restart it after
the diagnostic finishes. On macOS, `lsof /dev/cu.usbserial-EXAMPLE` identifies the
port owner without changing any process or device state. An exclusive-lock error
means the diagnostic has not started; it is not a new instrument error.
