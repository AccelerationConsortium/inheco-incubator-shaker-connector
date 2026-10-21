"""Read status by default; --demo controls simulation only, never physical hardware."""

import argparse
import asyncio
import json

from sila.client import Client, ClientConfig


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    client = Client(
        ClientConfig(
            hostname="127.0.0.1", port=args.port, tls=False, default_timeout=15000
        )
    )
    try:
        await client.open()
        f = next(
            v for v in client.features.values() if v.identifier == "ShakerController"
        )
        simulation = await f.properties["Simulation"].read()
        print(f"Simulation={simulation}")

        async def execute(name, parameters):
            result = await f.commands[name].execute(parameters)
            if hasattr(result, "get_responses"):
                # get_responses waits via the observable-command result endpoint.
                result = await result.get_responses()
            return result

        if args.demo:
            if not simulation:
                raise RuntimeError("--demo is restricted to Simulation=True")
            await execute("InitializeDevice", {"Address": 0})
            await execute(
                "ConfigureShaking",
                {
                    "Address": 0,
                    "FrequencyHz": 10.0,
                    "AmplitudeMm": 1.0,
                    "PhaseDegrees": 90,
                },
            )
            await execute("StartShaking", {"Address": 0})
            print("Started simulated shaking")
            await execute("StopShaking", {"Address": 0})
            await execute("OpenDrawer", {"Address": 0})
            await execute("CloseDrawer", {"Address": 0})
        for address in await f.properties["ConfiguredAddresses"].read():
            result = await execute("ReadStatus", {"Address": address})
            print(json.dumps(json.loads(result["StatusJson"]), indent=2))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
