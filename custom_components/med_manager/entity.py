"""Compatibility note for the retired entity module.

CGPT-STAMP: 2026-09-21 reliable-lifecycle
Home Assistant loads the sensor platform from sensor.py.  Earlier versions kept
a second, conflicting MedSensor implementation here; retaining it would make
future fixes ambiguous.  Import the canonical entity from sensor.py instead.
"""

from .sensor import MedSensor

__all__ = ["MedSensor"]
