# Changelog

## 0.2.0 — 2026-10-21

- Native serial bus, CRC framing, incremental response parser and vendor error handling.
- Separate master DIP ID / per-floor reply IDs; read-only startup identity checks.
- Explicit initialization, state-confirmed drawer/shaker/heater operations.
- Frequency/amplitude/phase configuration replaces provisional rpm interface.
- Observable operations and temperature stability wait with intermediate readings.
- Stateful command simulator, local setup/probe tools, simulation-only SiLA demo.
- Unit, fault/cancellation, gRPC and OS pseudo-terminal integration tests.
- Lockfile and detailed Chinese beginner tutorial. Hardware commissioning pending.

## 0.1.0

CDK simulation starter. No hardware backend.
