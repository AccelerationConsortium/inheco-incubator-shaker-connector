from unitelabs.cdk import sila

from ..io.errors import (
    CommunicationError,
    ConnectorError,
    DeviceError,
    DeviceInterlockError,
    ProtocolError,
    UnknownAddressError,
)
from ..io.protocol import InhecoProtocol


class ShakerController(sila.Feature):
    """Control INHECO Shaker MP floors; inspect Simulation before operating."""

    def __init__(self, protocol: InhecoProtocol):
        super().__init__(originator="org.sissifeng", category="incubation")
        self.protocol = protocol

    @sila.UnobservableProperty()
    async def get_simulation(self) -> bool:
        """Indicate whether this server uses the simulator."""
        return self.protocol.simulation

    @sila.UnobservableProperty()
    async def get_configured_addresses(self) -> list[int]:
        """Return configured floors that passed startup identity checks."""
        return self.protocol.floors

    @sila.UnobservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def read_status(self, address: int) -> str:
        """Read sequential status values including firmware identity and units.

        Args:
          Address: Configured floor 0 to 5.

        Returns:
          StatusJson: JSON snapshot; values are sequential, not atomic.
        """
        return await self.protocol.status(address)

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def initialize_device(self, address: int) -> None:
        """Initialize device; this closes drawer and stops heater and shaker.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.initialize(address)

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def open_drawer(self, address: int) -> None:
        """Open drawer and confirm fully open state.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.drawer(address, True)

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def close_drawer(self, address: int) -> None:
        """Close drawer and confirm closed state.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.drawer(address, False)

    @sila.UnobservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def configure_shaking(
        self, address: int, frequency_hz: float, amplitude_mm: float, phase_degrees: int
    ) -> None:
        """Configure equal X/Y frequency and amplitude while stopped; confirm setpoint readback.

        Args:
          Address: Configured floor 0 to 5.
          FrequencyHz: Equal X/Y frequency in Hz, 6.6 to 30.0 in 0.1 steps.
          AmplitudeMm: Per-axis firmware amplitude in mm, 0 to 3 in 0.1 steps; not a diameter conversion.
          PhaseDegrees: X/Y phase in integer degrees 0 to 360; 90 for an orbital pattern.
        """
        await self.protocol.configure_shaking(
            address, frequency_hz, amplitude_mm, phase_degrees
        )

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def start_shaking(self, address: int) -> None:
        """Enable shaking and confirm enabled state, not steady speed or mixing quality.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.start_shaking(address)

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def stop_shaking(self, address: int) -> None:
        """Disable shaking and wait until reported fully stopped.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.stop_shaking(address)

    @sila.UnobservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def set_target_temperature(self, address: int, temperature_c: float) -> None:
        """Set and read back target; this does not wait for actual temperature.

        Args:
          Address: Configured floor 0 to 5.
          TemperatureC: Target in degrees Celsius, 0.1 resolution.
        """
        await self.protocol.set_temperature(address, temperature_c)

    @sila.UnobservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def enable_heating(self, address: int) -> None:
        """Enable heating and confirm enable state.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.heating(address, True)

    @sila.UnobservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def disable_heating(self, address: int) -> None:
        """Disable heating and confirm disabled state.

        Args:
          Address: Configured floor 0 to 5.
        """
        await self.protocol.heating(address, False)

    @sila.ObservableCommand(
        errors=[
            ConnectorError,
            UnknownAddressError,
            DeviceInterlockError,
            DeviceError,
            ProtocolError,
            CommunicationError,
            ValueError,
        ]
    )
    async def wait_for_temperature(
        self,
        address: int,
        target_c: float,
        tolerance_c: float,
        stable_seconds: float,
        timeout_seconds: float,
        *,
        status: sila.Status,
        intermediate: sila.Intermediate[float],
    ) -> float:
        """Wait for the main device sensor to stay within tolerance; does not measure liquid temperature.

        Args:
          Address: Configured floor.
          TargetC: Expected existing temperature target in Celsius.
          ToleranceC: Allowed sensor deviation, 0.1 to 10 Celsius.
          StableSeconds: Required continuous time within tolerance.
          TimeoutSeconds: Maximum wait, at most 86400 seconds.

        Yields:
          MeasuredC: Latest main device sensor temperature in Celsius.

        Returns:
          FinalTemperatureC: Main sensor temperature at completion.
        """
        return await self.protocol.wait_temperature(
            address,
            target_c,
            tolerance_c,
            stable_seconds,
            timeout_seconds,
            intermediate.send,
        )
