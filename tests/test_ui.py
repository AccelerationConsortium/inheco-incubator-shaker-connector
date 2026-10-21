import asyncio
import re
from contextlib import asynccontextmanager

import pytest
from aiohttp import ClientSession
from aiohttp.test_utils import TestServer

from unitelabs.inheco_incubator_shaker import create_app
from unitelabs.inheco_incubator_shaker.config import InhecoConfig
from unitelabs.inheco_incubator_shaker.ui import PanelClient, create_http_app


@asynccontextmanager
async def running_panel():
    config = InhecoConfig(discovery=None)
    config.sila_server.port = 0
    gen = create_app(config)
    connector = await anext(gen)
    panel = None
    server = None
    try:
        await connector.start()
        panel = PanelClient(int(connector.sila_server._address.rsplit(":", 1)[1]))
        await panel.open()
        server = TestServer(create_http_app(panel))
        await server.start_server()
        async with ClientSession() as session:
            base = str(server.make_url("/")).rstrip("/")
            async with session.get(base + "/") as response:
                html = await response.text()
            token = re.search(r"const token='([^']+)'", html)[1]
            headers = {"Origin": base, "X-Panel-Token": token}
            yield panel, session, base, headers, html
    finally:
        if server is not None:
            await server.close()
        if panel is not None:
            await panel.close()
        await connector.stop()
        await gen.aclose()


async def wait_job(panel, key):
    async def wait():
        while panel.jobs[key]["state"] == "running":
            await asyncio.sleep(0.01)
        return panel.jobs[key]

    return await asyncio.wait_for(wait(), 5)


async def test_http_panel_drives_real_sila_client():
    async with running_panel() as (panel, http, base, headers, html):
        assert "Instrument control" in html and "__PANEL_TOKEN__" not in html
        async with http.get(base + "/api/info") as r:
            assert (await r.json())["simulation"] is True

        async def command(name, **params):
            async with http.post(
                base + "/api/commands",
                headers=headers,
                json={"command": name, "parameters": {"Address": 0, **params}},
            ) as response:
                assert response.status == 202
                key = (await response.json())["id"]
            result = await wait_job(panel, key)
            assert result["state"] == "succeeded", result

        await command("InitializeDevice")
        await command(
            "ConfigureShaking", FrequencyHz=10.0, AmplitudeMm=1.0, PhaseDegrees=90
        )
        await command("StartShaking")
        async with http.get(base + "/api/status?address=0") as r:
            assert (await r.json())["shaker_status"] == 1
        await command("StopShaking")
        await command("OpenDrawer")
        async with http.get(base + "/api/status?address=0") as r:
            assert (await r.json())["drawer_status"] == 1
        await command("CloseDrawer")
        await command("SetTargetTemperature", TemperatureC=25.0)
        await command("EnableHeating")
        await command(
            "WaitForTemperature",
            TargetC=25.0,
            ToleranceC=0.5,
            StableSeconds=0.0,
            TimeoutSeconds=1.0,
        )
        await command("DisableHeating")


async def test_http_rejects_cross_origin_missing_token_and_bad_commands():
    async with running_panel() as (panel, http, base, headers, html):
        payload = {"command": "InitializeDevice", "parameters": {"Address": 0}}
        for supplied in [
            {},
            {
                "Origin": "https://example.com",
                "X-Panel-Token": headers["X-Panel-Token"],
            },
            {"Origin": base},
        ]:
            async with http.post(
                base + "/api/commands", headers=supplied, json=payload
            ) as r:
                assert r.status == 403
        for payload in [
            {"command": "RawCommand", "parameters": {"Address": 0}},
            {"command": "StartShaking", "parameters": {"Address": 99}},
            {"command": "StartShaking", "parameters": {"Address": 0, "extra": 1}},
        ]:
            async with http.post(
                base + "/api/commands", headers=headers, json=payload
            ) as r:
                assert r.status == 400
        assert not panel.jobs


async def test_failure_is_not_reported_as_success_and_hardware_init_requires_confirmation():
    async with running_panel() as (panel, http, base, headers, html):
        job = panel.submit("StartShaking", {"Address": 0})
        result = await wait_job(panel, job["id"])
        assert result["state"] == "failed" and result["message"]
        panel.simulation = False
        with pytest.raises(ValueError, match="Confirm physical"):
            panel.submit("InitializeDevice", {"Address": 0})
        assert len(panel.jobs) == 1


async def test_wait_does_not_block_stop_controls():
    async with running_panel() as (panel, http, base, headers, html):
        for name, parameters in [
            ("InitializeDevice", {"Address": 0}),
            ("SetTargetTemperature", {"Address": 0, "TemperatureC": 37.0}),
            ("EnableHeating", {"Address": 0}),
        ]:
            job = panel.submit(name, parameters)
            assert (await wait_job(panel, job["id"]))["state"] == "succeeded"
        waiting = panel.submit(
            "WaitForTemperature",
            {
                "Address": 0,
                "TargetC": 37.0,
                "ToleranceC": 0.5,
                "StableSeconds": 1.0,
                "TimeoutSeconds": 20.0,
            },
        )
        with pytest.raises(ValueError, match="already"):
            panel.submit("OpenDrawer", {"Address": 0})
        stop = panel.submit("DisableHeating", {"Address": 0})
        assert (await wait_job(panel, stop["id"]))["state"] == "succeeded"
        assert (await wait_job(panel, waiting["id"]))["state"] == "failed"
