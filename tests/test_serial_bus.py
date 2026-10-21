import asyncio
import os
import pty
import select
import threading
import time

import pytest

from unitelabs.inheco_incubator_shaker.io.errors import CommunicationError, DeviceError
from unitelabs.inheco_incubator_shaker.io.protocol import InhecoProtocol
from unitelabs.inheco_incubator_shaker.io.serial_bus import SerialBus
from unitelabs.inheco_incubator_shaker.io.simulator import SimulationBus
from unitelabs.inheco_incubator_shaker.io.wire import crc8


class FakeSerial:
    def __init__(self, replies):
        self.replies = list(replies)
        self.buffer = b""
        self.writes = []

    def write(self, packet):
        self.writes.append(packet)
        self.buffer = self.replies.pop(0)
        return len(packet)

    def read(self, count):
        if not self.buffer:
            time.sleep(0.002)
            return b""
        result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result

    def close(self):
        pass


async def test_timeout_poison_no_write_retry():
    b = SerialBus("fake", 2, {0: 2}, 0.01)
    b.serial = FakeSerial([b""])
    with pytest.raises(CommunicationError):
        await b.query(0, "ASE1")
    assert b.poisoned
    with pytest.raises(CommunicationError):
        await b.query(0, "RSE")
    assert len(b.serial.writes) == 1


async def test_firmware_error_does_not_poison_and_supports_code20():
    b = SerialBus("fake", 2, {0: 2})
    b.serial = FakeSerial([b"\xb2\x34\x60", b"\xb20\xb2\x20\x60"])
    with pytest.raises(DeviceError) as e:
        await b.query(0, "ASE1")
    assert e.value.code == 20 and not b.poisoned
    assert await b.query(0, "RSE") == "0"


async def test_trailing_lf_next_transaction():
    b = SerialBus("fake", 2, {0: 2})
    b.serial = FakeSerial([b"\xb2\x20\x60", b"\n\xb20\xb2\x20\x60"])
    await b.query(0, "ASE0")
    assert await b.query(0, "RSE") == "0"


async def test_cancellation_holds_lock_until_thread_finishes():
    event = threading.Event()

    class Blocking(FakeSerial):
        def read(self, n):
            event.wait(0.5)
            return super().read(n)

    b = SerialBus("fake", 2, {0: 2}, 1)
    b.serial = Blocking([b"\xb2\x20\x60", b"\xb20\xb2\x20\x60"])
    first = asyncio.create_task(b.query(0, "ASE0"))
    await asyncio.sleep(0.02)
    first.cancel()
    second = asyncio.create_task(b.query(0, "RSE"))
    await asyncio.sleep(0.02)
    assert len(b.serial.writes) == 1
    event.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert await second == "0"


@pytest.mark.skipif(os.name != "posix", reason="POSIX pseudo-terminal integration")
async def test_real_pyserial_via_os_pseudo_terminal():
    master, slave = pty.openpty()
    slave_path = os.ttyname(slave)
    stop = threading.Event()
    failures = []
    model = SimulationBus([0, 1, 2])

    def emulate():
        buf = bytearray()
        while not stop.is_set():
            if not select.select([master], [], [], 0.05)[0]:
                continue
            try:
                chunk = os.read(master, 512)
            except OSError:
                return
            buf.extend(chunk)
            while buf and len(buf) >= buf[0] + 1:
                size = buf[0] + 1
                packet = bytes(buf[:size])
                del buf[:size]
                try:
                    assert crc8(packet[:-1]) == packet[-1]
                    payload = packet[3:-1].decode()
                    floor = int(payload[2])
                    cmd = payload[3:]
                    value = asyncio.run(model.query(floor, cmd)).encode()
                    reply = (
                        b"\xb2"
                        + value
                        + (b"\xb2" if cmd.startswith("R") else b"")
                        + b"\x20\x60"
                    )
                    # Fragment the response over actual OS serial reads.
                    for byte in reply:
                        os.write(master, bytes([byte]))
                except Exception as exc:
                    failures.append(exc)
                    stop.set()
                    return

    thread = threading.Thread(target=emulate, daemon=True)
    thread.start()
    b = SerialBus(slave_path, 2, {0: 2, 1: 2, 2: 2}, 1)
    try:
        await b.open()
        p = InhecoProtocol(b, [0, 1, 2])
        await p.startup()
        await p.initialize(0)
        await p.configure_shaking(0, 10.0, 1.0, 90)
        await p.start_shaking(0)
        await p.stop_shaking(0)
        await p.drawer(0, True)
        assert '"drawer_status": 1' in await p.status(0)
        assert not failures
    finally:
        await b.close()
        stop.set()
        thread.join(1)
        os.close(master)
        os.close(slave)
