import pytest

from unitelabs.inheco_incubator_shaker.io.errors import ProtocolError
from unitelabs.inheco_incubator_shaker.io.wire import ReplyParser, frame


def test_vendor_crc_vector():
    assert frame(2, 0, "RFV") == bytes.fromhex("09 32 c6 54 30 30 52 46 56 04")


@pytest.mark.parametrize(
    "raw,value,error,report",
    [
        (
            b"\xb2IVDIncubator-C-V1.33-12/2008\xb2\x20\x60",
            "IVDIncubator-C-V1.33-12/2008",
            0,
            True,
        ),
        (b"\xb2370\xb2\x20\x60", "370", 0, True),
        (b"\xb2\x20\x60", "", 0, False),
        (b"\xb2\x34\x60", "", 20, False),
        (b"\xb2\x0a\x20\x60\x0a", "", 0, False),
        (b"\xb2\x20\x0a\x60\x0a", "", 0, False),
    ],
)
def test_fragmented(raw, value, error, report):
    p = ReplyParser(2, report)
    for b in raw:
        result = p.feed(bytes([b]))
    assert result.data == value and result.error == error


@pytest.mark.parametrize("raw", [b"\xb1\x20\x60", b"\xb2junk\x20\x60", b"\xb2\x01\x60"])
def test_bad_control(raw):
    with pytest.raises(ProtocolError):
        ReplyParser(2, False).feed(raw)


def test_incomplete():
    assert ReplyParser(2, False).feed(b"\xb2\x20") is None


@pytest.mark.parametrize(
    "master,floor,cmd",
    [(16, 0, "RTS"), (2, 6, "RTS"), (2, 0, ""), (2, 0, "A" * 58), (2, 0, "RFV\n")],
)
def test_bad_frame_input(master, floor, cmd):
    with pytest.raises(ValueError):
        frame(master, floor, cmd)
