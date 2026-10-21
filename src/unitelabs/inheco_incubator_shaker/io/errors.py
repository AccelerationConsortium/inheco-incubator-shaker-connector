class ConnectorError(Exception):
    """The connector could not complete the requested operation."""


class UnknownAddressError(ConnectorError):
    """The requested floor is not configured."""


class DeviceInterlockError(ConnectorError):
    """The current device state does not permit the operation."""


class ProtocolError(ConnectorError):
    """The reply does not match the expected wire protocol."""


class CommunicationError(ConnectorError):
    """Communication failed; command outcome may be unknown. Reconnect and inspect state."""


class DeviceError(ConnectorError):
    """The instrument returned a firmware error code."""

    def __init__(self, command, code):
        self.command, self.code = command, code
        super().__init__(f"{command}: firmware error {code}")
