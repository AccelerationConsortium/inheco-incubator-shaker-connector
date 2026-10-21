import pytest

from unitelabs.inheco_incubator_shaker.io.discovery import discover, identity_query


class Device:
    def __init__(self):
        self.buffer = b""
        self.commands = []
        self.first = True

    def reset_input_buffer(self):
        self.buffer = b""

    def write(self, packet):
        master = packet[1] - 0x30
        floor = int(chr(packet[5]))
        command = packet[6:-1].decode()
        self.commands.append(command)
        if master != 2:
            return len(packet)
        reply_id = {0: 2, 1: 5, 2: 7}[floor]
        header = bytes([0xB0 + reply_id])
        if self.first:
            self.first = False
            self.buffer = header + b"\x21\x60"
            return len(packet)
        value = {"RTS": "1", "RFV0": "TEST-FW", "RFV2": f"TEST-SN-{floor}"}[command]
        self.buffer = header + value.encode() + header + b"\x20\x60"
        return len(packet)

    def read(self, size):
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data


def test_detects_master_and_distinct_slave_reply_ids_without_actions():
    device = Device()
    result = discover(device, [0, 1, 2], timeout=0.002, settle=0)
    assert result["master_id"] == 2
    assert [u["reply_device_id"] for u in result["units"]] == [2, 5, 7]
    assert result["units"][2]["serial_number"] == "TEST-SN-2"
    assert set(device.commands) <= {"RTS", "RFV0", "RFV2"}
    assert result["read_only"] is True


@pytest.mark.parametrize("command", ["AID", "ASE1", "SHE1", "AOD", "STT370"])
def test_discovery_refuses_mutating_commands(command):
    device = Device()
    with pytest.raises(ValueError, match="identity reads only"):
        identity_query(device, 2, 0, command, settle=0)
    assert not device.commands
