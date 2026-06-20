"""
Core data models for the Traffic Intersection Intelligence System.

Defines vehicles, lanes, directions, and the intersection geometry used
throughout the simulation, analytics, and signal-control modules.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VehicleType(str, Enum):
    """Vehicle categories calibrated to typical Indian urban traffic mix."""

    TWO_WHEELER = "two_wheeler"        # Motorcycles / scooters
    AUTO_RICKSHAW = "auto_rickshaw"    # Three-wheeler
    CAR = "car"
    BUS = "bus"
    TRUCK = "truck"
    CYCLE = "cycle"


# Approximate footprint (meters of road length occupied, including gap)
# and free-flow speed range (km/h) per vehicle type. These numbers are
# illustrative approximations used for simulation realism, not measured data.
VEHICLE_PROFILES = {
    VehicleType.TWO_WHEELER: {"length_m": 2.2, "speed_kmh": (35, 60), "weight": 0.45},
    VehicleType.AUTO_RICKSHAW: {"length_m": 3.2, "speed_kmh": (20, 40), "weight": 0.15},
    VehicleType.CAR: {"length_m": 4.5, "speed_kmh": (30, 55), "weight": 0.28},
    VehicleType.BUS: {"length_m": 11.0, "speed_kmh": (20, 40), "weight": 0.05},
    VehicleType.TRUCK: {"length_m": 9.0, "speed_kmh": (20, 35), "weight": 0.04},
    VehicleType.CYCLE: {"length_m": 1.8, "speed_kmh": (10, 20), "weight": 0.03},
}


class Direction(str, Enum):
    """Approach direction at a 4-way intersection."""

    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

    @property
    def opposite(self) -> "Direction":
        return {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        }[self]


class TurnIntent(str, Enum):
    STRAIGHT = "straight"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Vehicle:
    """A single tracked vehicle approaching or crossing the intersection."""

    vehicle_type: VehicleType
    direction: Direction
    turn_intent: TurnIntent
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    position_m: float = 0.0          # distance from stop line (m), decreases toward 0
    speed_kmh: float = 0.0
    waiting_time_s: float = 0.0
    entered_at_tick: int = 0
    has_crossed: bool = False
    is_violating: bool = False       # e.g. crossed on red / lane indiscipline

    def __post_init__(self) -> None:
        if self.speed_kmh == 0.0:
            # Fallback only: if no speed was explicitly assigned by the
            # caller (e.g. a seeded simulator), use the midpoint of this
            # vehicle type's profile range so behavior is still sane and
            # fully deterministic without touching the global `random`
            # module. Simulators should set speed_kmh explicitly using
            # their own seeded RNG right after construction.
            lo, hi = VEHICLE_PROFILES[self.vehicle_type]["speed_kmh"]
            self.speed_kmh = (lo + hi) / 2

    @property
    def length_m(self) -> float:
        return VEHICLE_PROFILES[self.vehicle_type]["length_m"]


@dataclass
class Lane:
    """A single approach lane queueing vehicles toward the stop line."""

    direction: Direction
    lane_index: int
    queue: list = field(default_factory=list)  # list[Vehicle], front = index 0
    capacity_m: float = 150.0  # visible road length modeled for this lane

    @property
    def queue_length(self) -> int:
        return len(self.queue)

    @property
    def occupied_length_m(self) -> float:
        return sum(v.length_m + 1.0 for v in self.queue)  # +1m inter-vehicle gap

    @property
    def density_ratio(self) -> float:
        """Fraction of lane capacity currently occupied, clamped to [0, 1]."""
        return min(1.0, self.occupied_length_m / self.capacity_m)


def make_intersection_lanes(lanes_per_direction: int = 2) -> dict:
    """Build an empty lane registry for a standard 4-way intersection.

    Returns a dict keyed by Direction -> list[Lane].
    """
    registry = {}
    for direction in Direction:
        registry[direction] = [
            Lane(direction=direction, lane_index=i)
            for i in range(lanes_per_direction)
        ]
    return registry


_id_counter = itertools.count(1)


def next_sequence_id() -> int:
    """Monotonic counter, handy for deterministic logging/test ordering."""
    return next(_id_counter)
