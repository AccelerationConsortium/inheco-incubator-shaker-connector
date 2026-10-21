# SiLA2 API — v0.2.0

Feature: `org.sissifeng/incubation/ShakerController` (custom application feature;
not a claim of SiLA certification or reuse of a normative shaker feature).
Address means configured floor; master DIP ID is a transport configuration item.

| Endpoint | Type | Parameters | Completion meaning |
|---|---|---|---|
| Simulation | Read property | — | true for in-memory simulator |
| ConfiguredAddresses | Read property | — | configured floors whose startup type/identity queries succeeded |
| ReadStatus | Command | Address | sequential live reports encoded as StatusJson |
| InitializeDevice | Observable command | Address | AID completed, REE=0 and RDS=0 confirmed; may move drawer and stops heater/shaker |
| OpenDrawer | Observable command | Address | RDS=1 confirmed |
| CloseDrawer | Observable command | Address | RDS=0 confirmed |
| ConfigureShaking | Command | Address, FrequencyHz, AmplitudeMm, PhaseDegrees | equal X/Y parameters read back; no automatic start |
| StartShaking | Observable command | Address | RSE=1 confirmed; steady speed not guaranteed |
| StopShaking | Observable command | Address | RSE=0 confirmed; known stack vibration timeout remains a commissioning item |
| SetTargetTemperature | Command | Address, TemperatureC | RTT target confirmed; actual temperature not awaited |
| EnableHeating | Command | Address | RHE=1 or 2 confirmed |
| DisableHeating | Command | Address | RHE=0 confirmed |
| WaitForTemperature | Observable command | Address, TargetC, ToleranceC, StableSeconds, TimeoutSeconds | main sensor within tolerance continuously for requested time; target/heating must remain unchanged |

WaitForTemperature intermediate response: MeasuredC. Final: FinalTemperatureC.
All temperature values are Celsius. Frequency 6.6–30.0 Hz, amplitude 0.0–3.0 mm,
resolution 0.1; phase integer 0–360 degrees. Temperature bounds are 0–80 C and
also limited by the configurable maximum and the device-reported RMT.
These are protocol constraints, not approval for every labware/load combination.
Application blocks normal mutations for any nonzero REF flag. Stops remain callable.

No generic raw-command endpoint, firmware update, calibration writes, error-flag
reset, labware-detection bypass, automatic initialization, broadcast control,
scheduler, or guaranteed software emergency stop is exposed.
Wait timeout/cancellation does not disable the heater. Service shutdown closes
communications only. No command or state is automatically replayed after restart.

## Native command mapping

| Application operation | Firmware commands |
|---|---|
| Identity | RTS, RFV0, RFV2 |
| State | RAT1, RTT, RHE, RDS, RSE, REE, REF, RFX1, RFY1, RAX1, RAY1 |
| Initialize | AID; verify REE and RDS |
| Drawer | AOD / ACD; verify RDS |
| Configure shaking | SSP; verify RAX0, RAY0, RFX0, RFY0, RPS0 |
| Start / stop shaking | ASE1 / ASE0; verify RSE |
| Temperature | RMT, STT; verify RTT |
| Heater | SHE1 / SHE0; verify RHE |

Source: INHECO FCS 900334-002 V1.5, August 2024. Refer to the linked manufacturer
manual for firmware errors and mechanical/thermal operating requirements.
