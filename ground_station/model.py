"""Transport-independent telemetry state. Missing values remain None."""
from dataclasses import dataclass, fields
import math
import time

@dataclass
class Telemetry:
    roll: float | None = None
    pitch: float | None = None
    yaw: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    groundspeed: float | None = None
    airspeed: float | None = None
    vertical_speed: float | None = None
    heading: float | None = None
    voltage: float | None = None
    current: float | None = None
    remaining: int | None = None
    satellites: int | None = None
    fix: str | None = None
    gps_status: str | None = None
    mode: str | None = None
    armed: str | None = None

FIXES = {0: "No GPS", 1: "No fix", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK float", 6: "RTK fixed", 7: "Static", 8: "PPP"}

class TelemetryStore:
    def __init__(self):
        self.data = Telemetry()
        self.updated = {}

    def update(self, msg, mode=None, now=None):
        now = time.monotonic() if now is None else now
        kind = msg.get_type()
        values = {}
        if kind == "ATTITUDE":
            values = dict(roll=math.degrees(msg.roll), pitch=math.degrees(msg.pitch), yaw=math.degrees(msg.yaw) % 360)
        elif kind == "GLOBAL_POSITION_INT":
            values = dict(latitude=msg.lat * 1e-7, longitude=msg.lon * 1e-7,
                          altitude=msg.relative_alt / 1000, groundspeed=math.hypot(msg.vx, msg.vy) / 100,
                          heading=None if msg.hdg == 65535 else msg.hdg / 100)
        elif kind == "VFR_HUD":
            # A positive reported value may be an estimate; zero does not prove a sensor exists.
            values = dict(airspeed=msg.airspeed if msg.airspeed > 0 else None,
                          groundspeed=msg.groundspeed, vertical_speed=msg.climb, heading=msg.heading)
        elif kind == "SYS_STATUS":
            values = dict(voltage=None if msg.voltage_battery == 65535 else msg.voltage_battery / 1000,
                          current=None if msg.current_battery == -1 else msg.current_battery / 100,
                          remaining=None if msg.battery_remaining == -1 else msg.battery_remaining)
        elif kind == "GPS_RAW_INT":
            values = dict(satellites=None if msg.satellites_visible == 255 else msg.satellites_visible,
                          fix=FIXES.get(msg.fix_type, "Unknown"),
                          gps_status={0: "No GPS detected", 1: "Searching for fix",
                                      2: "2D position only", 3: "3D fix acquired",
                                      4: "DGPS fix acquired", 5: "RTK float",
                                      6: "RTK fixed", 7: "Static position",
                                      8: "PPP fix acquired"}.get(msg.fix_type, "Unknown fix status"))
        elif kind == "HEARTBEAT":
            values = dict(mode=mode or "Unknown", armed="ARMED" if msg.base_mode & 128 else "DISARMED")
        for key, value in values.items():
            if isinstance(value, float) and not math.isfinite(value):
                value = None
            setattr(self.data, key, value)
            self.updated[key] = now

    def snapshot(self, now=None, max_age=3.0):
        now = time.monotonic() if now is None else now
        return Telemetry(**{f.name: getattr(self.data, f.name) if now - self.updated.get(f.name, -math.inf) < max_age else None for f in fields(Telemetry)})
