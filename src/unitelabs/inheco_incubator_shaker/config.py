from dataclasses import dataclass, field

from unitelabs.cdk.config import ConnectorBaseConfig, SiLAServerConfig


@dataclass
class InhecoConfig(ConnectorBaseConfig):
    simulation: bool = True
    port: str = ""
    master_id: int | None = None
    addresses: list[int] = field(default_factory=lambda: [0, 1, 2])
    reply_device_ids: list[int] = field(default_factory=list)
    transaction_timeout_seconds: float = 6.0
    max_temperature_c: float = 80.0
    sila_server: SiLAServerConfig = field(
        default_factory=lambda: SiLAServerConfig(
            hostname="127.0.0.1",
            port=50052,
            name="INHECO Shaker MP",
            type="InhecoIncubatorShakerMP",
            version="0.2.0",
            description="Read Simulation property before use. Real hardware commissioning pending.",
        )
    )
