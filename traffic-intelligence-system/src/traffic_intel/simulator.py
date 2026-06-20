"""
Simulation engine for the Traffic Intersection Intelligence System.

Drives a tick-based simulation of a 4-way signalized intersection:
generates vehicle arrivals according to a city traffic profile, advances
vehicles toward the stop line, releases them on green, and emits
per-tick snapshots consumed by the analytics and signal-control modules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .city_profiles import CityProfile
from .models import (
    Direction,
    Lane,
    TurnIntent,
    Vehicle,
    VehicleType,
    VEHICLE_PROFILES,
    make_intersection_lanes,
)
from .signal_control import SignalController, SignalPhase, SignalState


@dataclass
class TickSnapshot:
    """Immutable-ish record of intersection state at a single simulation tick."""

    tick: int
    sim_time_s: float
    hour_of_day: float
    signal_state: Dict[str, str]
    lane_queues: Dict[str, int]
    lane_density: Dict[str, float]
    vehicles_crossed_this_tick: int
    total_vehicles_crossed: int
    total_vehicles_waiting: int
    avg_wait_time_s: float
    violations_this_tick: int
    total_violations: int


class IntersectionSimulator:
    """Tick-based simulator for a single 4-way signalized intersection.

    Parameters
    ----------
    city_profile:
        Traffic-pattern profile (vehicle mix, arrival rates, peak hours).
    lanes_per_direction:
        Number of approach lanes modeled per direction.
    tick_seconds:
        Real-world seconds represented by one simulation tick.
    start_hour:
        Hour-of-day (0-23, float allowed) the simulation begins at; advances
        as ticks accumulate so peak-hour multipliers apply realistically.
    seed:
        Optional RNG seed for reproducible runs (useful in tests/CI).
    """

    def __init__(
        self,
        city_profile: CityProfile,
        lanes_per_direction: int = 2,
        tick_seconds: float = 2.0,
        start_hour: float = 8.0,
        seed: Optional[int] = None,
        direction_arrival_multipliers: Optional[Dict[Direction, float]] = None,
    ) -> None:
        self.city_profile = city_profile
        self.tick_seconds = tick_seconds
        self.lanes_per_direction = lanes_per_direction
        self._rng = random.Random(seed)

        # Allows modeling an arterial road (e.g. a main highway approach)
        # carrying more traffic than a quieter side street. Defaults to
        # uniform load across all four approaches.
        self.direction_arrival_multipliers: Dict[Direction, float] = (
            direction_arrival_multipliers
            if direction_arrival_multipliers is not None
            else {d: 1.0 for d in Direction}
        )

        self.lanes: Dict[Direction, List[Lane]] = make_intersection_lanes(lanes_per_direction)
        self.signal = SignalController(tick_seconds=tick_seconds)

        self.tick: int = 0
        self.sim_time_s: float = start_hour * 3600.0
        self.total_crossed: int = 0
        self.total_violations: int = 0
        self.total_wait_accum_s: float = 0.0
        self.total_wait_samples: int = 0
        # Wait time (s) of each vehicle at the moment it finally crosses,
        # bucketed by approach direction -- the metric that best reflects
        # what a driver actually experiences at this intersection.
        self.completed_wait_times: Dict[Direction, List[float]] = {d: [] for d in Direction}

        self._vehicle_type_pool: List[VehicleType] = list(city_profile.vehicle_mix.keys())
        self._vehicle_type_weights: List[float] = list(city_profile.vehicle_mix.values())

    # ------------------------------------------------------------------ #
    # Public properties
    # ------------------------------------------------------------------ #

    @property
    def hour_of_day(self) -> float:
        return (self.sim_time_s / 3600.0) % 24.0

    @property
    def is_peak_hour(self) -> bool:
        h = self.hour_of_day
        for start, end in self.city_profile.peak_hours:
            if start <= h < end:
                return True
        return False

    def current_arrival_rate(self, direction: Optional[Direction] = None) -> float:
        """Vehicles per minute per lane, adjusted for peak/off-peak and direction."""
        rate = self.city_profile.base_arrival_rate
        if self.is_peak_hour:
            rate *= self.city_profile.peak_multiplier
        if direction is not None:
            rate *= self.direction_arrival_multipliers.get(direction, 1.0)
        return rate

    # ------------------------------------------------------------------ #
    # Core simulation step
    # ------------------------------------------------------------------ #

    def step(self) -> TickSnapshot:
        """Advance the simulation by one tick and return a snapshot."""
        self.tick += 1
        self.sim_time_s += self.tick_seconds

        self.signal.advance(self.tick_seconds)
        self._spawn_arrivals()
        crossed_this_tick, violations_this_tick = self._advance_vehicles()

        self.total_crossed += crossed_this_tick
        self.total_violations += violations_this_tick

        return self._build_snapshot(crossed_this_tick, violations_this_tick)

    def run(self, n_ticks: int) -> List[TickSnapshot]:
        """Run the simulation for n_ticks and return all snapshots."""
        return [self.step() for _ in range(n_ticks)]

    # ------------------------------------------------------------------ #
    # Internal mechanics
    # ------------------------------------------------------------------ #

    def _spawn_arrivals(self) -> None:
        """Probabilistically spawn new vehicles into each lane this tick."""
        minute_fraction = self.tick_seconds / 60.0
        for direction in Direction:
            for lane in self.lanes[direction]:
                expected = self.current_arrival_rate(direction) * minute_fraction
                # Poisson-like arrival via random threshold (cheap, no numpy dependency)
                if self._rng.random() < min(0.95, expected):
                    if lane.density_ratio < 0.97:  # don't overflow a full lane
                        lane.queue.append(self._spawn_vehicle(direction))

    def _spawn_vehicle(self, direction: Direction) -> Vehicle:
        vtype = self._rng.choices(self._vehicle_type_pool, weights=self._vehicle_type_weights, k=1)[0]
        turn = self._rng.choices(
            [TurnIntent.STRAIGHT, TurnIntent.LEFT, TurnIntent.RIGHT],
            weights=[0.60, 0.20, 0.20],
            k=1,
        )[0]
        v = Vehicle(vehicle_type=vtype, direction=direction, turn_intent=turn)
        # Assign speed from this simulator's own seeded RNG so runs with
        # the same seed are fully reproducible (Vehicle itself never
        # touches the global `random` module).
        lo, hi = VEHICLE_PROFILES[vtype]["speed_kmh"]
        v.speed_kmh = self._rng.uniform(lo, hi)
        v.entered_at_tick = self.tick
        # Place at back of the visible queue window
        lane = self.lanes[direction][0]
        v.position_m = max(lane.capacity_m - lane.occupied_length_m, v.length_m)
        return v

    def _advance_vehicles(self) -> tuple[int, int]:
        """Move vehicles toward the stop line; release crossing ones on green."""
        crossed = 0
        violations = 0

        for direction in Direction:
            lane_state = self.signal.state_for(direction)
            for lane in self.lanes[direction]:
                still_queued: List[Vehicle] = []
                for idx, vehicle in enumerate(lane.queue):
                    can_move = (
                        lane_state == SignalState.GREEN
                        or (lane_state == SignalState.YELLOW and idx == 0)
                    )

                    if idx == 0 and lane_state == SignalState.RED:
                        # Small chance of a signal violation (jumping red), per city profile
                        if self._rng.random() < (self.city_profile.signal_violation_rate * self.tick_seconds / 30.0):
                            can_move = True
                            vehicle.is_violating = True
                            violations += 1

                    if can_move:
                        step_m = vehicle.speed_kmh * (1000 / 3600) * self.tick_seconds
                        vehicle.position_m -= step_m
                        if vehicle.position_m <= 0:
                            vehicle.has_crossed = True
                            crossed += 1
                            self.completed_wait_times[direction].append(vehicle.waiting_time_s)
                            continue  # vehicle leaves the lane entirely
                        still_queued.append(vehicle)
                    else:
                        vehicle.waiting_time_s += self.tick_seconds
                        still_queued.append(vehicle)

                lane.queue = still_queued

        return crossed, violations

    def _build_snapshot(self, crossed_this_tick: int, violations_this_tick: int) -> TickSnapshot:
        lane_queues: Dict[str, int] = {}
        lane_density: Dict[str, float] = {}
        total_waiting = 0
        wait_accum = 0.0

        for direction in Direction:
            total_q = sum(lane.queue_length for lane in self.lanes[direction])
            avg_density = (
                sum(lane.density_ratio for lane in self.lanes[direction]) / len(self.lanes[direction])
            )
            lane_queues[direction.value] = total_q
            lane_density[direction.value] = round(avg_density, 3)
            total_waiting += total_q
            for lane in self.lanes[direction]:
                wait_accum += sum(v.waiting_time_s for v in lane.queue)

        avg_wait = wait_accum / total_waiting if total_waiting else 0.0

        return TickSnapshot(
            tick=self.tick,
            sim_time_s=self.sim_time_s,
            hour_of_day=round(self.hour_of_day, 2),
            signal_state={d.value: self.signal.state_for(d).value for d in Direction},
            lane_queues=lane_queues,
            lane_density=lane_density,
            vehicles_crossed_this_tick=crossed_this_tick,
            total_vehicles_crossed=self.total_crossed,
            total_vehicles_waiting=total_waiting,
            avg_wait_time_s=round(avg_wait, 1),
            violations_this_tick=violations_this_tick,
            total_violations=self.total_violations,
        )

    # ------------------------------------------------------------------ #
    # Introspection helpers (used by analytics / dashboard)
    # ------------------------------------------------------------------ #

    def all_vehicles_snapshot(self) -> List[Vehicle]:
        """Flat list of all vehicles currently queued across all lanes."""
        out: List[Vehicle] = []
        for direction in Direction:
            for lane in self.lanes[direction]:
                out.extend(lane.queue)
        return out

    def completed_wait_summary(self) -> Dict[str, float]:
        """Average completed wait time (s) per direction, over the full run.

        Unlike the instantaneous `avg_wait_time_s` in each TickSnapshot
        (which only reflects vehicles still queued at that instant), this
        reflects the actual end-to-end wait experienced by vehicles that
        have already crossed -- the metric travellers actually feel.
        """
        out: Dict[str, float] = {}
        for direction, waits in self.completed_wait_times.items():
            out[direction.value] = round(sum(waits) / len(waits), 1) if waits else 0.0
        return out
