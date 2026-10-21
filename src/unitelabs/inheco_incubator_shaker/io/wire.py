"""INHECO FCS 900334-002 v1.5, sections 7.2.1–7.2.3. Independent implementation."""

from dataclasses import dataclass

from .errors import ProtocolError


def crc8(data: bytes) -> int:
    crc = 0xA1
    for value in data:
        for _ in range(8):
            mix = (crc ^ value) & 1
            crc >>= 1
            if mix:
                crc ^= 0x8C
            value >>= 1
    return crc


def frame(master_id: int, floor: int, command: str) -> bytes:
    if type(master_id) is not int or not 0 <= master_id <= 15:
        raise ValueError("Master DIP ID must be 0..15")
    if type(floor) is not int or not 0 <= floor <= 5:
        raise ValueError("Floor must be 0..5")
    if not command or any(not (32 < ord(c) < 127) for c in command):
        raise ValueError("Command must be nonempty printable ASCII without spaces")
    payload = f"T0{floor}{command}".encode("ascii")
    if len(payload) > 60:
        raise ValueError("Payload exceeds 60 bytes")
    body = bytes([len(payload) + 3, 0x30 + master_id, 0xC0 + len(payload)]) + payload
    return body + bytes([crc8(body)])


@dataclass(frozen=True)
class Reply:
    data: str
    error: int


class ReplyParser:
    """Incremental ASCII-report / set-action parser; handles documented stray LF.

    This is not a binary EEPROM parser. Only the connector's allowlisted ASCII
    commands are supported. No CRC is supplied by this device on responses.
    """

    def __init__(self, expected_id: int, report: bool):
        self.header = 0xB0 + expected_id
        self.report = report
        self.raw = bytearray()
        self.result = None

    def feed(self, chunk: bytes) -> Reply | None:
        for value in chunk:
            if self.result is not None:
                if value != 10:
                    raise ProtocolError("Unexpected bytes after response terminator")
                continue
            if not self.raw and value == 10:
                continue
            self.raw.append(value)
            if len(self.raw) > 4096:
                raise ProtocolError("Reply exceeds 4096 bytes")
            if len(self.raw) == 1 and value != self.header:
                raise ProtocolError(
                    f"Unexpected reply ID: 0x{value:02x}; check reply_device_ids"
                )
            if value != 0x60:
                continue
            # LF is known to occur before the error byte or before the terminator.
            body = bytes(self.raw[:-1]).replace(b"\n", b"")
            if len(body) < 2 or not 0x20 <= body[-1] <= 0x3F:
                raise ProtocolError("Invalid error trailer")
            content = body[1:-1]
            if self.report and content.endswith(bytes([self.header])):
                content = content[:-1]
            if self.header in content or any(b >= 128 for b in content):
                raise ProtocolError("Unexpected report body / address marker")
            if not self.report and content:
                raise ProtocolError("Unexpected data in control response")
            try:
                data = content.decode("ascii").strip("\r\x00")
            except UnicodeDecodeError as exc:
                raise ProtocolError("Non-ASCII report") from exc
            self.result = Reply(data, body[-1] - 0x20)
        return self.result
