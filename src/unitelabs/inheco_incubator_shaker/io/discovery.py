"""Explicit, read-only identity discovery; never writes instrument configuration."""

import time

from .errors import CommunicationError, DeviceError, ProtocolError
from .wire import ReplyParser, frame

READ_ONLY_COMMANDS = frozenset({"RTS", "RFV0", "RFV2"})


def identity_query(device, master_id, floor, command, timeout=0.5, settle=1.0):
    if command not in READ_ONLY_COMMANDS:
        raise ValueError("Discovery permits identity reads only")
    # Only for an explicitly invoked, exclusive discovery session; no previous
    # motion request is in flight. Leave a quiet interval after a prior timeout.
    if settle:
        time.sleep(settle)
    device.reset_input_buffer()
    packet = frame(master_id, floor, command)
    if device.write(packet) != len(packet):
        raise CommunicationError("Incomplete discovery request")
    deadline = time.monotonic() + timeout
    parser = None
    reply_id = None
    while time.monotonic() < deadline:
        chunk = device.read(1)
        if not chunk:
            continue
        if parser is None:
            if chunk == b"\n":
                continue
            if not 0xB0 <= chunk[0] <= 0xBF:
                raise ProtocolError("Unexpected identity reply header")
            reply_id = chunk[0] - 0xB0
            parser = ReplyParser(reply_id, report=True)
        reply = parser.feed(chunk)
        if reply is not None:
            if reply.error:
                raise DeviceError(command, reply.error)
            return reply_id, reply.data
    raise CommunicationError("No complete identity reply")


def discover(device, floors, timeout=0.5, settle=1.0):
    master_id = None
    for candidate in range(16):
        try:
            try:
                reply_id, model = identity_query(
                    device, candidate, 0, "RTS", timeout, settle
                )
            except DeviceError as exc:
                if exc.code != 1:
                    raise
                reply_id, model = identity_query(
                    device, candidate, 0, "RTS", timeout, settle
                )
            if reply_id != candidate:
                continue
            # This is identification, not an initialization or operating command.
            int(model)
            master_id = candidate
            break
        except (CommunicationError, ProtocolError, DeviceError, ValueError):
            continue
    if master_id is None:
        raise CommunicationError(
            "No master identified. Check power, cable, port ownership and DIP settings; no device actions were sent."
        )
    units = []
    for floor in floors:
        try:
            try:
                reply_id, kind = identity_query(
                    device, master_id, floor, "RTS", timeout, settle
                )
            except DeviceError as exc:
                if exc.code != 1:
                    raise
                reply_id, kind = identity_query(
                    device, master_id, floor, "RTS", timeout, settle
                )
            fw_id, firmware = identity_query(
                device, master_id, floor, "RFV0", timeout, settle
            )
            sn_id, serial_number = identity_query(
                device, master_id, floor, "RFV2", timeout, settle
            )
            if fw_id != reply_id or sn_id != reply_id:
                raise ProtocolError("Reply ID changed between identity reads")
            units.append(
                dict(
                    floor=floor,
                    reply_device_id=reply_id,
                    device_type=int(kind),
                    firmware=firmware,
                    serial_number=serial_number,
                )
            )
        except (CommunicationError, ProtocolError, DeviceError, ValueError) as exc:
            units.append(dict(floor=floor, error=str(exc)))
    return dict(master_id=master_id, units=units, read_only=True)


def discover_port(port, floors):
    import serial

    device = serial.Serial(
        port=None,
        baudrate=19200,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.05,
        write_timeout=1,
        exclusive=True,
    )
    device.dtr = False
    device.rts = False
    device.port = port
    try:
        device.open()
        return discover(device, floors)
    finally:
        if device.is_open:
            device.close()
