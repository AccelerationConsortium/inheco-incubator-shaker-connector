import math
from collections.abc import AsyncGenerator

from unitelabs.cdk import Connector

from .config import InhecoConfig
from .features.shaker_controller import ShakerController
from .io.protocol import InhecoProtocol
from .io.serial_bus import SerialBus
from .io.simulator import SimulationBus

__version__ = "0.3.0"


async def create_app(config: InhecoConfig) -> AsyncGenerator[Connector, None]:
    """Create a simulator or a native serial connector; startup never initializes hardware."""
    if (
        not math.isfinite(config.transaction_timeout_seconds)
        or not 0.1 <= config.transaction_timeout_seconds <= 300
    ):
        raise ValueError("Transaction timeout must be 0.1..300 seconds")
    if (
        not math.isfinite(config.max_temperature_c)
        or not 0 <= config.max_temperature_c <= 80
    ):
        raise ValueError("Configured maximum temperature must be 0..80 C")
    if config.simulation:
        bus = SimulationBus(config.addresses)
    else:
        if (
            not config.port
            or type(config.master_id) is not int
            or not 0 <= config.master_id <= 15
        ):
            raise ValueError(
                "Hardware mode requires explicit port and master_id (0..15)"
            )
        ids = config.reply_device_ids or [config.master_id] * len(config.addresses)
        if len(ids) != len(config.addresses) or any(
            type(i) is not int or not 0 <= i <= 15 for i in ids
        ):
            raise ValueError(
                "reply_device_ids must match addresses and contain IDs 0..15"
            )
        bus = SerialBus(
            config.port,
            config.master_id,
            dict(zip(config.addresses, ids)),
            config.transaction_timeout_seconds,
        )
    protocol = InhecoProtocol(bus, config.addresses, config.max_temperature_c)
    app = Connector(config)
    try:
        await bus.open()
        await protocol.startup()
        app.register(ShakerController(protocol))
        yield app
    finally:
        # Close communications only. Disconnect is not a physical emergency stop.
        await bus.close()
