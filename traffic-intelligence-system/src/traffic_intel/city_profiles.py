"""
City traffic profiles for the Traffic Intersection Intelligence System.

Each profile parameterizes a generic Indian city's traffic behavior:
vehicle-type mix, peak-hour multipliers, and base arrival rates. These
are configurable, illustrative approximations meant to make simulations
feel representative of common Indian urban traffic patterns -- they are
NOT measured municipal data.

Add your own city by instantiating CityProfile and registering it in
CITY_PROFILES.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .models import VehicleType


@dataclass
class CityProfile:
    name: str
    state: str
    # Relative likelihood of each vehicle type appearing (need not sum to 1; normalized at use)
    vehicle_mix: Dict[VehicleType, float]
    # Base vehicles/minute/lane arriving under free-flow (off-peak) conditions
    base_arrival_rate: float
    # Multiplier applied to base_arrival_rate during peak windows
    peak_multiplier: float
    # 24h list of (start_hour, end_hour) tuples considered "peak"
    peak_hours: list = field(default_factory=lambda: [(8, 11), (17, 21)])
    # Fraction of vehicles likely to jump signal / encroach on red (lane discipline factor)
    signal_violation_rate: float = 0.05
    # Average pedestrian jaywalking events per minute, affecting effective green time
    jaywalking_rate_per_min: float = 2.0
    notes: str = ""


CITY_PROFILES: Dict[str, CityProfile] = {
    "mumbai": CityProfile(
        name="Mumbai",
        state="Maharashtra",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.40,
            VehicleType.CAR: 0.28,
            VehicleType.AUTO_RICKSHAW: 0.20,
            VehicleType.BUS: 0.06,
            VehicleType.TRUCK: 0.03,
            VehicleType.CYCLE: 0.03,
        },
        base_arrival_rate=9.0,
        peak_multiplier=2.4,
        peak_hours=[(8, 11), (17, 21)],
        signal_violation_rate=0.06,
        jaywalking_rate_per_min=3.5,
        notes="High density, heavy two-wheeler and auto-rickshaw share, severe peak congestion.",
    ),
    "delhi": CityProfile(
        name="Delhi",
        state="Delhi (NCT)",
        vehicle_mix={
            VehicleType.CAR: 0.36,
            VehicleType.TWO_WHEELER: 0.34,
            VehicleType.AUTO_RICKSHAW: 0.12,
            VehicleType.BUS: 0.08,
            VehicleType.TRUCK: 0.06,
            VehicleType.CYCLE: 0.04,
        },
        base_arrival_rate=8.5,
        peak_multiplier=2.2,
        peak_hours=[(8, 10), (17, 20)],
        signal_violation_rate=0.07,
        jaywalking_rate_per_min=2.5,
        notes="Wider roads but higher car ownership; freight truck traffic at night.",
    ),
    "bangalore": CityProfile(
        name="Bangalore",
        state="Karnataka",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.45,
            VehicleType.CAR: 0.32,
            VehicleType.AUTO_RICKSHAW: 0.14,
            VehicleType.BUS: 0.06,
            VehicleType.TRUCK: 0.02,
            VehicleType.CYCLE: 0.01,
        },
        base_arrival_rate=8.0,
        peak_multiplier=2.6,
        peak_hours=[(9, 11), (17, 21)],
        signal_violation_rate=0.04,
        jaywalking_rate_per_min=2.0,
        notes="IT-corridor commute peaks; high two-wheeler share; notorious tech-park congestion.",
    ),
    "chennai": CityProfile(
        name="Chennai",
        state="Tamil Nadu",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.42,
            VehicleType.CAR: 0.27,
            VehicleType.AUTO_RICKSHAW: 0.17,
            VehicleType.BUS: 0.08,
            VehicleType.TRUCK: 0.03,
            VehicleType.CYCLE: 0.03,
        },
        base_arrival_rate=7.5,
        peak_multiplier=2.1,
        peak_hours=[(8, 10), (17, 20)],
        signal_violation_rate=0.05,
        jaywalking_rate_per_min=2.2,
        notes="Coastal city grid roads; moderate congestion outside IT corridor.",
    ),
    "pune": CityProfile(
        name="Pune",
        state="Maharashtra",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.48,
            VehicleType.CAR: 0.28,
            VehicleType.AUTO_RICKSHAW: 0.13,
            VehicleType.BUS: 0.06,
            VehicleType.TRUCK: 0.03,
            VehicleType.CYCLE: 0.02,
        },
        base_arrival_rate=7.0,
        peak_multiplier=2.3,
        peak_hours=[(8, 10), (18, 21)],
        signal_violation_rate=0.05,
        jaywalking_rate_per_min=2.0,
        notes="Very high two-wheeler density driven by student/IT population.",
    ),
    "generic_tier1": CityProfile(
        name="Generic Tier-1 Indian City",
        state="N/A",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.42,
            VehicleType.CAR: 0.30,
            VehicleType.AUTO_RICKSHAW: 0.15,
            VehicleType.BUS: 0.06,
            VehicleType.TRUCK: 0.04,
            VehicleType.CYCLE: 0.03,
        },
        base_arrival_rate=7.5,
        peak_multiplier=2.2,
        peak_hours=[(8, 11), (17, 20)],
        signal_violation_rate=0.05,
        jaywalking_rate_per_min=2.0,
        notes="Default fallback profile blending common metro characteristics.",
    ),
    "generic_tier2": CityProfile(
        name="Generic Tier-2 Indian City",
        state="N/A",
        vehicle_mix={
            VehicleType.TWO_WHEELER: 0.50,
            VehicleType.CAR: 0.22,
            VehicleType.AUTO_RICKSHAW: 0.16,
            VehicleType.BUS: 0.05,
            VehicleType.TRUCK: 0.04,
            VehicleType.CYCLE: 0.03,
        },
        base_arrival_rate=4.5,
        peak_multiplier=1.8,
        peak_hours=[(9, 10), (18, 19)],
        signal_violation_rate=0.04,
        jaywalking_rate_per_min=1.5,
        notes="Lower base volume, lighter peaks, smaller road network assumption.",
    ),
}


def get_city_profile(key: str) -> CityProfile:
    """Fetch a registered profile by key (case-insensitive), default to generic_tier1."""
    key_norm = key.strip().lower().replace(" ", "_")
    if key_norm not in CITY_PROFILES:
        available = ", ".join(sorted(CITY_PROFILES))
        raise KeyError(f"Unknown city profile '{key}'. Available: {available}")
    return CITY_PROFILES[key_norm]


def list_city_profiles() -> list:
    return sorted(CITY_PROFILES.keys())
