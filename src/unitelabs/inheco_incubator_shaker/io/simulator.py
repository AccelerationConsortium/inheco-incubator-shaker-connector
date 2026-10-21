"""Stateful vendor-command simulator. No elapsed-time or thermal-physics claim."""

from .errors import DeviceError


class SimulationBus:
    simulation = True

    def __init__(self, floors):
        self.states = {
            f: dict(
                initialized=False,
                drawer=0,
                shaker=0,
                heater=0,
                target=250,
                temp=250,
                flags=0,
                ax=20,
                ay=20,
                fx=142,
                fy=142,
                phase=90,
            )
            for f in floors
        }

    async def open(self):
        pass

    async def close(self):
        pass

    async def query(self, floor, command):
        s = self.states[floor]
        name, arg = command[:3], command[3:]
        values = dict(
            RTS="1",
            RFV=("SIM-FW-3.50" if arg == "0" else f"SIM-{floor}"),
            REE=str(0 if s["initialized"] else 1),
            REF=str(s["flags"]),
            RDS=str(s["drawer"]),
            RLW="1",
            RAT=str(s["temp"]),
            RTT=str(s["target"]),
            RHE=str(s["heater"]),
            RMT="800",
            RSE=str(s["shaker"]),
            RDA=str(sum(1 << f for f in self.states)),
        )
        for n, k in [
            ("RAX", "ax"),
            ("RAY", "ay"),
            ("RFX", "fx"),
            ("RFY", "fy"),
            ("RPS", "phase"),
        ]:
            values[n] = str(s[k] if arg != "1" or s["shaker"] else 0)
        if name in values:
            return values[name]
        if name == "AID":
            s.update(initialized=True, drawer=0, shaker=0, heater=0)
            return ""
        if not s["initialized"]:
            raise DeviceError(command, 7)
        if name in ("AOD", "ACD"):
            if s["shaker"]:
                raise DeviceError(command, 8)
            s["drawer"] = int(name == "AOD")
        elif name == "STT":
            s["target"] = int(arg)
        elif name == "SHE":
            s["heater"] = int(arg)
        elif name == "ASE":
            if arg == "1" and s["drawer"]:
                raise DeviceError(command, 8)
            s["shaker"] = int(arg)
        elif name == "SSP":
            s.update(zip(["ax", "ay", "fx", "fy", "phase"], map(int, arg.split(","))))
        else:
            raise DeviceError(command, 2)
        return ""
