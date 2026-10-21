"""High-level operations shared by real transport and simulator."""

import asyncio
import json
import math
import time

from .errors import (
    ConnectorError,
    DeviceError,
    DeviceInterlockError,
    ProtocolError,
    UnknownAddressError,
)


def tenths(value, low, high, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} must be finite")
    if not low <= value <= high or abs(value * 10 - round(value * 10)) > 1e-7:
        raise ValueError(f"{label} must be {low}..{high} in steps of 0.1")
    return round(value * 10)


class InhecoProtocol:
    def __init__(self, bus, floors, max_temperature_c=80.0):
        if (
            not floors
            or len(set(floors)) != len(floors)
            or any(type(f) is not int or not 0 <= f <= 5 for f in floors)
        ):
            raise ValueError("Floors must be unique integers 0..5")
        self.bus = bus
        self.floors = list(floors)
        self.locks = {f: asyncio.Lock() for f in floors}
        self.max_temperature_c = max_temperature_c
        self.identities = {}

    @property
    def simulation(self):
        return self.bus.simulation

    def check(self, floor):
        if type(floor) is not int or floor not in self.locks:
            raise UnknownAddressError(f"Unconfigured floor {floor}")

    async def integer(self, floor, command):
        data = await self.bus.query(floor, command)
        try:
            return int(data)
        except ValueError as exc:
            raise ProtocolError(f"{command}: expected integer, got {data!r}") from exc

    async def startup(self):
        # The reset response is accepted once per floor, only for a read-only probe.
        # Never silently retry a control or initialize on startup.
        for f in self.floors:
            try:
                kind = await self.integer(f, "RTS")
            except DeviceError as exc:
                if exc.code != 1:
                    raise
                kind = await self.integer(f, "RTS")
            if kind != 1:
                raise DeviceInterlockError(
                    f"Floor {f}: type {kind}; this connector targets Shaker MP (type 1)"
                )
            self.identities[f] = dict(
                firmware=await self.bus.query(f, "RFV0"),
                serial_number=await self.bus.query(f, "RFV2"),
                device_type=kind,
            )

    async def ready(self, f):
        if await self.integer(f, "REE") & 1:
            raise DeviceInterlockError(
                "InitializeDevice explicitly before control; it can move the drawer"
            )
        if await self.integer(f, "REF"):
            raise DeviceInterlockError(
                "Device reports error flags; inspect ReadStatus before continuing"
            )

    async def wait_value(self, f, command, expected, timeout=12.0):
        deadline = time.monotonic() + timeout
        while True:
            if await self.integer(f, command) == expected:
                return
            if time.monotonic() >= deadline:
                raise ConnectorError(
                    f"{command}: state did not reach {expected}; inspect instrument"
                )
            await asyncio.sleep(0.1)

    async def initialize(self, f):
        self.check(f)
        async with self.locks[f]:
            await self.bus.query(f, "AID")
            await self.wait_value(f, "REE", 0)
            await self.wait_value(f, "RDS", 0)

    async def status(self, f):
        self.check(f)
        async with self.locks[f]:
            values = dict(
                floor=f, simulation=self.simulation, **self.identities.get(f, {})
            )
            for key, cmd, scale in [
                ("temperature_c", "RAT1", 10),
                ("target_temperature_c", "RTT", 10),
                ("heater_status", "RHE", 1),
                ("drawer_status", "RDS", 1),
                ("shaker_status", "RSE", 1),
                ("initialization_status", "REE", 1),
                ("error_flags", "REF", 1),
                ("frequency_x_hz", "RFX1", 10),
                ("frequency_y_hz", "RFY1", 10),
                ("amplitude_x_mm", "RAX1", 10),
                ("amplitude_y_mm", "RAY1", 10),
            ]:
                value = await self.integer(f, cmd)
                values[key] = value if scale == 1 else value / scale
            # Sequential reads, not an atomic hardware snapshot.
            values["snapshot_kind"] = "sequential_reads"
            return json.dumps(values, sort_keys=True)

    async def drawer(self, f, opened):
        self.check(f)
        async with self.locks[f]:
            await self.ready(f)
            if await self.integer(f, "RSE") != 0:
                raise DeviceInterlockError(
                    "Wait until shaker is fully stopped before drawer movement"
                )
            await self.bus.query(f, "AOD" if opened else "ACD")
            await self.wait_value(f, "RDS", int(opened))

    async def configure_shaking(self, f, frequency_hz, amplitude_mm, phase_degrees):
        self.check(f)
        frequency = tenths(frequency_hz, 6.6, 30.0, "Frequency Hz")
        amplitude = tenths(amplitude_mm, 0.0, 3.0, "Amplitude mm")
        if type(phase_degrees) is not int or not 0 <= phase_degrees <= 360:
            raise ValueError("Phase must be an integer 0..360 degrees")
        async with self.locks[f]:
            await self.ready(f)
            if await self.integer(f, "RSE") != 0:
                raise DeviceInterlockError("Stop shaker before changing parameters")
            await self.bus.query(
                f, f"SSP{amplitude},{amplitude},{frequency},{frequency},{phase_degrees}"
            )
            for cmd, expected in [
                ("RAX0", amplitude),
                ("RAY0", amplitude),
                ("RFX0", frequency),
                ("RFY0", frequency),
                ("RPS0", phase_degrees),
            ]:
                await self.wait_value(f, cmd, expected)

    async def start_shaking(self, f):
        self.check(f)
        async with self.locks[f]:
            await self.ready(f)
            if await self.integer(f, "RDS") != 0:
                raise DeviceInterlockError("Close drawer first")
            if await self.integer(f, "RLW") != 1:
                raise DeviceInterlockError(
                    "Labware not detected; detection bypass is not exposed"
                )
            await self.bus.query(f, "ASE1")
            await self.wait_value(f, "RSE", 1)
            # Enabled status is confirmed; steady frequency / physical mixing not guaranteed.

    async def stop_shaking(self, f):
        self.check(f)
        async with self.locks[f]:
            await self.bus.query(f, "ASE0")
            await self.wait_value(f, "RSE", 0)

    async def set_temperature(self, f, temperature_c):
        self.check(f)
        target = tenths(temperature_c, 0.0, self.max_temperature_c, "Temperature C")
        async with self.locks[f]:
            await self.ready(f)
            if target > await self.integer(f, "RMT"):
                raise ValueError("Target exceeds device-reported maximum temperature")
            await self.bus.query(f, f"STT{target}")
            await self.wait_value(f, "RTT", target)

    async def heating(self, f, enabled):
        self.check(f)
        async with self.locks[f]:
            if enabled:
                await self.ready(f)
                if await self.integer(f, "RTT") > self.max_temperature_c * 10:
                    raise DeviceInterlockError(
                        "Existing temperature target exceeds configured limit"
                    )
            await self.bus.query(f, f"SHE{int(enabled)}")
            if enabled:
                if await self.integer(f, "RHE") not in (1, 2):
                    raise DeviceInterlockError("Heating enable not confirmed")
            else:
                await self.wait_value(f, "RHE", 0)

    async def wait_temperature(
        self, f, target_c, tolerance_c, stable_seconds, timeout_seconds, callback=None
    ):
        self.check(f)
        tenths(target_c, 0, self.max_temperature_c, "Target C")
        if not all(
            isinstance(v, (int, float)) and math.isfinite(v)
            for v in [tolerance_c, stable_seconds, timeout_seconds]
        ):
            raise ValueError("Wait parameters must be finite")
        if (
            not 0.1 <= tolerance_c <= 10
            or not 0 <= stable_seconds <= timeout_seconds
            or not 0 < timeout_seconds <= 86400
        ):
            raise ValueError(
                "Invalid tolerance, stability duration, or timeout (max 86400 s)"
            )
        start = time.monotonic()
        stable_since = None
        while time.monotonic() - start < timeout_seconds:
            async with self.locks[f]:
                await self.ready(f)
                actual_target = await self.integer(f, "RTT") / 10
                enabled = await self.integer(f, "RHE")
                measured = await self.integer(f, "RAT1") / 10
            if abs(actual_target - target_c) > 0.05 or enabled not in (1, 2):
                raise DeviceInterlockError(
                    "Heating stopped or target changed while waiting"
                )
            now = time.monotonic()
            stable_since = (
                (stable_since if stable_since is not None else now)
                if abs(measured - target_c) <= tolerance_c
                else None
            )
            if callback:
                callback(measured)
            if stable_since is not None and now - stable_since >= stable_seconds:
                return measured
            await asyncio.sleep(min(1.0, max(0.01, timeout_seconds - (now - start))))
        raise ConnectorError(
            "Temperature wait timed out; heater state is unchanged, inspect instrument"
        )
