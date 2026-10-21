"""Small local setup helpers; no movements are sent by this module."""

import argparse
import asyncio
import json
from pathlib import Path

from . import create_app
from .config import InhecoConfig
from .features.shaker_controller import ShakerController


def update_config(path, args):
    if not path.exists():
        raise SystemExit("Run config create first; config.json was not found")
    original = path.read_text()
    data = json.loads(original)
    if args.simulation:
        data["simulation"] = True
    else:
        data.update(
            simulation=False,
            port=args.port,
            master_id=args.master_id,
            addresses=args.floors,
            reply_device_ids=args.reply_ids,
        )
    # Validate before overwriting the file.
    InhecoConfig.validate(data)
    path.with_suffix(".json.bak").write_text(original)
    path.write_text(json.dumps(data, indent=2))
    print(f"Updated {path}; previous version saved as {path}.bak")
    print(
        "SIMULATION"
        if data["simulation"]
        else "HARDWARE — configuration only, no commands sent"
    )


async def probe(path):
    config = InhecoConfig.validate(json.loads(path.read_text()))
    gen = create_app(config)
    try:
        app = await anext(gen)
        controller = app.get_feature(ShakerController)
        print(
            "SIMULATION"
            if controller.protocol.simulation
            else "HARDWARE read-only probe"
        )
        for floor in controller.protocol.floors:
            print(await controller.protocol.status(floor))
    finally:
        await gen.aclose()


def main():
    import logging

    import structlog

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
    )
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("ports", help="List serial ports without opening them")
    setup = sub.add_parser("configure", help="Edit an existing generated config.json")
    mode = setup.add_mutually_exclusive_group(required=True)
    mode.add_argument("--simulation", action="store_true")
    mode.add_argument("--hardware", action="store_true")
    setup.add_argument("--port")
    setup.add_argument("--master-id", type=int)
    setup.add_argument("--floors", type=int, nargs="+", default=[0, 1, 2])
    setup.add_argument("--reply-ids", type=int, nargs="*", default=[])
    setup.add_argument("--config", type=Path, default=Path("config.json"))
    read = sub.add_parser(
        "probe", help="Read identity and status without initializing or moving"
    )
    read.add_argument("--config", type=Path, default=Path("config.json"))
    detect = sub.add_parser(
        "detect", help="Discover master and per-floor identity using read-only queries"
    )
    detect.add_argument("--port", required=True)
    detect.add_argument("--floors", type=int, nargs="+", default=[0, 1, 2])
    args = parser.parse_args()
    if args.action == "ports":
        from serial.tools import list_ports

        for port in list_ports.comports():
            print(
                json.dumps(
                    dict(
                        port=port.device,
                        description=port.description,
                        vid=port.vid,
                        pid=port.pid,
                        serial=port.serial_number,
                    )
                )
            )
    elif args.action == "detect":
        if (
            not args.floors
            or len(set(args.floors)) != len(args.floors)
            or any(not 0 <= f <= 5 for f in args.floors)
        ):
            parser.error("Floors must be unique integers 0..5")
        from .io.discovery import discover_port

        print(
            "Read-only identity scan; allow up to 45 seconds. No device actions are sent.",
            flush=True,
        )
        try:
            result = discover_port(args.port, args.floors)
        except OSError as exc:
            parser.exit(
                1,
                f"Cannot open serial port {args.port}: {exc}\nStop the connector or other serial software first. On macOS, inspect the owner with: lsof {args.port}\n",
            )
        print(json.dumps(result, indent=2))
    elif args.action == "configure":
        if args.hardware and (not args.port or args.master_id is None):
            parser.error("--hardware requires --port and --master-id")
        if args.hardware and (
            not 0 <= args.master_id <= 15
            or not args.floors
            or len(set(args.floors)) != len(args.floors)
            or any(not 0 <= f <= 5 for f in args.floors)
        ):
            parser.error("Master ID must be 0..15; floors must be unique 0..5")
        if args.reply_ids and (
            len(args.reply_ids) != len(args.floors)
            or any(not 0 <= i <= 15 for i in args.reply_ids)
        ):
            parser.error("--reply-ids must have one ID 0..15 per floor")
        update_config(args.config, args)
    else:
        asyncio.run(probe(args.config))


if __name__ == "__main__":
    main()
