import asyncio

from unitelabs.cdk import run

from . import create_app

if __name__ == "__main__":
    asyncio.run(run(create_app))
