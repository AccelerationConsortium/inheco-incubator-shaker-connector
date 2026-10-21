"""Local browser control panel. All instrument calls go through a SiLA client."""

import argparse
import asyncio
import contextlib
import json
import secrets
import time
import webbrowser
from importlib.resources import files

from sila.client import Client, ClientConfig

COMMANDS = {
    "InitializeDevice": set(),
    "OpenDrawer": set(),
    "CloseDrawer": set(),
    "ConfigureShaking": {"FrequencyHz", "AmplitudeMm", "PhaseDegrees"},
    "StartShaking": set(),
    "StopShaking": set(),
    "SetTargetTemperature": {"TemperatureC"},
    "EnableHeating": set(),
    "DisableHeating": set(),
    "WaitForTemperature": {"TargetC", "ToleranceC", "StableSeconds", "TimeoutSeconds"},
}


class PanelClient:
    """Bounded, in-memory execution history; no direct device/serial access."""

    def __init__(self, port=50052):
        self.client = Client(
            ClientConfig(
                hostname="127.0.0.1", port=port, tls=False, default_timeout=15000
            )
        )
        self.feature = None
        self.jobs = {}
        self.tasks = set()
        self.read_lock = asyncio.Lock()
        self.simulation = None
        self.addresses = []

    async def open(self):
        await self.client.open()
        self.feature = next(
            f
            for f in self.client.features.values()
            if f.identifier == "ShakerController"
        )
        self.simulation = await self.feature.properties["Simulation"].read()
        self.addresses = await self.feature.properties["ConfiguredAddresses"].read()

    async def close(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.client.close()

    async def status(self, address):
        if address not in self.addresses:
            raise ValueError("Unknown floor")
        async with self.read_lock:
            data = await self.feature.commands["ReadStatus"].execute(
                {"Address": address}
            )
        return json.loads(data["StatusJson"])

    def submit(self, command, parameters, confirmed=False):
        if command not in COMMANDS or not isinstance(parameters, dict):
            raise ValueError("Unsupported command or parameters")
        if set(parameters) != COMMANDS[command] | {"Address"}:
            raise ValueError("Parameters do not match command")
        address = parameters["Address"]
        if type(address) is not int or address not in self.addresses:
            raise ValueError("Unknown floor")
        if (
            not self.simulation
            and command == "InitializeDevice"
            and confirmed is not True
        ):
            raise ValueError("Confirm physical drawer movement before initialization")
        active = [j for j in self.jobs.values() if j["state"] == "running"]
        if len(active) >= 12:
            raise ValueError("Too many running operations")
        # One active normal operation per floor. Stops are still available during a wait.
        if command not in ("StopShaking", "DisableHeating") and any(
            j["address"] == address for j in active
        ):
            raise ValueError("This floor already has an operation running")
        while len(self.jobs) >= 100:
            old = next(
                (k for k, v in self.jobs.items() if v["state"] != "running"), None
            )
            if old is None:
                raise ValueError("Execution history is full")
            del self.jobs[old]
        key = secrets.token_hex(8)
        job = dict(
            id=key,
            command=command,
            address=address,
            state="running",
            message="Awaiting device result",
            started=time.time(),
            result=None,
        )
        self.jobs[key] = job
        task = asyncio.create_task(self._execute(job, parameters))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return job.copy()

    async def _execute(self, job, parameters):
        try:
            result = await self.feature.commands[job["command"]].execute(parameters)
            if hasattr(result, "get_responses"):
                # A temperature wait can outlive the normal unary request timeout.
                timeout = (
                    (parameters.get("TimeoutSeconds", 0) + 30) * 1000
                    if job["command"] == "WaitForTemperature"
                    else 30000
                )
                result = await result.get_responses(timeout=timeout)
            job.update(
                state="succeeded",
                message="Completed and confirmed by connector",
                result=result,
            )
        except asyncio.CancelledError:
            job.update(
                state="unknown", message="Panel closed; device outcome may be unknown"
            )
            raise
        except Exception as exc:
            job.update(state="failed", message=str(exc))
        finally:
            job["finished"] = time.time()


def create_http_app(panel, allowed_authorities=None):
    from aiohttp import web

    token = secrets.token_urlsafe(32)
    authorities = allowed_authorities

    @web.middleware
    async def local_only(request, handler):
        from urllib.parse import urlsplit

        host = request.host
        if authorities is not None:
            valid_host = host in authorities
        else:
            valid_host = urlsplit("//" + host).hostname in ("127.0.0.1", "localhost")
        if not valid_host:
            raise web.HTTPForbidden(text="Local access only")
        if request.method == "POST":
            if request.headers.get("Origin") != f"http://{host}":
                raise web.HTTPForbidden(text="Same-origin request required")
            if not secrets.compare_digest(
                request.headers.get("X-Panel-Token", ""), token
            ):
                raise web.HTTPForbidden(text="Invalid panel token")
            if request.content_type != "application/json":
                raise web.HTTPUnsupportedMediaType()
        response = await handler(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    app = web.Application(middlewares=[local_only], client_max_size=8192)

    async def index(request):
        text = (
            files("unitelabs.inheco_incubator_shaker")
            .joinpath("static/panel.html")
            .read_text()
        )
        return web.Response(
            text=text.replace("__PANEL_TOKEN__", token), content_type="text/html"
        )

    async def info(request):
        return web.json_response(
            dict(simulation=panel.simulation, addresses=panel.addresses)
        )

    async def status(request):
        try:
            value = await panel.status(int(request.query.get("address", "0")))
            return web.json_response(value)
        except Exception as exc:
            return web.json_response({"error": str(exc)}, status=502)

    async def commands(request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            job = panel.submit(
                data.get("command"),
                data.get("parameters"),
                data.get("confirmed", False),
            )
            return web.json_response(job, status=202)
        except (ValueError, TypeError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    async def jobs(request):
        return web.json_response(list(panel.jobs.values())[::-1])

    app.add_routes(
        [
            web.get("/", index),
            web.get("/api/info", info),
            web.get("/api/status", status),
            web.post("/api/commands", commands),
            web.get("/api/jobs", jobs),
        ]
    )
    return app


async def serve(args):
    from aiohttp import web

    generator = connector = None
    panel = PanelClient(args.sila_port)
    runner = None
    try:
        if args.simulation:
            from . import create_app
            from .config import InhecoConfig

            config = InhecoConfig(discovery=None)
            config.sila_server.port = args.sila_port
            generator = create_app(config)
            connector = await anext(generator)
            await connector.start()
        await panel.open()
        runner = web.AppRunner(create_http_app(panel))
        await runner.setup()
        await web.TCPSite(runner, "127.0.0.1", args.port).start()
        actual_port = runner.addresses[0][1]
        url = f"http://127.0.0.1:{actual_port}"
        print(
            f"INHECO panel: {url} | {'SIMULATION' if panel.simulation else 'HARDWARE'}",
            flush=True,
        )
        if not args.no_browser:
            webbrowser.open(url)
        await asyncio.Event().wait()
    finally:
        if runner is not None:
            await runner.cleanup()
        await panel.close()
        if connector is not None:
            await connector.stop()
        if generator is not None:
            await generator.aclose()


def main():
    import logging

    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--simulation",
        action="store_true",
        help="Start an embedded simulated SiLA connector",
    )
    parser.add_argument(
        "--sila-port", type=int, default=50052, help="Local SiLA server port"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Local web panel port; 0 selects a free port automatically",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not 1 <= args.sila_port <= 65535:
        parser.error("Web port must be 0..65535; SiLA port must be 1..65535")
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        parser.error("Install the UI extra: uv sync --extra ui")
    with contextlib.suppress(KeyboardInterrupt):
        try:
            asyncio.run(serve(args))
        except OSError as exc:
            import errno

            if exc.errno == errno.EADDRINUSE:
                parser.exit(
                    1,
                    "Web port is already in use. Run with --port 0 to select a free port automatically.\n",
                )
            raise


if __name__ == "__main__":
    main()
