import json

import pytest
from sila.client import Client, ClientConfig, DefinedExecutionError

from unitelabs.inheco_incubator_shaker import create_app
from unitelabs.inheco_incubator_shaker.config import InhecoConfig


async def test_real_grpc_client_simulated_device():
    config = InhecoConfig(discovery=None)
    config.sila_server.port = 0
    gen = create_app(config)
    app = await anext(gen)
    client = None
    try:
        await app.start()
        port = int(app.sila_server._address.rsplit(":", 1)[1])
        client = Client(
            ClientConfig(
                hostname="127.0.0.1", port=port, tls=False, default_timeout=3000
            )
        )
        await client.open()
        feature = next(
            f for f in client.features.values() if f.identifier == "ShakerController"
        )
        assert await feature.properties["Simulation"].read() is True

        async def execute(name, params):
            execution = await feature.commands[name].execute(params)
            if hasattr(execution, "get_responses"):
                return await execution.get_responses()
            return execution

        with pytest.raises(DefinedExecutionError):
            await execute("StartShaking", {"Address": 0})
        with pytest.raises(DefinedExecutionError):
            await execute("ReadStatus", {"Address": 5})
        await execute("InitializeDevice", {"Address": 0})
        await execute(
            "ConfigureShaking",
            {"Address": 0, "FrequencyHz": 10.0, "AmplitudeMm": 1.0, "PhaseDegrees": 90},
        )
        await execute("StartShaking", {"Address": 0})
        result = await execute("ReadStatus", {"Address": 0})
        assert json.loads(result["StatusJson"])["shaker_status"] == 1
        await execute("StopShaking", {"Address": 0})
        await execute("OpenDrawer", {"Address": 0})
        await execute("CloseDrawer", {"Address": 0})
        await execute("SetTargetTemperature", {"Address": 0, "TemperatureC": 25.0})
        await execute("EnableHeating", {"Address": 0})
        result = await execute(
            "WaitForTemperature",
            {
                "Address": 0,
                "TargetC": 25.0,
                "ToleranceC": 0.5,
                "StableSeconds": 0.0,
                "TimeoutSeconds": 1.0,
            },
        )
        assert result["FinalTemperatureC"] == 25.0
        await execute("DisableHeating", {"Address": 0})
    finally:
        if client is not None:
            await client.close()
        await app.stop()
        await gen.aclose()
