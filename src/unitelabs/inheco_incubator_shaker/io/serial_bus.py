import asyncio
import logging
import time

from .errors import CommunicationError, DeviceError, ProtocolError
from .wire import ReplyParser, frame

logger = logging.getLogger(__name__)


class SerialBus:
    """One owner and one in-flight transaction for the entire physical USB stack."""

    simulation = False

    def __init__(self, port, master_id, reply_ids, timeout=6.0):
        self.port, self.master_id, self.reply_ids = port, master_id, reply_ids
        self.timeout = timeout
        self.lock = asyncio.Lock()
        self.serial = None
        self.poisoned = False

    async def open(self):
        import serial

        def connect():
            device = serial.Serial(
                port=None,
                baudrate=19200,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.05,
                write_timeout=1,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
                exclusive=True,
            )
            device.dtr = False
            device.rts = False
            device.port = self.port
            device.open()
            return device

        self.serial = await asyncio.to_thread(connect)

    async def close(self):
        async with self.lock:
            if self.serial is not None:
                await asyncio.to_thread(self.serial.close)
                self.serial = None

    def _exchange(self, floor, command):
        if self.poisoned or self.serial is None:
            raise CommunicationError(
                "Bus unavailable; restart connector and read state"
            )
        parser = ReplyParser(self.reply_ids[floor], command.startswith("R"))
        packet = frame(self.master_id, floor, command)
        logger.debug("TX floor=%s command=%s frame=%s", floor, command, packet.hex())
        try:
            if self.serial.write(packet) != len(packet):
                raise CommunicationError("Partial serial write; outcome unknown")
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                chunk = self.serial.read(1)
                if not chunk:
                    continue
                reply = parser.feed(chunk)
                if reply is not None:
                    logger.debug("RX floor=%s bytes=%s", floor, parser.raw.hex())
                    if reply.error:
                        raise DeviceError(command, reply.error)
                    return reply.data
            raise CommunicationError(f"Timeout waiting for {command}; outcome unknown")
        except DeviceError:
            raise
        except Exception as exc:
            self.poisoned = True
            if isinstance(exc, (CommunicationError, ProtocolError)):
                raise
            raise CommunicationError(
                f"Serial failure during {command}; outcome unknown"
            ) from exc

    async def query(self, floor, command):
        async with self.lock:
            # A cancelled coroutine must not free the bus while its thread is reading.
            task = asyncio.create_task(
                asyncio.to_thread(self._exchange, floor, command)
            )
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                except Exception:
                    logger.exception("Transaction failed while caller was cancelling")
                raise
