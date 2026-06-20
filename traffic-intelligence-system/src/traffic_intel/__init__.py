"""
traffic_intel
=============

A Traffic Intersection Intelligence System for Indian smart-city
scenarios: simulates vehicle arrivals and movement at a 4-way
signalized intersection, runs adaptive congestion-aware signal control,
and produces flow/congestion analytics.

Quick start
-----------
    from traffic_intel import IntersectionSimulator, CongestionAnalyzer
    from traffic_intel.city_profiles import get_city_profile

    profile = get_city_profile("mumbai")
    sim = IntersectionSimulator(city_profile=profile, seed=42)
    sim.signal.enable_adaptive(lambda d: sum(l.queue_length for l in sim.lanes[d]))

    analyzer = CongestionAnalyzer(tick_seconds=sim.tick_seconds)
    for snapshot in sim.run(n_ticks=900):
        analyzer.ingest(snapshot)

    report = analyzer.analyze()
    print(report.overall_congestion, report.throughput_per_min)
"""

from .analytics import AnalysisReport, CongestionAnalyzer, CongestionLevel, classify_congestion
from .city_profiles import CityProfile, CITY_PROFILES, get_city_profile, list_city_profiles
from .models import (
    Direction,
    Lane,
    TurnIntent,
    Vehicle,
    VehicleType,
    VEHICLE_PROFILES,
)
from .signal_control import SignalController, SignalPhase, SignalState
from .simulator import IntersectionSimulator, TickSnapshot

__version__ = "1.0.0"

__all__ = [
    "IntersectionSimulator",
    "TickSnapshot",
    "CongestionAnalyzer",
    "AnalysisReport",
    "CongestionLevel",
    "classify_congestion",
    "CityProfile",
    "CITY_PROFILES",
    "get_city_profile",
    "list_city_profiles",
    "Direction",
    "Lane",
    "TurnIntent",
    "Vehicle",
    "VehicleType",
    "VEHICLE_PROFILES",
    "SignalController",
    "SignalPhase",
    "SignalState",
]
