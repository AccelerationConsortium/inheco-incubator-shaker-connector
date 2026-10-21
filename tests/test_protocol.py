import asyncio
import json

import pytest

from unitelabs.inheco_incubator_shaker.io.errors import (
    ConnectorError,
    DeviceError,
    DeviceInterlockError,
    UnknownAddressError,
)
from unitelabs.inheco_incubator_shaker.io.protocol import InhecoProtocol
from unitelabs.inheco_incubator_shaker.io.simulator import SimulationBus


async def make():
    b = SimulationBus([0, 1, 2])
    p = InhecoProtocol(b, [0, 1, 2])
    await p.startup()
    return p, b


async def test_startup_read_only():
    p, b = await make()
    assert all(not s["initialized"] for s in b.states.values())
    with pytest.raises(DeviceInterlockError):
        await p.start_shaking(0)


async def test_isolation_interlocks_and_roundtrip():
    p, b = await make()
    await p.initialize(0)
    await p.initialize(1)
    await p.drawer(0, True)
    with pytest.raises(DeviceInterlockError):
        await p.start_shaking(0)
    await p.configure_shaking(1, 10.0, 1.0, 90)
    await p.start_shaking(1)
    with pytest.raises(DeviceInterlockError):
        await p.drawer(1, True)
    await p.stop_shaking(1)
    await p.drawer(1, True)
    assert json.loads(await p.status(2))["drawer_status"] == 0


@pytest.mark.parametrize(
    "freq,amp,phase",
    [
        (0, 1, 90),
        (30.1, 1, 90),
        (10.01, 1, 90),
        (10, 3.1, 90),
        (10, 1, 361),
        (10, 1, 1.5),
        (float("nan"), 1, 90),
    ],
)
async def test_invalid_shaking(freq, amp, phase):
    p, b = await make()
    await p.initialize(0)
    before = await p.status(0)
    with pytest.raises(ValueError):
        await p.configure_shaking(0, freq, amp, phase)
    assert await p.status(0) == before


async def test_temperature():
    p, b = await make()
    await p.initialize(0)
    for t in [-1, 80.1, 25.01, float("nan")]:
        with pytest.raises(ValueError):
            await p.set_temperature(0, t)
    await p.set_temperature(0, 37.0)
    await p.heating(0, True)
    assert b.states[0]["target"] == 370
    assert b.states[0]["heater"] == 1
    await p.heating(0, False)
    assert b.states[0]["heater"] == 0
    with pytest.raises(UnknownAddressError):
        await p.initialize(3)


async def test_parallel_floors():
    p, b = await make()
    await asyncio.gather(*(p.initialize(a) for a in range(3)))
    await asyncio.gather(*(p.configure_shaking(a, 10.0 + a, 1.0, 90) for a in range(3)))
    assert [s["fx"] for s in b.states.values()] == [100, 110, 120]


async def test_wait_temperature():
    p, b = await make()
    await p.initialize(0)
    await p.heating(0, True)
    assert await p.wait_temperature(0, 25, 0.5, 0, 0.1) == 25
    await p.set_temperature(0, 37)
    with pytest.raises(ConnectorError, match="timed out"):
        await p.wait_temperature(0, 37, 0.5, 0, 0.03)
    with pytest.raises(DeviceInterlockError):
        await p.wait_temperature(0, 25, 0.5, 0, 0.1)


async def test_reset_retry_read_only():
    class ResetBus(SimulationBus):
        calls = 0

        async def query(self, f, c):
            if c == "RTS":
                self.calls += 1
                if self.calls == 1:
                    raise DeviceError(c, 1)
            return await super().query(f, c)

    b = ResetBus([0])
    await InhecoProtocol(b, [0]).startup()
    assert b.calls == 2


async def test_cdk_registration():
    from unitelabs.inheco_incubator_shaker import create_app
    from unitelabs.inheco_incubator_shaker.config import InhecoConfig

    g = create_app(InhecoConfig())
    assert await anext(g) is not None
    await g.aclose()


async def test_hardware_requires_explicit_config():
    from unitelabs.inheco_incubator_shaker import create_app
    from unitelabs.inheco_incubator_shaker.config import InhecoConfig

    with pytest.raises(ValueError, match="explicit"):
        await anext(create_app(InhecoConfig(simulation=False)))
