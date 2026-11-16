"""Sensor catalogue (SPEC §2.1).

Defined once here for offline use (the generator); migration 0001 seeds the `sensor` table with
the same values and an integration test keeps them equal. At runtime the API reads the table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sensor:
    id: str
    name: str
    measurement: str
    unit: str
    valid_min: float
    valid_max: float
    alarm_low: float | None
    warn_low: float | None
    warn_high: float | None
    alarm_high: float | None


ASSET_ID = "P-101"

# Order is significant: it is the "catalogue order" used to break arrival-time ties (SPEC §3.5).
SENSORS: tuple[Sensor, ...] = (
    Sensor("TT-101", "Inlet temperature", "temperature", "°C", -40, 150, 0, 5, 40, 45),
    Sensor("TT-102", "Outlet temperature", "temperature", "°C", -40, 200, 5, 10, 55, 65),
    Sensor("PT-101", "Discharge pressure", "pressure", "bar", 0, 25, 3.0, 4.0, 8.5, 10.0),
    Sensor("VT-101", "Vibration velocity RMS", "vibration", "mm/s", 0, 50, None, None, 4.5, 7.1),
    Sensor("FT-101", "Flow rate", "flow", "m³/h", 0, 400, 30, 50, 180, 200),
)

BY_ID: dict[str, Sensor] = {s.id: s for s in SENSORS}
