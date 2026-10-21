# Validation — 0.3.0 / 2026-10-21

Status: software implementation with offline validation; physical commissioning pending.

## Evidence actually obtained

- Fresh `uv sync --python 3.12 --extra test --locked` succeeded on Linux/Python 3.12.
- The v0.2.0 connector baseline passed GitHub Actions on both `ubuntu-latest` and `macos-latest`: [run 39643043672](https://github.com/SissiFeng/inheco-incubator-shaker/actions/runs/39643043672).
- Project editable package build succeeded.
- `uv run pytest -q`: **41 passed**.
- Ruff undefined/unused-symbol checks passed; source/tests/examples formatted.
- CDK generated a fresh configuration; helper changed simulation config and read-only probe succeeded.
- Native serial framing matches the manufacturer's published RFV CRC test vector.
- Fragmented frames, missing trailers, wrong reply IDs, stray LF and firmware error 20 tested.
- Simulator tests cover floor isolation, interlocks, configuration readback, temperature wait and input bounds.
- Fault tests verify transport poisoning after timeout, no blind write retry and cancellation-safe bus ownership.
- POSIX pseudo-terminal integration exercised actual pyserial open/write/read and fragmented device responses.
- gRPC integration connected the real SiLA client to CDK, exercised operations and checked defined failure responses.
- CLI server plus supplied `client_demo.py --demo` completed in separate subprocesses in one network namespace.
- Chinese tutorial rendered to self-contained HTML with 20 linked chapters.

Local TCP client/server tests passed. Multicast discovery was unavailable in the
development environment and is not part of the validated connection path.

## Local panel validation

- Four HTTP → real SiLA/gRPC → simulator tests cover all panel operations,
  failure propagation, unknown inputs, same-origin/token checks and hardware-init confirmation.
- A running temperature wait rejects overlapping normal operations while allowing heater disable.
- Panel JavaScript syntax checked with Node; HTML verified present in the wheel.
- The installed `shaker-ui --simulation --no-browser` command passed a subprocess smoke test for startup, HTML, server mode, floors and command submission.
- Browser layout and the temperature-wait disclosure were inspected against read-only simulation fixtures. The managed preview cannot launch the Python runtime; actual HTTP/gRPC operation tests ran separately.
- The localhost web panel has not been tested against physical hardware.

## Not yet established

- macOS serial enumeration/driver compatibility or installation.
- Actual master/slave DIP reply IDs, firmware and per-floor serial-number mapping.
- Real initialization, drawer motion, labware detection, thermal or mixing performance.
- Exact response quirks on these particular 2021 Rev.04 instruments.
- Multi-unit ASE0 stop latency; manufacturer notes stack vibration can delay completion.
- Device state after USB loss, power cycle, process crash or long unattended operation.
- TLS, LAN discovery, remote deployment or production endurance.

## Important behavioral boundaries

- Only device type 1 is accepted. Equal X/Y shaking parameters supported.
- ReadStatus is sequential reads, not an atomic hardware snapshot.
- InitializeDevice can close drawer and stop heater/shaker. It is never automatic at startup.
- StartShaking confirms enable state, not steady frequency or validated mixing.
- Temperature wait uses the main device sensor, not sample liquid temperature.
- A timeout or cancelled temperature wait does not automatically disable heating.
- Communication failure blocks further transactions until reconnect/restart; previous motion outcome may be unknown.
- No auto-replay, auto-clearing error flags, firmware changes, calibration writes,
  labware detection bypass, broadcast stop or emergency-stop guarantee.
- Shutdown closes communication only, without silently changing instrument state.

Commissioning must record actual OS, port, firmware, floor IDs, identity, successful
operations and fault/recovery behavior before declaring this hardware validated.
